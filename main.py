import os
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# ---------------------------------------------------------
# البيانات الأساسية، الرولات، وحافظة التذاكر النشطة
# ---------------------------------------------------------

# قائمة جميع الإداريين (المسموح بالتحويل إليهم)
ALL_ADMIN_ROLES = [
    1552026718854844427,
    1552030869483687936,
    1552030964161450027,
    1552030709026131990,
    1552031186325606532,
    1552031250255188138
]

# الرولات الاستثنائية للتحكم المطلق
EXEMPT_ROLES = [
    1552026718854844427,
    1552031112413577286,
    1552026718854844427,
    1552030869483687936,
    1552030964161450027
]

# بيانات التذاكر الخمس
ticket_data = {
    'ticket_player': {
        'name': 'شكوى ضد لاعب',
        'category_id': 1552034050816999625,
        'type_text': 'تذكرة ضد لاعب',
        'panel_type': 'player',
        'roles': [1552030709026131990, 1552031186325606532, 1552031250255188138]
    },
    'ticket_faction': {
        'name': 'شكوى ضد قائد فصيل',
        'category_id': 1552034692272754738,
        'type_text': 'تذكرة ضد قائد فصيل',
        'panel_type': 'factions_staff',
        'roles': [1552030869483687936, 1552030964161450027, 1552030709026131990, 1552031186325606532]
    },
    'ticket_staff': {
        'name': 'شكوى ضد إداري',
        'category_id': 1552034331436781608,
        'type_text': 'تذكرة ضد إداري',
        'panel_type': 'factions_staff',
        'roles': [1552030869483687936, 1552030964161450027, 1552030709026131990, 1552031186325606532]
    },
    'ticket_support': {
        'name': 'الدعم الفني',
        'category_id': 1552184064121901160,
        'type_text': 'تذكرة دعم فني',
        'panel_type': 'support_store',
        'roles': [1552026718854844427, 1552031112413577286]
    },
    'ticket_store': {
        'name': 'المتجر',
        'category_id': 1552184221135675412,
        'type_text': 'تذكرة المتجر',
        'panel_type': 'support_store',
        'roles': [1552026718854844427, 1552034858216333414]
    }
}

# تخزين رومات وأبعاد اللوحات
panel_channels = {
    'player': None,
    'factions_staff': None,
    'support_store': None
}

# قاعدة البيانات المؤقتة للتذاكر النشطة
# Structure: { ticket_id: { "channel_id": int, "user_id": int, "type_name": str, "claimed_by": int or None, "panel_type": str, "card_msg_id": int or None } }
active_tickets = {}


# ---------------------------------------------------------
# دالة تحديث وإدارة كروت اللوحات المركزية (Dashboards)
# ---------------------------------------------------------
async def update_dashboard_panel(guild: discord.Guild, panel_type: str):
    channel_id = panel_channels.get(panel_type)
    if not channel_id:
        return

    channel = guild.get_channel(channel_id)
    if not channel:
        return

    # التذاكر المخصصة لهذه اللوحة
    tickets_for_panel = {
        tid: tdata for tid, tdata in active_tickets.items()
        if tdata['panel_type'] == panel_type
    }

    # إذا لا يوجد تذاكر مفتوحة في هذه اللوحة
    if not tickets_for_panel:
        async for msg in channel.history(limit=50):
            if msg.author == bot.user and "لا يوجد تذاكر حالية" in (msg.embeds[0].description if msg.embeds else ""):
                return
        embed = discord.Embed(
            title="📋 لوحة التحكم بالتذاكر",
            description="```text\nلا يوجد تذاكر حالية\n```",
            color=0x2b2d31
        )
        await channel.send(embed=embed)
        return

    # معالجة وتحديث كارت كل تذكرة مستقلة
    for tid, tdata in list(tickets_for_panel.items()):
        claimed_str = f"<@{tdata['claimed_by']}>" if tdata['claimed_by'] else "⏳ بانتظار الاستلام"

        embed = discord.Embed(
            title=f"🎫 تذكرة #{tid}",
            color=0x2b2d31
        )
        embed.add_field(name="👤 صاحب التذكرة", value=f"<@{tdata['user_id']}>", inline=True)
        embed.add_field(name="📂 النوع", value=tdata['type_name'], inline=True)
        embed.add_field(name="📌 الحالة", value=claimed_str, inline=True)
        embed.add_field(name="🔗 روم التذكرة", value=f"<#{tdata['channel_id']}>", inline=False)

        # إنشاء الأزرار المستقلة الخاصة بهذه التذكرة فقط
        view = discord.ui.View(timeout=None)
        
        claim_btn = discord.ui.Button(
            label="استلام",
            style=discord.ButtonStyle.green,
            custom_id=f"btn_claim_{tid}",
            disabled=(tdata['claimed_by'] is not None)
        )
        transfer_btn = discord.ui.Button(
            label="تحويل",
            style=discord.ButtonStyle.blurple,
            custom_id=f"btn_transfer_{tid}"
        )
        close_btn = discord.ui.Button(
            label="إغلاق",
            style=discord.ButtonStyle.red,
            custom_id=f"btn_close_{tid}"
        )

        claim_btn.callback = make_claim_callback(tid)
        transfer_btn.callback = make_transfer_callback(tid)
        close_btn.callback = make_close_callback(tid)

        view.add_item(claim_btn)
        view.add_item(transfer_btn)
        view.add_item(close_btn)

        # تحيين الرسالة أو إرسال كارت جديد
        if tdata.get('card_msg_id'):
            try:
                card_msg = await channel.fetch_message(tdata['card_msg_id'])
                await card_msg.edit(embed=embed, view=view)
            except:
                card_msg = await channel.send(embed=embed, view=view)
                tdata['card_msg_id'] = card_msg.id
        else:
            card_msg = await channel.send(embed=embed, view=view)
            tdata['card_msg_id'] = card_msg.id


# ---------------------------------------------------------
# Callbacks الأزرار
# ---------------------------------------------------------
def make_claim_callback(ticket_id):
    async def callback(interaction: discord.Interaction):
        if ticket_id not in active_tickets:
            return await interaction.response.send_message("عذراً، هذه التذكرة لم تعد موجودة.", ephemeral=True)

        tdata = active_tickets[ticket_id]
        if tdata['claimed_by'] is not None:
            return await interaction.response.send_message("هذه التذكرة مستلمة بالفعل من إداري آخر!", ephemeral=True)

        tdata['claimed_by'] = interaction.user.id
        await interaction.response.send_message(f"تم استلام التذكرة #{ticket_id} بنجاح!", ephemeral=True)

        ticket_channel = interaction.guild.get_channel(tdata['channel_id'])
        if ticket_channel:
            embed = discord.Embed(
                title="📥 تم استلام التذكرة",
                description=f"تم استلام التذكرة من قبل الإداري: {interaction.user.mention}\nسيكون معك لمتابعة طلبك الآن.",
                color=0x2ecc71
            )
            await ticket_channel.send(embed=embed)

        await update_dashboard_panel(interaction.guild, tdata['panel_type'])
    return callback


def make_transfer_callback(ticket_id):
    async def callback(interaction: discord.Interaction):
        if ticket_id not in active_tickets:
            return await interaction.response.send_message("عذراً، هذه التذكرة غير موجودة.", ephemeral=True)

        tdata = active_tickets[ticket_id]
        user_roles = [r.id for r in interaction.user.roles]

        is_exempt = any(rid in EXEMPT_ROLES for rid in user_roles)
        is_claimer = (tdata['claimed_by'] == interaction.user.id)

        if not (is_claimer or is_exempt):
            return await interaction.response.send_message("لا تملك صلاحية تحويل هذه التذكرة لأنك لست الإداري المستلم لها!", ephemeral=True)

        options = []
        guild = interaction.guild
        for member in guild.members:
            if any(r.id in ALL_ADMIN_ROLES for r in member.roles) and not member.bot:
                options.append(discord.SelectOption(label=member.display_name, value=str(member.id)))

        if not options:
            return await interaction.response.send_message("لم يتم العثور على إداريين متصلين متاحين للتحويل.", ephemeral=True)

        select = discord.ui.Select(placeholder="اختر الإداري المراد تحويل التذكرة إليه", options=options[:25])

        async def select_callback(select_interaction: discord.Interaction):
            new_admin_id = int(select.values[0])
            tdata['claimed_by'] = new_admin_id

            await select_interaction.response.send_message(f"تم تحويل التذكرة إلى <@{new_admin_id}> بنجاح!", ephemeral=True)

            ticket_channel = guild.get_channel(tdata['channel_id'])
            if ticket_channel:
                embed = discord.Embed(
                    title="🔄 تم تحويل التذكرة",
                    description=f"تم تحويل التذكرة للإداري: <@{new_admin_id}>\nسيقوم بمتابعة التذكرة مع حضرتكم.",
                    color=0x3498db
                )
                await ticket_channel.send(embed=embed)

            await update_dashboard_panel(guild, tdata['panel_type'])

        select.callback = select_callback
        view = discord.ui.View()
        view.add_item(select)
        await interaction.response.send_message("يرجى اختيار الإداري من القائمة أدناه:", view=view, ephemeral=True)

    return callback


def make_close_callback(ticket_id):
    async def callback(interaction: discord.Interaction):
        if ticket_id not in active_tickets:
            return await interaction.response.send_message("هذه التذكرة غير موجودة بالفعل.", ephemeral=True)

        tdata = active_tickets[ticket_id]
        user_roles = [r.id for r in interaction.user.roles]

        is_exempt = any(rid in EXEMPT_ROLES for rid in user_roles)
        is_claimer = (tdata['claimed_by'] == interaction.user.id)

        if not (is_claimer or is_exempt):
            return await interaction.response.send_message("لا تملك صلاحية إغلاق هذه التذكرة لأنك لست الإداري المستلم!", ephemeral=True)

        await interaction.response.send_message("جاري إغلاق وحذف روم التذكرة...", ephemeral=True)

        ticket_channel = interaction.guild.get_channel(tdata['channel_id'])
        panel_type = tdata['panel_type']
        card_msg_id = tdata.get('card_msg_id')

        # حذف كارت التذكرة من قناة اللوحة
        panel_channel_id = panel_channels.get(panel_type)
        if panel_channel_id and card_msg_id:
            panel_chan = interaction.guild.get_channel(panel_channel_id)
            if panel_chan:
                try:
                    msg = await panel_chan.fetch_message(card_msg_id)
                    await msg.delete()
                except:
                    pass

        # حذف التذكرة
        del active_tickets[ticket_id]

        if ticket_channel:
            try:
                await ticket_channel.delete()
            except:
                pass

        await update_dashboard_panel(interaction.guild, panel_type)
    return callback


# ---------------------------------------------------------
# قائمة اختيار التذاكر الرئيسية
# ---------------------------------------------------------
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="شكوى ضد لاعب", value="ticket_player", emoji="📗", description="لتقديم البلاغات ضد اللاعبين والاستفسار عن العقوبات"),
            discord.SelectOption(label="شكوى ضد قائد فصيل", value="ticket_faction", emoji="📘", description="لتقديم الشكاوى ضد قادة الفصائل وتجاوزاتهم"),
            discord.SelectOption(label="شكوى ضد إداري", value="ticket_staff", emoji="📕", description="للإبلاغ عن تجاوز أو سوء استخدام للسلطة للإدارة"),
            discord.SelectOption(label="الدعم الفني", value="ticket_support", emoji="🛠️", description="للمساعدة العامة وحل المشاكل التقنية"),
            discord.SelectOption(label="المتجر", value="ticket_store", emoji="🛍️"),
            discord.SelectOption(label="قواعد التذاكر", value="ticket_rules", emoji="📜", description="لإظهار قوانين وشروط التذاكر")
        ]
        super().__init__(placeholder="يرجى اختيار الموضوع المناسب", min_values=1, max_values=1, options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]

        # اعادة تعيين الـ View لتصفير الخيار المختار
        await interaction.message.edit(view=TicketView())

        if key == "ticket_rules":
            rules_text = (
                "**قواعد التذاكر:**\n\n"
                "1. لن يتم قبول أي شكاوى مقدمة من طرف ثالث.\n"
                "2. قد لا يتم قبول الأدلة إذا تم تسجيلها قبل أكثر من أسبوع من تاريخ فتح التذكرة.\n"
                "3. يمكن تقديم طلب استئناف ضد العقوبات الصادرة من الإداريين خلال مدة أقصاها 3 أيام فقط.\n"
                "4. يُمنع منعاً باتاً فتح أكثر من تذكرة لنفس الحالة أو الشكوى.\n"
                "5. يجب أن يكون التاريخ، الوقت، واسم الشخص ظاهرين بوضوح تام في الأدلة المُقدمة، والا سيتم رفض الشكوى فوراً.\n"
                "6. الشكاوي ليست مجهولة أو سرية؛ وقد يتم مشاركة الدليل مع الطرف الآخر عند اتخاذ الإجراءات.\n"
                "7. يُمنع استخدام الإشارات (Mentions) غير الضرورية أو إساءة استخدامها للإدارة داخل التذاكر.\n"
                "8. تستغرق مدة مراجعة الشكاوي، التقارير، واتخاذ الإجراءات اللازمة ما يصل إلى 24 ساعة كحد أقصى."
            )
            return await interaction.response.send_message(rules_text, ephemeral=True)

        await interaction.response.defer(ephemeral=True)
        data = ticket_data[key]
        guild = interaction.guild
        member = interaction.user

        category = guild.get_channel(data['category_id'])

        # توليد رقم عشوائي مكون من 6 أرقام
        ticket_id = str(random.randint(100000, 999999))
        channel_name = f"ticket-{ticket_id}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        for role_id in data['roles']:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # إنشاء الروم
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        active_tickets[ticket_id] = {
            "channel_id": channel.id,
            "user_id": member.id,
            "type_name": data['name'],
            "claimed_by": None,
            "panel_type": data['panel_type'],
            "card_msg_id": None
        }

        # إنشاء الإمبد الأساسي داخل التذكرة بالتنسيق المحدث بالضبط
        embed = discord.Embed(
            title="قسم التذاكر والدعم الفني",
            description=f"قام {member.mention} بإنشاء تذكرة",
            color=0x2b2d31
        )
        embed.add_field(name="🎫 نوع التذكرة", value=data['name'], inline=True)
        embed.add_field(name="رقم التذكرة", value=f"`{ticket_id}`", inline=True)
        embed.set_footer(text="يرجى كتابة تفاصيل مشكلتك وانتظار رد الإدارة.")

        role_mentions = "\n".join([f"• <@&{r}>" for r in data['roles']])

        await channel.send(embed=embed)
        await channel.send(f"**طاقم الإدارة المسؤول:**\n{role_mentions}")

        await interaction.followup.send(f"تم فتح تذكرتك بنجاح: {channel.mention}", ephemeral=True)

        await update_dashboard_panel(guild, data['panel_type'])


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# ---------------------------------------------------------
# الأحداث والأوامر
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")
    bot.add_view(TicketView())


@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = discord.Embed(
        title="قسم التذاكر والدعم الفني",
        description="مرحباً بك في قسم التذاكر والدعم الفني. اختر الموضوع المناسب من القائمة أدناه لنساعدك في أقرب وقت",
        color=0x2b2d31
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1552028670900830299/1552030625693966438/IMG__.png?ex=6ab4c968&is=6ab377e8&hm=00b6d179088f91b56be8c75f43a6425bd6826d2d345ec91dedc79b7a13868d3c&")
    embed.set_footer(text="يرجى الالتزام بقوانين التذاكر لتجنب التعرض للعقوبة.")

    view = TicketView()
    await ctx.send(embed=embed, view=view)
    try: await ctx.message.delete()
    except: pass


@bot.command(name="setup_player_panel")
@commands.has_permissions(administrator=True)
async def setup_player_panel(ctx):
    panel_channels['player'] = ctx.channel.id
    await update_dashboard_panel(ctx.guild, 'player')
    try: await ctx.message.delete()
    except: pass


@bot.command(name="setup_factions_staff_panel")
@commands.has_permissions(administrator=True)
async def setup_factions_staff_panel(ctx):
    panel_channels['factions_staff'] = ctx.channel.id
    await update_dashboard_panel(ctx.guild, 'factions_staff')
    try: await ctx.message.delete()
    except: pass


@bot.command(name="setup_support_store_panel")
@commands.has_permissions(administrator=True)
async def setup_support_store_panel(ctx):
    panel_channels['support_store'] = ctx.channel.id
    await update_dashboard_panel(ctx.guild, 'support_store')
    try: await ctx.message.delete()
    except: pass


bot.run(os.getenv("DISCORD_TOKEN"))
