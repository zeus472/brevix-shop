import discord
from discord.ext import commands
from discord.ui import View, Button, Select, Modal, TextInput
import json
import os
import datetime

# ==========================================
# 1. إعدادات البوت والبيانات
# ==========================================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# الأقسام الـ 5 المعتمدة
CATEGORIES = {
    "player_complaint": "شكوى ضد لاعب",
    "faction_complaint": "شكوى ضد قائد فصيل",
    "admin_complaint": "شكوى ضد إداري",
    "tech_support": "الدعم الفني",
    "store_ticket": "المتجر"
}

# أسباب الإغلاق الثلاثة
CLOSE_REASONS = [
    "عفوا قائمة التذاكر ممتلئة حاليا يرجي المحاولة في وقت لاحق",
    "عفوا قسم {category} مغلق حاليا للصيانة يرجي المحاولة في وقت لاحق",
    "عفوا قسم {category} مغلق حاليا من قبل الإداري يرجي المحاولة في وقت لاحق"
]

# الرولات المصرح لها بفتح لوحة التحكم
ALLOWED_ROLES = [
    1552026718854844427,
    1552031112413577286,
    1552030869483687936,
    1552030964161450027
]

DATA_FILE = "bot_settings.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {
            "closed_categories": {}, # {cat_key: reason_index}
            "banned_users": [],       # [user_id]
            "blocked_admins": [],     # [admin_id]
            "active_tickets": {}      # {channel_id: ...}
        }
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

bot_data = load_data()

# ==========================================
# 2. وظائف مساعدة لحساب الوقت والتنسيق
# ==========================================
def format_time_spent(start_iso):
    start_time = datetime.datetime.fromisoformat(start_iso)
    now = datetime.datetime.now(datetime.timezone.utc)
    delta = now - start_time
    minutes = int(delta.total_seconds() // 60)
    
    if minutes < 1:
        return "أقل من دقيقة"
    elif minutes == 1:
        return "دقيقة واحدة"
    elif minutes == 2:
        return "دقيقتان"
    elif 3 <= minutes <= 10:
        return f"{minutes} دقائق"
    else:
        return f"{minutes} دقيقة"

def is_authorized(user: discord.Member):
    user_role_ids = [role.id for role in user.roles]
    return any(role_id in ALLOWED_ROLES for role_id in user_role_ids)

# ==========================================
# 3. لوحة التحكم الإدارية (Admin Control Panel)
# ==========================================

# ----------------- أ) حظر التذاكر -----------------
class UserLookupModal(Modal, title="🔍 الاستعلام عن عضو"):
    user_id_input = TextInput(label="ID العضو", placeholder="أدخل رقم ID العضو هنا...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            target_id = int(self.user_id_input.value)
        except ValueError:
            await interaction.response.send_message("❌ عفواً، يجب كتابة ID صحيح (أرقام فقط).", ephemeral=True)
            return

        is_banned = target_id in bot_data["banned_users"]
        embed = discord.Embed(
            title="🛡️ تفاصيل حالة العضو",
            description=f"**العضو:** <@{target_id}> (`{target_id}`)\n**الحالة الحالية:** " + ("🛑 **محظور من فتح التذاكر**" if is_banned else "✅ **غير محظور**"),
            color=discord.Color.red() if is_banned else discord.Color.green()
        )
        view = UserBanToggleView(target_id, is_banned)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class UserBanToggleView(View):
    def __init__(self, target_id: int, is_banned: bool):
        super().__init__(timeout=120)
        self.target_id = target_id
        self.is_banned = is_banned
        
        btn_label = "🔓 فك الحظر عن العضو" if is_banned else "🚫 حظر العضو من التذاكر"
        btn_style = discord.ButtonStyle.success if is_banned else discord.ButtonStyle.danger
        
        button = Button(label=btn_label, style=btn_style, custom_id="toggle_ban_btn")
        button.callback = self.toggle_ban
        self.add_item(button)

    async def toggle_ban(self, interaction: discord.Interaction):
        if self.is_banned:
            bot_data["banned_users"].remove(self.target_id)
            save_data(bot_data)
            await interaction.response.send_message(f"✅ تم فك الحظر بنجاح عن <@{self.target_id}>.", ephemeral=True)
        else:
            bot_data["banned_users"].append(self.target_id)
            save_data(bot_data)
            await interaction.response.send_message(f"🛑 تم حظر العضو <@{self.target_id}> من فتح التذاكر بنجاح.", ephemeral=True)

# ----------------- ب) حالة إداري -----------------
class AdminLookupModal(Modal, title="👨‍💼 الاستعلام عن حالة إداري"):
    admin_id_input = TextInput(label="ID الإداري", placeholder="أدخل رقم ID الإداري هنا...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            admin_id = int(self.admin_id_input.value)
        except ValueError:
            await interaction.response.send_message("❌ عفواً، يجب كتابة ID صحيح (أرقام فقط).", ephemeral=True)
            return

        is_blocked = admin_id in bot_data["blocked_admins"]
        embed = discord.Embed(
            title="⚙️ حالة استلام التذاكر للإداري",
            description=f"**الإداري:** <@{admin_id}> (`{admin_id}`)\n**وضع الاستلام:** " + ("🚫 **ممنوع من استلام وتحويل التذاكر**" if is_blocked else "✅ **متاح لاستلام التذاكر**"),
            color=discord.Color.dark_red() if is_blocked else discord.Color.blue()
        )
        view = AdminBlockToggleView(admin_id, is_blocked)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class AdminBlockToggleView(View):
    def __init__(self, admin_id: int, is_blocked: bool):
        super().__init__(timeout=120)
        self.admin_id = admin_id
        self.is_blocked = is_blocked
        
        btn_label = "✅ السماح بالإستلام والتحويل" if is_blocked else "🚫 منع من استلام وتحويل التذاكر"
        btn_style = discord.ButtonStyle.success if is_blocked else discord.ButtonStyle.danger
        
        button = Button(label=btn_label, style=btn_style, custom_id="toggle_admin_btn")
        button.callback = self.toggle_admin
        self.add_item(button)

    async def toggle_admin(self, interaction: discord.Interaction):
        if self.is_blocked:
            bot_data["blocked_admins"].remove(self.admin_id)
            save_data(bot_data)
            await interaction.response.send_message(f"✅ تم السماح للإداري <@{self.admin_id}> باستلام وتحويل التذاكر مجدداً.", ephemeral=True)
        else:
            bot_data["blocked_admins"].append(self.admin_id)
            save_data(bot_data)
            await interaction.response.send_message(f"🚫 تم منع الإداري <@{self.admin_id}> من استلام أو تحويل التذاكر إليه.", ephemeral=True)

# ----------------- ج) إدارة الأقسام (فتح/غلق) -----------------
class CategorySelectView(View):
    def __init__(self):
        super().__init__(timeout=120)
        select = Select(
            placeholder="📂 اختر القسم المراد إدارة حالته...",
            options=[discord.SelectOption(label=name, value=key) for key, name in CATEGORIES.items()]
        )
        select.callback = self.select_category
        self.add_item(select)

    async def select_category(self, interaction: discord.Interaction):
        cat_key = interaction.data['values'][0]
        cat_name = CATEGORIES[cat_key]
        is_closed = cat_key in bot_data["closed_categories"]
        
        embed = discord.Embed(
            title=f"🏷️ إدارة قسم: {cat_name}",
            description=f"**الحالة الحالية:** " + ("🔴 **مغلق**" if is_closed else "🟢 **مفتوح**"),
            color=discord.Color.red() if is_closed else discord.Color.green()
        )
        view = CategoryToggleView(cat_key)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class CategoryToggleView(View):
    def __init__(self, cat_key: str):
        super().__init__(timeout=120)
        self.cat_key = cat_key
        is_closed = cat_key in bot_data["closed_categories"]
        
        btn_label = "🔓 فتح القسم" if is_closed else "🔒 إغلاق القسم"
        btn_style = discord.ButtonStyle.success if is_closed else discord.ButtonStyle.danger
        button = Button(label=btn_label, style=btn_style)
        button.callback = self.toggle_action
        self.add_item(button)

    async def toggle_action(self, interaction: discord.Interaction):
        if self.cat_key in bot_data["closed_categories"]:
            del bot_data["closed_categories"][self.cat_key]
            save_data(bot_data)
            await interaction.response.send_message(f"🟢 تم فتح قسم **{CATEGORIES[self.cat_key]}** بنجاح أمام الأعضاء!", ephemeral=True)
        else:
            view = ReasonSelectView(self.cat_key)
            await interaction.response.send_message("⚠️ يرجى اختيار سبب إغلاق القسم:", view=view, ephemeral=True)

class ReasonSelectView(View):
    def __init__(self, cat_key: str):
        super().__init__(timeout=120)
        self.cat_key = cat_key
        
        options = []
        for idx, reason_template in enumerate(CLOSE_REASONS):
            formatted_reason = reason_template.format(category=CATEGORIES[cat_key])
            options.append(discord.SelectOption(label=f"سبب {idx+1}", description=formatted_reason[:100], value=str(idx)))
            
        select = Select(placeholder="❌ اختر سبب الإغلاق...", options=options)
        select.callback = self.reason_selected
        self.add_item(select)

    async def reason_selected(self, interaction: discord.Interaction):
        reason_idx = int(interaction.data['values'][0])
        bot_data["closed_categories"][self.cat_key] = reason_idx
        save_data(bot_data)
        
        reason_msg = CLOSE_REASONS[reason_idx].format(category=CATEGORIES[self.cat_key])
        await interaction.response.send_message(f"🔴 تم إغلاق قسم **{CATEGORIES[self.cat_key]}** بنجاح.\n**الرسالة الظاهرة للاعبين:**\n> {reason_msg}", ephemeral=True)

# ----------------- الرئيسية: لوحة التحكم الإدارية -----------------
class AdminDashboardView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📁 إدارة الأقسام", style=discord.ButtonStyle.primary, emoji="⚙️", custom_id="admin_manage_categories")
    async def manage_categories(self, interaction: discord.Interaction, button: Button):
        if not is_authorized(interaction.user):
            await interaction.response.send_message("❌ عفواً، لا تملك الصلاحية لاستخدام لوحة التحكم.", ephemeral=True)
            return
        await interaction.response.send_message("📂 اختر القسم الذي تريد تعديل حالته:", view=CategorySelectView(), ephemeral=True)

    @discord.ui.button(label="🔨 حظر التذاكر", style=discord.ButtonStyle.secondary, emoji="🚫", custom_id="admin_ban_tickets")
    async def ban_tickets(self, interaction: discord.Interaction, button: Button):
        if not is_authorized(interaction.user):
            await interaction.response.send_message("❌ عفواً، لا تملك الصلاحية لاستخدام لوحة التحكم.", ephemeral=True)
            return
        await interaction.response.send_modal(UserLookupModal())

    @discord.ui.button(label="👨‍💼 حالة إداري", style=discord.ButtonStyle.success, emoji="👑", custom_id="admin_status_tickets")
    async def admin_status(self, interaction: discord.Interaction, button: Button):
        if not is_authorized(interaction.user):
            await interaction.response.send_message("❌ عفواً، لا تملك الصلاحية لاستخدام لوحة التحكم.", ephemeral=True)
            return
        await interaction.response.send_modal(AdminLookupModal())

# ==========================================
# 4. نظام فتح التذاكر والمعالجة (المطابق للتصميم القديم)
# ==========================================

class TicketModal(Modal):
    def __init__(self, cat_key: str):
        super().__init__(title=f"بيانات {CATEGORIES[cat_key]}")
        self.cat_key = cat_key
        
        self.ingame_name = TextInput(label="الاسم باللعبة", placeholder="اكتب اسمك داخل اللعبة...", required=True)
        self.target_name = TextInput(label="المشتكى عليه", placeholder="اسم المشتكى عليه (إن وجد)...", required=False)
        self.problem_desc = TextInput(label="شرح المشكلة", style=discord.TextStyle.paragraph, placeholder="اكتب تفاصيل الشكوى بالتفصيل...", required=True)
        
        self.add_item(self.ingame_name)
        self.add_item(self.target_name)
        self.add_item(self.problem_desc)

    async def on_submit(self, interaction: discord.Interaction):
        if self.cat_key in bot_data["closed_categories"]:
            reason_idx = bot_data["closed_categories"][self.cat_key]
            if reason_idx == 0:
                msg = CLOSE_REASONS[0].format(category=CATEGORIES[self.cat_key])
                await interaction.response.send_message(msg, ephemeral=True)
                return

        guild = interaction.guild
        category_channel = discord.utils.get(guild.categories, name="التذاكر") or await guild.create_category("التذاكر")
        
        ticket_number = datetime.datetime.now().strftime("%f")[:6]
        channel_name = f"ticket-{ticket_number}"
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            interaction.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        
        ticket_channel = await guild.create_text_channel(name=channel_name, category=category_channel, overwrites=overwrites)
        start_time_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        panel_channel = discord.utils.get(guild.channels, name="player-tickets")
        card_msg_id = None
        
        if panel_channel:
            card_embed = discord.Embed(title=f"كارت تذكرة جديدة #{ticket_number}", color=discord.Color.blue())
            card_embed.add_field(name="👤 صاحب التذكرة", value=interaction.user.mention, inline=False)
            card_embed.add_field(name="📬 نوع التذكرة", value=CATEGORIES[self.cat_key], inline=False)
            card_embed.add_field(name="📌 الحالة", value="غير مستلمة", inline=False)
            
            data_text = f"• **الاسم باللعبة:** {self.ingame_name.value}\n"
            if self.target_name.value:
                data_text += f"• **المشتكى عليه:** {self.target_name.value}\n"
            data_text += f"• **شرح المشكلة:** {self.problem_desc.value}"
            
            card_embed.add_field(name="📋 البيانات المدخلة", value=data_text, inline=False)
            card_embed.add_field(name="⏱️ الوقت المستغرق", value="أقل من دقيقة", inline=False)
            card_embed.add_field(name="🏷️ روم التذكرة", value=ticket_channel.mention, inline=False)
            
            card_msg = await panel_channel.send(embed=card_embed, view=TicketCardActionsView(ticket_channel.id))
            card_msg_id = card_msg.id

        bot_data["active_tickets"][str(ticket_channel.id)] = {
            "user_id": interaction.user.id,
            "admin_id": None,
            "start_time": start_time_iso,
            "card_msg_id": card_msg_id,
            "panel_channel_id": panel_channel.id if panel_channel else None,
            "category": CATEGORIES[self.cat_key],
            "ticket_number": ticket_number,
            "ingame_name": self.ingame_name.value,
            "target_name": self.target_name.value,
            "problem_desc": self.problem_desc.value
        }
        save_data(bot_data)

        welcome_embed = discord.Embed(
            title=f"تذكرة {CATEGORIES[self.cat_key]} #{ticket_number}",
            description=f"أهلاً بك {interaction.user.mention}، تم فتح تذكرتك بنجاح.\nيرجى انتظار رد الفريق الإداري.",
            color=discord.Color.green()
        )
        await ticket_channel.send(embed=welcome_embed)
        await interaction.response.send_message(f"✅ تم فتح تذكرتك بنجاح في {ticket_channel.mention}", ephemeral=True)

# ---------------- القائمة المنسدلة لاختيار الموضوع ----------------
class TicketSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="شكوى ضد لاعب",
                description="لتقديم البلاغات ضد اللاعبين والاستفسار عن العقوبات",
                emoji="📗",
                value="player_complaint"
            ),
            discord.SelectOption(
                label="شكوى ضد قائد فصيل",
                description="لتتقديم الشكاوى ضد قادة الفصائل وتجاوزاتهم",
                emoji="📘",
                value="faction_complaint"
            ),
            discord.SelectOption(
                label="شكوى ضد إداري",
                description="للإبلاغ عن تجاوز أو سوء استخدام السلطة للإدارة",
                emoji="📕",
                value="admin_complaint"
            ),
            discord.SelectOption(
                label="الدعم الفني",
                description="للمساعدة العامة وحل المشاكل التقنية",
                emoji="🛠️",
                value="tech_support"
            ),
            discord.SelectOption(
                label="المتجر",
                description="استفسارات ومعاملات متجر السيرفر",
                emoji="👛",
                value="store_ticket"
            ),
        ]
        super().__init__(placeholder="يرجى اختيار الموضوع المناسب", min_values=1, max_values=1, options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        cat_key = self.values[0]

        # 1. التحقق من حظر العضو
        if interaction.user.id in bot_data["banned_users"]:
            await interaction.response.send_message("عفواً، أنت محظور من فتح التذاكر.", ephemeral=True)
            return

        # 2. التحقق من حالة القسم
        if cat_key in bot_data["closed_categories"]:
            reason_idx = bot_data["closed_categories"][cat_key]
            if reason_idx in [1, 2]:
                reason_msg = CLOSE_REASONS[reason_idx].format(category=CATEGORIES[cat_key])
                await interaction.response.send_message(reason_msg, ephemeral=True)
                return

        # فتح الـ Modal للقسم المختار
        await interaction.response.send_modal(TicketModal(cat_key))

# ---------------- واجهة التذاكر الشاملة للأعضاء ----------------
class TicketOpenView(View):
    def __init__(self):
        super().__init__(timeout=None)
        # إضافة القائمة المنسدلة
        self.add_item(TicketSelect())

    @discord.ui.button(label="قوانين التذاكر", style=discord.ButtonStyle.primary, emoji="📜", custom_id="btn_rules")
    async def show_rules(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(
            title="📜 قوانین وشروط التذاكر",
            description=(
                "• يُمنع فتح التذاكر العشوائية أو السبام.\n"
                "• يرجى الاحترام أثناء التحدث مع الفريق الإداري.\n"
                "• يرجى عدم استدعاء الإداريين (Mention) وتوفير الأدلة مباشرة."
            ),
            color=discord.Color.gold()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

# ==========================================
# 5. أزرار أفعال التذكرة (استلام، تحويل، إغلاق)
# ==========================================

class TicketCardActionsView(View):
    def __init__(self, ticket_channel_id: int):
        super().__init__(timeout=None)
        self.ticket_channel_id = str(ticket_channel_id)

    @discord.ui.button(label="استلام", style=discord.ButtonStyle.success, custom_id="card_claim_btn")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id in bot_data["blocked_admins"]:
            await interaction.response.send_message("❌ عفواً، أنت ممنوع حالياً من استلام التذاكر.", ephemeral=True)
            return

        ticket_info = bot_data["active_tickets"].get(self.ticket_channel_id)
        if not ticket_info:
            await interaction.response.send_message("❌ تعذر العثور على بيانات التذكرة.", ephemeral=True)
            return

        ticket_info["admin_id"] = interaction.user.id
        save_data(bot_data)

        embed = interaction.message.embeds[0]
        for idx, field in enumerate(embed.fields):
            if field.name == "📌 الحالة":
                embed.set_field_at(idx, name="📌 الحالة", value=f"مستلمة بواسطة {interaction.user.mention}", inline=False)
        
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message(f"✅ تم استلام التذكرة بواسطة {interaction.user.mention}", ephemeral=True)

    @discord.ui.button(label="تحويل", style=discord.ButtonStyle.primary, custom_id="card_transfer_btn")
    async def transfer_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(TransferModal(self.ticket_channel_id, interaction.message))

    @discord.ui.button(label="إغلاق", style=discord.ButtonStyle.danger, custom_id="card_close_btn")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CloseReasonModal(self.ticket_channel_id))

class TransferModal(Modal, title="🔄 تحويل التذكرة لإداري آخر"):
    new_admin_id_input = TextInput(label="ID الإداري الجديد", placeholder="أدخل رقم ID الإداري...", required=True)

    def __init__(self, ticket_channel_id: str, card_message: discord.Message):
        super().__init__()
        self.ticket_channel_id = ticket_channel_id
        self.card_message = card_message

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_admin_id = int(self.new_admin_id_input.value)
        except ValueError:
            await interaction.response.send_message("❌ يجب كتابة ID صحيح.", ephemeral=True)
            return

        if new_admin_id in bot_data["blocked_admins"]:
            await interaction.response.send_message("❌ لا يمكنك تحويل التذكرة لهذا الإداري لأنه ممنوع من استلام التذاكر.", ephemeral=True)
            return

        ticket_info = bot_data["active_tickets"].get(self.ticket_channel_id)
        if ticket_info:
            ticket_info["admin_id"] = new_admin_id
            save_data(bot_data)

        embed = self.card_message.embeds[0]
        for idx, field in enumerate(embed.fields):
            if field.name == "📌 الحالة":
                embed.set_field_at(idx, name="📌 الحالة", value=f"مستلمة بواسطة <@{new_admin_id}> (محولة)", inline=False)

        await self.card_message.edit(embed=embed)
        await interaction.response.send_message(f"✅ تم تحويل التذكرة للإداري <@{new_admin_id}> بنجاح.", ephemeral=True)

class CloseReasonModal(Modal, title="📝 إغلاق التذكرة وشرح الحل"):
    solution_desc = TextInput(label="ملخص الشكوى والحل", style=discord.TextStyle.paragraph, placeholder="اكتب ما تم التعامل به لإغلاق التذكرة...", required=True)

    def __init__(self, ticket_channel_id: str):
        super().__init__()
        self.ticket_channel_id = ticket_channel_id

    async def on_submit(self, interaction: discord.Interaction):
        ticket_info = bot_data["active_tickets"].get(self.ticket_channel_id)
        if not ticket_info:
            await interaction.response.send_message("❌ التذكرة غير موجودة أو تم إغلاقها سابقاً.", ephemeral=True)
            return

        total_time_str = format_time_spent(ticket_info["start_time"])
        admin_mention = f"<@{ticket_info['admin_id']}>" if ticket_info["admin_id"] else "غير محدد"
        user_id = ticket_info["user_id"]

        dm_embed = discord.Embed(
            title="ملخص إغلاق التذكرة",
            description="شكراً لتواصلك مع نظام الدعم الفني، تم إغلاق تذكرتك وتوثيق الحل بنجاح.",
            color=discord.Color.gold()
        )
        dm_embed.add_field(name="👤 منشئ التذكرة", value=f"<@{user_id}>", inline=False)
        dm_embed.add_field(name="👨‍💼 الإداري المسؤول", value=admin_mention, inline=False)
        dm_embed.add_field(name="📬 نوع التذكرة", value=ticket_info["category"], inline=False)
        dm_embed.add_field(name="🏷️ رقم التذكرة", value=ticket_info["ticket_number"], inline=False)
        dm_embed.add_field(name="📝 ملخص الشكوى والحل", value=self.solution_desc.value, inline=False)
        dm_embed.add_field(name="⏱️ إجمالي الوقت المستغرق", value=total_time_str, inline=False)

        user = interaction.guild.get_member(user_id) or await interaction.client.fetch_user(user_id)
        if user:
            try:
                await user.send(embed=dm_embed)
            except discord.Forbidden:
                pass

        channel = interaction.guild.get_channel(int(self.ticket_channel_id))
        if channel:
            await channel.delete()

        del bot_data["active_tickets"][self.ticket_channel_id]
        save_data(bot_data)

        await interaction.response.send_message("✅ تم إغلاق التذكرة وإرسال التقرير بنجاح.", ephemeral=True)

# ==========================================
# 6. الـ Tasks لتحديث الوقت بانتظام
# ==========================================
from discord.ext import tasks

@tasks.loop(minutes=1)
async def update_ticket_cards():
    for ticket_channel_id, info in list(bot_data["active_tickets"].items()):
        panel_channel_id = info.get("panel_channel_id")
        card_msg_id = info.get("card_msg_id")
        
        if not panel_channel_id or not card_msg_id:
            continue

        panel_channel = bot.get_channel(panel_channel_id)
        if not panel_channel:
            continue

        try:
            card_msg = await panel_channel.fetch_message(card_msg_id)
            if card_msg and card_msg.embeds:
                embed = card_msg.embeds[0]
                updated = False
                
                for idx, field in enumerate(embed.fields):
                    if field.name == "⏱️ الوقت المستغرق":
                        new_time = format_time_spent(info["start_time"])
                        embed.set_field_at(idx, name="⏱️ الوقت المستغرق", value=new_time, inline=False)
                        updated = True
                        break
                        
                if updated:
                    await card_msg.edit(embed=embed)
        except discord.NotFound:
            pass
        except Exception as e:
            print(f"Error updating card {card_msg_id}: {e}")

# ==========================================
# 7. أوامر التشغيل والـ Events
# ==========================================

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    bot.add_view(AdminDashboardView())
    bot.add_view(TicketOpenView())
    update_ticket_cards.start()

@bot.command()
async def setup_admin_panel(ctx):
    """أمر لإنشاء لوحة التحكم الإدارية"""
    if not is_authorized(ctx.author):
        await ctx.send("❌ لا تملك صلاحية استخدام هذا الأمر.")
        return

    embed = discord.Embed(
        title="🎛️ لوحة التحكم الإدارية الشاملة",
        description="أهلاً بك في لوحة تحكم التذاكر. يمكن للرولات المعتمدة استخدام الأزرار أدناه للتحكم بجميع خصائص النظام.",
        color=discord.Color.dark_purple()
    )
    await ctx.send(embed=embed, view=AdminDashboardView())

@bot.command()
async def setup_tickets_panel(ctx):
    """أمر لإنشاء لوحة فتح التذاكر للأعضاء بالمظهر الكامل الأصلي"""
    if not is_authorized(ctx.author):
        await ctx.send("❌ لا تملك صلاحية استخدام هذا الأمر.")
        return

    # إنشاء Embed بنص وصورة البانر الأصلي
    embed = discord.Embed(
        title="📂 قسم التذاكر والدعم الفني",
        description="مرحباً بك في قسم التذاكر والدعم الفني، اختر الموضوع المناسب من القائمة أدناه لنساعدك في أقرب وقت.\n\n*يرجى الالتزام بقوانين التذاكر لتجنب التعرض للعقوبة.*",
        color=0x2b2d31
    )
    # رابط الصورة الظاهرة في البانر القديم (BX BREVIX RP)
    embed.set_image(url="https://media.discordapp.net/attachments/1234567890/1234567890/brevix_banner.jpg") 

    await ctx.send(embed=embed, view=TicketOpenView())

# تشغيل البوت
# bot.run(os.getenv("DISCORD_TOKEN"))
