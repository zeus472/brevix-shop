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
# البيانات الأساسية، الرولات، وقنوات الإدارة
# ---------------------------------------------------------

# جميع رولات الإدارة المسموح بالتحويل إليها
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
    1552030869483687936,
    1552030964161450027
]

# بيانات التذاكر الخمس مع تحديد قنوات الإدارة الموجه إليها الكارت
ticket_data = {
    'ticket_player': {
        'name': 'شكوى ضد لاعب',
        'category_id': 1552034050816999625,
        'target_log_channel': 1552716678998134905,
        'roles': [1552030709026131990, 1552031186325606532, 1552031250255188138]
    },
    'ticket_faction': {
        'name': 'شكوى ضد قائد فصيل',
        'category_id': 1552034692272754738,
        'target_log_channel': 1552717043479093288,
        'roles': [1552030869483687936, 1552030964161450027, 1552030709026131990, 1552031186325606532]
    },
    'ticket_staff': {
        'name': 'شكوى ضد إداري',
        'category_id': 1552034331436781608,
        'target_log_channel': 1552717043479093288,
        'roles': [1552030869483687936, 1552030964161450027, 1552030709026131990, 1552031186325606532]
    },
    'ticket_support': {
        'name': 'الدعم الفني',
        'category_id': 1552184064121901160,
        'target_log_channel': 1552717816107372675,
        'roles': [1552026718854844427, 1552031112413577286]
    },
    'ticket_store': {
        'name': 'المتجر',
        'category_id': 1552184221135675412,
        'target_log_channel': 1552717816107372675,
        'roles': [1552026718854844427, 1552034858216333414]
    }
}

# قاعدة بيانات الذاكرة للتذاكر النشطة
active_tickets = {}


# ---------------------------------------------------------
# النوافذ المنبثقة (Modals) لإدخال البيانات قبل فتح التذكرة
# ---------------------------------------------------------
class TicketModal(discord.ui.Modal):
    def __init__(self, ticket_key: str):
        self.ticket_key = ticket_key
        t_info = ticket_data[ticket_key]
        super().__init__(title=f"بيانات {t_info['name']}")

        self.ingame_name = discord.ui.TextInput(
            label="اسمك داخل سيرفر اللعبة",
            placeholder="اكتب اسمك الثلاثي داخل اللعبة هنا...",
            required=True
        )
        self.add_item(self.ingame_name)

        if ticket_key == "ticket_player":
            self.target_name = discord.ui.TextInput(
                label="اسم اللاعب المقدم ضده الشكوى",
                placeholder="اكتب اسم اللاعب...",
                required=True
            )
            self.add_item(self.target_name)
        elif ticket_key == "ticket_faction":
            self.target_name = discord.ui.TextInput(
                label="اسم قائد الفصيل المقدم ضده الشكوى",
                placeholder="اكتب اسم قائد الفصيل...",
                required=True
            )
            self.add_item(self.target_name)
        elif ticket_key == "ticket_staff":
            self.target_name = discord.ui.TextInput(
                label="اسم الإداري المقدم ضده الشكوى",
                placeholder="اكتب اسم الإداري...",
                required=True
            )
            self.add_item(self.target_name)

        if ticket_key != "ticket_store":
            self.details = discord.ui.TextInput(
                label="شرح المشكلة / التفاصيل",
                style=discord.TextStyle.paragraph,
                placeholder="اشرح المشكلة بالتفصيل هنا...",
                required=True
            )
            self.add_item(self.details)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        member = interaction.user
        data = ticket_data[self.ticket_key]

        # توليد ID عشوائي وتسمية القناة
        ticket_id = str(random.randint(100000, 999999))
        channel_name = f"ticket-{ticket_id}"

        category = guild.get_channel(data['category_id'])

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        for role_id in data['roles']:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # إنشاء قناة التذكرة
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        # تجميع تفاصيل المدخلات
        form_details = f"• **الاسم باللعبة:** {self.ingame_name.value}\n"
        if hasattr(self, 'target_name'):
            form_details += f"• **المشتكى عليه:** {self.target_name.value}\n"
        if hasattr(self, 'details'):
            form_details += f"• **شرح المشكلة:** {self.details.value}\n"

        # حفظ التذكرة في الذاكرة
        active_tickets[ticket_id] = {
            "channel_id": channel.id,
            "user_id": member.id,
            "type_name": data['name'],
            "claimed_by": None,
            "card_msg_id": None,
            "log_channel_id": data['target_log_channel'],
            "form_details": form_details
        }

        # 1. إرسال الإمبد داخل روم التذكرة
        embed_ticket = discord.Embed(
            title="قسم التذاكر والدعم الفني",
            description=f"قام {member.mention} بإنشاء تذكرة",
            color=0x2b2d31
        )
        embed_ticket.add_field(name="🎫 نوع التذكرة", value=data['name'], inline=True)
        embed_ticket.add_field(name="رقم التذكرة", value=f"`{ticket_id}`", inline=True)
        embed_ticket.add_field(name="📋 بيانات التذكرة المدخلة", value=form_details, inline=False)
        
        if self.ticket_key in ["ticket_player", "ticket_faction", "ticket_staff"]:
            embed_ticket.set_footer(text="⚠️ تنبيه: يرجى إرفاق الدلائل وإثبات الحالة بعد إنشاء التذكرة فوراً.")
        else:
            embed_ticket.set_footer(text="يرجى كتابة تفاصيل طلبك وانتظار رد الإدارة.")

        role_mentions = "\n".join([f"• <@&{r}>" for r in data['roles']])

        await channel.send(embed=embed_ticket)
        await channel.send(f"**طاقم الإدارة المسؤول:**\n{role_mentions}")

        # 2. إرسال كارت التذكرة التفاعلي في قناة الإدارة المخصصة
        log_channel = guild.get_channel(data['target_log_channel'])
        if log_channel:
            card_embed = discord.Embed(
                title=f"🎫 كارت تذكرة جديدة #{ticket_id}",
                color=0x2b2d31
            )
            card_embed.add_field(name="👤 صاحب التذكرة", value=member.mention, inline=True)
            card_embed.add_field(name="📂 نوع التذكرة", value=data['name'], inline=True)
            card_embed.add_field(name="📌 الحالة", value="⏳ بانتظار الاستلام", inline=True)
            card_embed.add_field(name="📋 البيانات المدخلة", value=form_details, inline=False)
            card_embed.add_field(name="🔗 روم التذكرة", value=channel.mention, inline=False)

            view = create_ticket_control_view(ticket_id)
            card_msg = await log_channel.send(embed=card_embed, view=view)
            active_tickets[ticket_id]["card_msg_id"] = card_msg.id

        await interaction.followup.send(f"تم فتح تذكرتك بنجاح: {channel.mention}", ephemeral=True)


# ---------------------------------------------------------
# إنشاء أزرار التحكم لكروت الإدارة
# ---------------------------------------------------------
def create_ticket_control_view(ticket_id: str) -> discord.ui.View:
    view = discord.ui.View(timeout=None)
    tdata = active_tickets.get(ticket_id, {})

    claim_btn = discord.ui.Button(
        label="استلام",
        style=discord.ButtonStyle.green,
        custom_id=f"btn_claim_{ticket_id}",
        disabled=(tdata.get('claimed_by') is not None)
    )
    transfer_btn = discord.ui.Button(
        label="تحويل",
        style=discord.ButtonStyle.blurple,
        custom_id=f"btn_transfer_{ticket_id}"
    )
    close_btn = discord.ui.Button(
        label="إغلاق",
        style=discord.ButtonStyle.red,
        custom_id=f"btn_close_{ticket_id}"
    )

    claim_btn.callback = make_claim_callback(ticket_id)
    transfer_btn.callback = make_transfer_callback(ticket_id)
    close_btn.callback = make_close_callback(ticket_id)

    view.add_item(claim_btn)
    view.add_item(transfer_btn)
    view.add_item(close_btn)
    return view


# ---------------------------------------------------------
# Callbacks الأزرار (استلام / تحويل / إغلاق)
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

        # تحديث كارت الإدارة
        log_chan = interaction.guild.get_channel(tdata['log_channel_id'])
        if log_chan and tdata.get('card_msg_id'):
            try:
                card_msg = await log_chan.fetch_message(tdata['card_msg_id'])
                card_embed = card_msg.embeds[0]
                card_embed.set_field_at(2, name="📌 الحالة", value=f"مستلمة بواسطة {interaction.user.mention}", inline=True)
                await card_msg.edit(embed=card_embed, view=create_ticket_control_view(ticket_id))
            except:
                pass

        # تنبيه داخل روم التذكرة
        ticket_channel = interaction.guild.get_channel(tdata['channel_id'])
        if ticket_channel:
            embed = discord.Embed(
                title="📥 تم استلام التذكرة",
                description=f"تم استلام التذكرة من قبل الإداري: {interaction.user.mention}\nسيكون معك لمتابعة طلبك الآن.",
                color=0x2ecc71
            )
            await ticket_channel.send(embed=embed)
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
            return await interaction.response.send_message("لم يتم العثور على إداريين متاحيين للتحويل.", ephemeral=True)

        select = discord.ui.Select(placeholder="اختر الإداري المراد تحويل التذكرة إليه", options=options[:25])

        async def select_callback(select_interaction: discord.Interaction):
            new_admin_id = int(select.values[0])
            tdata['claimed_by'] = new_admin_id

            await select_interaction.response.send_message(f"تم تحويل التذكرة إلى <@{new_admin_id}> بنجاح!", ephemeral=True)

            # تحديث كارت الإدارة
            log_chan = guild.get_channel(tdata['log_channel_id'])
            if log_chan and tdata.get('card_msg_id'):
                try:
                    card_msg = await log_chan.fetch_message(tdata['card_msg_id'])
                    card_embed = card_msg.embeds[0]
                    card_embed.set_field_at(2, name="📌 الحالة", value=f"مستلمة بواسطة <@{new_admin_id}>", inline=True)
                    # إعادة ضبط الـ view وتصفير خيار القائمة المنسدلة
                    await card_msg.edit(embed=card_embed, view=create_ticket_control_view(ticket_id))
                except:
                    pass

            ticket_channel = guild.get_channel(tdata['channel_id'])
            if ticket_channel:
                embed = discord.Embed(
                    title="🔄 تم تحويل التذكرة",
                    description=f"تم تحويل التذكرة للإداري: <@{new_admin_id}>\nسيقوم بمتابعة التذكرة مع حضرتكم.",
                    color=0x3498db
                )
                await ticket_channel.send(embed=embed)

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

        # حذف كارت التذكرة من قناة الإدارة
        log_chan = interaction.guild.get_channel(tdata['log_channel_id'])
        if log_chan and tdata.get('card_msg_id'):
            try:
                msg = await log_chan.fetch_message(tdata['card_msg_id'])
                await msg.delete()
            except:
                pass

        ticket_channel = interaction.guild.get_channel(tdata['channel_id'])

        del active_tickets[ticket_id]

        if ticket_channel:
            try:
                await ticket_channel.delete()
            except:
                pass
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

        # فتح النافذة المنبثقة (Modal) لإدخال البيانات
        modal = TicketModal(key)
        await interaction.response.send_modal(modal)


class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketSelect())


# ---------------------------------------------------------
# الأحداث وأمر التحضير الرئيسي
# ---------------------------------------------------------
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")
    bot.add_view(TicketView())


@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx):
    """تحضير لوحة التذاكر الرئيسية لللاعبين"""
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


bot.run(os.getenv("DISCORD_TOKEN"))
