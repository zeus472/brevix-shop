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

# قائمة الرولات المسموح بتحويل التذاكر إليها (جميع الإداريين)
ALL_ADMIN_ROLES = [
    1552026718854844427,
    1552030869483687936,
    1552030964161450027,
    1552030709026131990,
    1552031186325606532,
    1552031250255188138
]

# الرولات الاستثنائية للتحكم المطلق بجميع التذاكر
EXEMPT_ROLES = [
    1552026718854844427,
    1552031112413577286,
    1552030869483687936,
    1552030964161450027
]

# بيانات التذاكر الخمس الأساسية
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

# قنوات وتخزين اللوحات المركزية
panel_messages = {
    'player': {'channel_id': None, 'message_id': None},
    'factions_staff': {'channel_id': None, 'message_id': None},
    'support_store': {'channel_id': None, 'message_id': None}
}

# قاعدة بيانات مؤقتة للذاكرة لتخزين التذاكر النشطة
# Structure: { ticket_id: { "channel_id": int, "user_id": int, "type_name": str, "claimed_by": int or None, "panel_type": str } }
active_tickets = {}


# ---------------------------------------------------------
# دالة تحديث اللوحات المركزية (Dashboards)
# ---------------------------------------------------------
async def update_dashboard_panel(guild: discord.Guild, panel_type: str):
    info = panel_messages.get(panel_type)
    if not info or not info['channel_id'] or not info['message_id']:
        return

    channel = guild.get_channel(info['channel_id'])
    if not channel:
        return

    try:
        msg = await channel.fetch_message(info['message_id'])
    except:
        return

    # تصفية التذاكر المخصصة لهذه اللوحة
    tickets_for_panel = {
        tid: tdata for tid, tdata in active_tickets.items()
        if tdata['panel_type'] == panel_type
    }

    panel_titles = {
        'player': "📋 لوحة التحكم | تذاكر شكاوى اللاعبين",
        'factions_staff': "📋 لوحة التحكم | تذاكر الإداريين والفصائل",
        'support_store': "📋 لوحة التحكم | تذاكر الدعم الفني والمتجر"
    }

    embed = discord.Embed(
        title=panel_titles.get(panel_type, "لوحة التحكم بالتذاكر"),
        color=0x2b2d31
    )

    if not tickets_for_panel:
        embed.description = "```text\nلا يوجد تذاكر حالية\n```"
        view = discord.ui.View(timeout=None)
        await msg.edit(embed=embed, view=view)
        return

    embed.description = "فيما يلي جميع التذاكر المفتوحة حالياً والمتاحة للإدارة:"
    view = discord.ui.View(timeout=None)

    for tid, tdata in list(tickets_for_panel.items()):
        claimed_str = f"<@{tdata['claimed_by']}>" if tdata['claimed_by'] else "⏳ بانتظار الاستلام"
        
        field_value = (
            f"👤 **صاحب التذكرة:** <@{tdata['user_id']}>\n"
            f"📂 **النوع:** {tdata['type_name']}\n"
            f"📌 **الحالة:** {claimed_str}\n"
            f"🔗 **روم التذكرة:** <#{tdata['channel_id']}>"
        )
        embed.add_field(name=f"🎫 تذكرة #{tid}", value=field_value, inline=False)

        # إضافة الأزرار لكل تذكرة
        claim_btn = discord.ui.Button(
            label=f"استلام #{tid}",
            style=discord.ButtonStyle.green,
            custom_id=f"btn_claim_{tid}",
            disabled=(tdata['claimed_by'] is not None)
        )
        transfer_btn = discord.ui.Button(
            label=f"تحويل #{tid}",
            style=discord.ButtonStyle.blurple,
            custom_id=f"btn_transfer_{tid}"
        )
        close_btn = discord.ui.Button(
            label=f"إغلاق #{tid}",
            style=discord.ButtonStyle.red,
            custom_id=f"btn_close_{tid}"
        )

        claim_btn.callback = make_claim_callback(tid)
        transfer_btn.callback = make_transfer_callback(tid)
        close_btn.callback = make_close_callback(tid)

        view.add_item(claim_btn)
        view.add_item(transfer_btn)
        view.add_item(close_btn)

    await msg.edit(embed=embed, view=view)


# ---------------------------------------------------------
# callbacks الأزرار الخاصة باللوحات
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

        # إرسال إمبد التبريكات في روم التذكرة
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

        # تحقق من الصلاحيات (المستلم أو ذوي الاستثناء)
        is_exempt = any(rid in EXEMPT_ROLES for rid in user_roles)
        is_claimer = (tdata['claimed_by'] == interaction.user.id)

        if not (is_claimer or is_exempt):
            return await interaction.response.send_message("لا تملك صلاحية تحويل هذه التذكرة لأنك لست الإداري المستلم لها!", ephemeral=True)

        # تجهيز قائمة اختيار الإداريين
        options = []
        guild = interaction.guild
        for member in guild.members:
            if any(r.id in ALL_ADMIN_ROLES for r in member.roles) and not member.bot:
                options.append(discord.SelectOption(label=member.display_name, value=str(member.id)))

        if not options:
            return await interaction.response.send_message("لم يتم العثور على إداريين متصلين متاحين للتحويل.", ephemeral=True)

        # القائمة المنسدلة للتحويل
        select = discord.ui.Select(placeholder="اختر الإداري المراد تحويل التذكرة إليه", options=options[:25])

        async def select_callback(select_interaction: discord.Interaction):
            new_admin_id = int(select.values[0])
            tdata['claimed_by'] = new_admin_id

            await select_interaction.response.send_message(f"تم تحويل التذكرة إلى <@{new_admin_id}> بنجاح!", ephemeral=True)

            # إرسال تنبيه في روم التذكرة
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

        # حذف التذكرة من السجلات
        del active_tickets[ticket_id]

        if ticket_channel:
            try:
                await ticket_channel.delete()
            except:
                pass

        await update_dashboard_panel(interaction.guild, panel_type)
    return callback


# ---------------------------------------------------------
# واجهة اختيار التذاكر القائمة المنسدلة (Main Select)
# ---------------------------------------------------------
class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="شكوى ضد لاعب", value="ticket_player", emoji="📗", description="لتقديم البلاغات ضد اللاعبين والاستفسار عن العقوبات"),
            discord.SelectOption(label="شكوى ضد قائد فصيل", value="ticket_faction", emoji="📘", description="لتقديم الشكاوى ضد قادة الفصائل وتجاوزاتهم"),
            discord.SelectOption(label="شكوى ضد إداري", value="ticket_staff", emoji="📕", description="للإبلاغ عن تجاوز أو سوء استخدام للسلطة للإدارة"),
            discord.SelectOption(label="الدعم الفني", value="ticket_support", emoji="🛠️", description="ل للمساعدة العامة وحل المشاكل التقنية"),
            discord.SelectOption(label="المتجر", value="ticket_store", emoji="🛍️"),
            discord.SelectOption(label="قواعد التذاكر", value="ticket_rules", emoji="📜", description="لإظهار قوانين وشروط التذاكر")
        ]
        super().__init__(placeholder="يرجى اختيار الموضوع المناسب", min_values=1, max_values=1, options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        key = self.values[0]

        # إعادة ضبط الواجهة فوراً لحل مشكلة احتفاظ القائمة بالخيار المختار (Fix Select Menu Persistence)
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

        # توليد رقم عشوائي مكون من 6 أرقام لتسمية القناة
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

        # إنشاء الروم الخاصة بالتذكرة
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        # حفظ التذكرة في القائمة النشطة
        active_tickets[ticket_id] = {
            "channel_id": channel.id,
            "user_id": member.id,
            "type_name": data['name'],
            "claimed_by": None,
            "panel_type": data['panel_type']
        }

        # بناء الرسالة الأولى داخل روم التذكرة (إمبد فخم)
        embed = discord.Embed(
            title="قسم التذاكر والدعم الفني",
            description=f"قام {member.mention} بإنشاء {data['type_text']}",
            color=0x2b2d31
        )
        embed.add_field(name="📂 نوع التذكرة", value=data['name'], inline=True)
        embed.add_field(name="🔢 رقم التذكرة", value=f"`{ticket_id}`", inline=True)
        embed.set_footer(text="يرجى كتابة تفاصيل مشكلتك وانتظار رد الإدارة.")

        # تجهيز المنشن المنظم للإداريين أسفل الإمبد
        role_mentions = "\n".join([f"• <@&{r}>" for r in data['roles']])

        await channel.send(embed=embed)
        await channel.send(f"**منشن طاقم الإدارة المسؤول:**\n{role_mentions}")

        # رد للمستخدم بإنشاء التذكرة
        await interaction.followup.send(f"تم فتح تذكرتك بنجاح: {channel.mention}", ephemeral=True)

        # تحديث اللوحة المركزية فوراً
        await update_dashboard_panel(guild, data['panel_type'])


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# ---------------------------------------------------------
# أحداث وأوامر تحضير اللوحات والبوت
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")
    bot.add_view(TicketView())


@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """أمر تحضير لوحة اختيار التذاكر الرئيسية"""
    embed = discord.Embed(
        title="قسم التذاكر والدعم الفني",
        description="مرحباً بك في قسم التذاكر والدعم الفني. اختر الموضوع المناسب من القائمة أدناه لنساعدك في أقرب وقت",
        color=0x2b2d31
    )
    embed.set_image(url="https://cdn.discordapp.com/attachments/1552028670900830299/1552030625693966438/IMG__.png?ex=6ab4c968&is=6ab377e8&hm=00b6d179088f91b56be8c75f43a6425bd6826d2d345ec91dedc79b7a13868d3c&")
    embed.set_footer(text="يرجى الالتزام بقوانين التذاكر لتجنب التعرض للعقوبة.")

    view = TicketView()
    await ctx.send(embed=embed, view=view)
    try:
        await ctx.message.delete()
    except:
        pass


@bot.command(name="setup_player_panel")
@commands.has_permissions(administrator=True)
async def setup_player_panel(ctx):
    """تحضير لوحة استلام تذاكر اللاعبين"""
    embed = discord.Embed(title="📋 لوحة التحكم | تذاكر شكاوى اللاعبين", description="```text\nلا يوجد تذاكر حالية\n```", color=0x2b2d31)
    msg = await ctx.send(embed=embed)
    panel_messages['player']['channel_id'] = ctx.channel.id
    panel_messages['player']['message_id'] = msg.id
    try: await ctx.message.delete()
    except: pass


@bot.command(name="setup_factions_staff_panel")
@commands.has_permissions(administrator=True)
async def setup_factions_staff_panel(ctx):
    """تحضير لوحة استلام تذاكر الفصائل والإداريين"""
    embed = discord.Embed(title="📋 لوحة التحكم | تذاكر الإداريين والفصائل", description="```text\nلا يوجد تذاكر حالية\n```", color=0x2b2d31)
    msg = await ctx.send(embed=embed)
    panel_messages['factions_staff']['channel_id'] = ctx.channel.id
    panel_messages['factions_staff']['message_id'] = msg.id
    try: await ctx.message.delete()
    except: pass


@bot.command(name="setup_support_store_panel")
@commands.has_permissions(administrator=True)
async def setup_support_store_panel(ctx):
    """تحضير لوحة استلام تذاكر الدعم الفني والمتجر"""
    embed = discord.Embed(title="📋 لوحة التحكم | تذاكر الدعم الفني والمتجر", description="```text\nلا يوجد تذاكر حالية\n```", color=0x2b2d31)
    msg = await ctx.send(embed=embed)
    panel_messages['support_store']['channel_id'] = ctx.channel.id
    panel_messages['support_store']['message_id'] = msg.id
    try: await ctx.message.delete()
    except: pass


bot.run(os.getenv("DISCORD_TOKEN"))
