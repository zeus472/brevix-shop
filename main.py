import os
import random
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قاعدة بيانات وهمية في الذاكرة لتخزين البيانات (يمكن ربطها بقاعدة بيانات لاحقاً مثل SQLite)
database = {
    "users": {},  # {user_id: {"coins": 0, "level": 0, "messages": 0, "voice_minutes": 0, "inventory": [], "discount_codes": [], "last_spin": None}}
    "products": {},  # {prod_code: {"name": "", "desc": "", "price": 0, "is_role": True, "role_id": None, "duration": None, "allow_discount": True, "allowed_users": []}}
    "levels": {},  # {level_num: {"req_msg": 0, "req_voice": 0, "reward": 0}}
    "admin_codes": {},  # {code: {"discount": 0, "uses": 0, "max_uses": None, "expiry": None}}
}

# الآي ديوهات الثابتة المطلوبة
DEFAULT_ROLE_ID = 1541620051033985085
LEVEL_LOG_CHANNEL = 1544834419544821780
REVIEW_CHANNEL = 1547726880134664273
STORE_TEAM_ROLE = 1547655214507622481
WHEEL_LOG_CHANNEL = 1547732226358120579
LOGS_CHANNEL = 1547668485340012575
LUCKY_STAR_ROLE = 1547731648982945792
VIP_ROLE = 1541619810230730762


# دالة مساعدة لإرسال اللوج العام
async def send_log(guild, title, description, color=discord.Color.blue()):
  channel = guild.get_channel(LOGS_CHANNEL)
  if channel:
    embed = discord.Embed(
        title=f"📋 {title}", description=description, color=color
    )
    embed.set_footer(text="Brevix System Logs")
    await channel.send(embed=embed)


@bot.event
async def on_ready():
  print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
  print("--- Bot is ready and running successfully! ---")


# ==================== لوحة المتجر (Store Panel) ====================
class StoreView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="عرض المنتجات",
      style=discord.ButtonStyle.primary,
      emoji="🛍️",
      custom_id="store_view_products",
  )
  async def view_products(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    embed = discord.Embed(
        title="🛒 متجر السيرفر - المنتجات المتاحة",
        description="هذه قائمة بجميع المنتجات المتوفرة حالياً:",
        color=discord.Color.gold(),
    )
    if not database["products"]:
      embed.add_field(
          name="تنبيه",
          value="لا توجد منتجات مضافة حالياً من قبل الإدارة.",
          inline=False,
      )
    else:
      for code, p in database["products"].items():
        prod_type = "رول (فوري)" if p["is_role"] else "منتج عادي (تيكت)"
        embed.add_field(
            name=f"{p['name']} (الكود: `{code}`)",
            value=(
                f"📝 **الوصف:** {p['desc']}\n💰 **السعر:** {p['price']} BX"
                f" Coins\n🏷️ **النوع:** {prod_type}"
            ),
            inline=False,
        )
    await interaction.response.send_message(embed=embed, ephemeral=True)

  @discord.ui.button(
      label="شراء منتج",
      style=discord.ButtonStyle.success,
      emoji="💳",
      custom_id="store_buy_product",
  )
  async def buy_product(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await interaction.response.send_modal(BuyModal())

  @discord.ui.button(
      label="قيم منتجاتنا",
      style=discord.ButtonStyle.secondary,
      emoji="⭐",
      custom_id="store_rate_product",
  )
  async def rate_product(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await interaction.response.send_modal(RateModal())


class BuyModal(discord.ui.Modal, title="شراء منتج من المتجر"):
  prod_code = discord.ui.TextInput(
      label="كود المنتج (6 أرقام)", placeholder="مثال: 482910", max_length=6
  )
  discount_code = discord.ui.TextInput(
      label="كود الخصم (اختياري)",
      placeholder="اكتب كود الخصم إن وجد",
      required=False,
  )

  async def on_submit(self, interaction: discord.Interaction):
    code = self.prod_code.value
    user_id = str(interaction.user.id)

    if code not in database["products"]:
      await interaction.response.send_message(
          "❌ كود المنتج غير صحيح!", ephemeral=True
      )
      return

    product = database["products"][code]
    user_data = database["users"].setdefault(
        user_id, {"coins": 1000, "inventory": [], "discount_codes": []}
    )

    if (
        product["is_role"]
        and product["role_id"] in [r.id for r in interaction.user.roles]
    ):
      await interaction.response.send_message(
          "⚠️ أنت تمتلك هذا المنتج بالفعل!", ephemeral=True
      )
      return

    price = product["price"]

    if user_data["coins"] < price:
      await interaction.response.send_message(
          "❌ رصيدك غير كافٍ لإتمام عملية الشراء!", ephemeral=True
      )
      return

    user_data["coins"] -= price
    user_data["inventory"].append(code)

    if product["is_role"]:
      role = interaction.guild.get_role(product["role_id"])
      if role:
        await interaction.user.add_roles(role)
      await interaction.response.send_message(
          f"✅ تم شراء المنتج `{product['name']}` بنجاح وإضافة الرول إليك!",
          ephemeral=True,
      )
    else:
      overwrites = {
          interaction.guild.default_role: discord.PermissionOverwrite(
              read_messages=False
          ),
          interaction.user: discord.PermissionOverwrite(
              read_messages=True, send_messages=True
          ),
          interaction.guild.get_role(STORE_TEAM_ROLE): (
              discord.PermissionOverwrite(
                  read_messages=True, send_messages=True
              )
          ),
      }
      channel = await interaction.guild.create_text_channel(
          f"ticket-{interaction.user.name}", overwrites=overwrites
      )
      await channel.send(
          f"مرحباً {interaction.user.mention}, لقد طلبت المنتج `{product['name']}`."
          f" فريق المتجر {interaction.guild.get_role(STORE_TEAM_ROLE).mention}"
          " سيقوم بخدمتك قريباً."
      )
      await interaction.response.send_message(
          f"✅ تم إرسال طلبك بنجاح! تم فتح تيكت لك هنا: {channel.mention}",
          ephemeral=True,
      )

    await send_log(
        interaction.guild,
        "عملية شراء جديدة",
        f"المستخدم {interaction.user.mention} اشترى المنتج `{product['name']}`"
        f" بالكود `{code}`.",
    )


class RateModal(discord.ui.Modal, title="تقييم منتج"):
  prod_name = discord.ui.TextInput(
      label="اسم أو كود المنتج", placeholder="اكتب اسم المنتج أو كوده"
  )
  rating = discord.ui.TextInput(
      label="التقييم (من 0 إلى 10)", placeholder="اكتب رقم من 0 لـ 10", max_length=2
  )
  reason = discord.ui.TextInput(
      label="سبب التقييم",
      style=discord.TextStyle.paragraph,
      placeholder="اكتب تفاصيل تقييمك...",
  )

  async def on_submit(self, interaction: discord.Interaction):
    channel = interaction.guild.get_channel(REVIEW_CHANNEL)
    if channel:
      embed = discord.Embed(
          title="⭐ تقييم منتج جديد",
          color=discord.Color.green(),
          timestamp=discord.utils.utcnow(),
      )
      embed.add_field(name="المستخدم", value=interaction.user.mention, inline=True)
      embed.add_field(
          name="المنتج", value=self.prod_name.value, inline=True
      )
      embed.add_field(
          name="التقييم", value=f"{self.rating.value}/10", inline=False
      )
      embed.add_field(name="السبب", value=self.reason.value, inline=False)
      await channel.send(embed=embed)
    await interaction.response.send_message(
        "✅ شكراً لك! تم إرسال تقييمك للإدارة بنجاح.", ephemeral=True
    )


# ==================== لوحة الأعضاء (User Panel) ====================
class UserView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="استعلام عن الرصيد",
      style=discord.ButtonStyle.primary,
      emoji="🪙",
      custom_id="user_balance",
  )
  async def check_balance(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    user_data = database["users"].setdefault(
        str(interaction.user.id),
        {"coins": 0, "discount_codes": [], "level": 0},
    )
    embed = discord.Embed(
        title="💰 رصيدك ومعلوماتك", color=discord.Color.blurple()
    )
    embed.add_field(
        name="العملات الحالية", value=f"{user_data['coins']} BX Coins 🪙", inline=False
    )
    embed.add_field(
        name="أكواد الخصم الخاصة بك",
        value=(
            ", ".join(user_data["discount_codes"])
            if user_data["discount_codes"]
            else "لا توجد أكواد حالياً"
        ),
        inline=False,
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)

  @discord.ui.button(
      label="تحويل عملات",
      style=discord.ButtonStyle.success,
      emoji="💸",
      custom_id="user_transfer",
  )
  async def transfer_coins(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    await interaction.response.send_modal(TransferModal())

  @discord.ui.button(
      label="المستوى والتفاعل",
      style=discord.ButtonStyle.secondary,
      emoji="📊",
      custom_id="user_level_stats",
  )
  async def level_stats(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    user_data = database["users"].setdefault(
        str(interaction.user.id),
        {"level": 0, "messages": 0, "voice_minutes": 0},
    )
    embed = discord.Embed(title="📊 إحصائيات المستوى والتفاعل", color=discord.Color.teal())
    embed.add_field(name="المستوى الحالي (Level)", value=str(user_data["level"]), inline=True)
    embed.add_field(name="عدد الرسائل", value=str(user_data["messages"]), inline=True)
    embed.add_field(name="الدقائق الصوتية", value=str(user_data["voice_minutes"]), inline=True)
    await interaction.response.send_message(embed=embed, ephemeral=True)

  @discord.ui.button(
      label="عجلة الحظ",
      style=discord.ButtonStyle.danger,
      emoji="🎡",
      custom_id="user_lucky_wheel",
  )
  async def lucky_wheel(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    user_id = str(interaction.user.id)
    user_data = database["users"].setdefault(
        user_id, {"coins": 1000, "discount_codes": []}
    )

    reward_type = random.choices(
        ["coins", "discount", "role", "spin"], weights=[60, 30, 5, 5]
    )[0]
    result_text = ""

    if reward_type == "coins":
      won_coins = random.choice([10, 20, 30, 50])
      user_data["coins"] += won_coins
      result_text = f"ربحت {won_coins} BX Coins 🪙!"
    elif reward_type == "discount":
      d_code = f"WHEEL-{random.randint(1000, 9999)}"
      user_data["discount_codes"].append(d_code)
      result_text = f"ربحت كود خصم حصري الخاص بك: `{d_code}`"
    elif reward_type == "role":
      role = interaction.guild.get_role(VIP_ROLE)
      if role:
        if role in interaction.user.roles:
          user_data["coins"] += 100
          result_text = "ربحت رول VIP ولكنها معك بالفعل، فتم إضافة 100 عملة بدلاً منها!"
        else:
          await interaction.user.add_roles(role)
          result_text = "ربحت رول VIP وتم إضافتها إليك فوراً!"
    else:
      result_text = "ربحت لفة مجانية إضافية!"

    await interaction.response.send_message(
        f"🎡 نتيجة عجلة الحظ: {result_text}", ephemeral=True
    )

    wheel_log_ch = interaction.guild.get_channel(WHEEL_LOG_CHANNEL)
    if wheel_log_ch:
      await wheel_log_ch.send(
          f"🎡 المستخدم {interaction.user.mention} قام بلف عجلة الحظ والنتيجة:"
          f" {result_text}"
      )


class TransferModal(discord.ui.Modal, title="تحويل عملات لصديق"):
  target_id = discord.ui.TextInput(
      label="آي دي الشخص (User ID)", placeholder="اكتب آي دي صديقك هنا"
  )
  amount = discord.ui.TextInput(
      label="المبلغ المراد تحويله", placeholder="مثال: 100"
  )

  async def on_submit(self, interaction: discord.Interaction):
    try:
      amt = int(self.amount.value)
    except ValueError:
      await interaction.response.send_message(
          "❌ برجاء إدخال رقم صحيح للمبلغ!", ephemeral=True
      )
      return

    if amt <= 0:
      await interaction.response.send_message(
          "❌ المبلغ غير صالح للتحويل!", ephemeral=True
      )
      return

    fee = int(amt * 0.1)
    net_amount = amt - fee

    sender_id = str(interaction.user.id)
    sender_data = database["users"].setdefault(sender_id, {"coins": 1000})

    if sender_data["coins"] < amt:
      await interaction.response.send_message(
          "❌ رصيدك لا يكفي لإتمام التحويل مع رسوم الخدمة!", ephemeral=True
      )
      return

    sender_data["coins"] -= amt
    receiver_id = self.target_id.value
    receiver_data = database["users"].setdefault(receiver_id, {"coins": 0})
    receiver_data["coins"] += net_amount

    await interaction.response.send_message(
        f"✅ تم تحويل {net_amount} BX Coins بنجاح! (تم خصم {fee} عملة كرسوم"
        " تحويل).",
        ephemeral=True,
    )


# ==================== لوحة الإدارة (Admin Panel) ====================
class AdminView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="إضافة منتج جديد",
      style=discord.ButtonStyle.success,
      emoji="➕",
      custom_id="admin_add_product",
  )
  async def add_product(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ هذا الزر مخصص للإدارة فقط!", ephemeral=True
      )
      return
    await interaction.response.send_modal(AddProductModal())

  @discord.ui.button(
      label="تعديل عملات أو ليفل",
      style=discord.ButtonStyle.primary,
      emoji="⚙️",
      custom_id="admin_edit_user",
  )
  async def edit_user(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ هذا الزر مخصص للإدارة فقط!", ephemeral=True
      )
      return
    await interaction.response.send_modal(EditUserModal())

  @discord.ui.button(
      label="إنشاء كود خصم",
      style=discord.ButtonStyle.secondary,
      emoji="🏷️",
      custom_id="admin_create_discount",
  )
  async def create_discount(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ هذا الزر مخصص للإدارة فقط!", ephemeral=True
      )
      return
    await interaction.response.send_modal(DiscountModal())


class AddProductModal(discord.ui.Modal, title="إضافة منتج جديد للمتجر"):
  prod_name = discord.ui.TextInput(
      label="اسم المنتج", placeholder="مثال: رول فيسبوك / خدمة تفعيل"
  )
  prod_desc = discord.ui.TextInput(
      label="وصف المنتج",
      style=discord.TextStyle.paragraph,
      placeholder="اكتب تفاصيل المنتج...",
  )
  prod_price = discord.ui.TextInput(
      label="السعر (بالعملات)", placeholder="مثال: 500"
  )
  is_role = discord.ui.TextInput(
      label="هل هو رول فوري؟ (نعم / لا)", placeholder="اكتب نعم أو لا", max_length=3
  )
  role_id = discord.ui.TextInput(
      label="آي دي الرول (لو نعم، اكتبه وإلا اتركها)",
      required=False,
      placeholder="1541620051...",
  )

  async def on_submit(self, interaction: discord.Interaction):
    try:
      price = int(self.prod_price.value)
    except ValueError:
      await interaction.response.send_message(
          "❌ السعر يجب أن يكون رقماً صحيحاً!", ephemeral=True
      )
      return

    prod_code = str(random.randint(100000, 999999))
    while prod_code in database["products"]:
      prod_code = str(random.randint(100000, 999999))

    is_r = True if self.is_role.value.strip().lower() in ["نعم", "yes", "y"] else False
    r_id = int(self.role_id.value) if self.role_id.value.isdigit() else None

    database["products"][prod_code] = {
        "name": self.prod_name.value,
        "desc": self.prod_desc.value,
        "price": price,
        "is_role": is_r,
        "role_id": r_id,
    }

    await interaction.response.send_message(
        f"✅ تم إضافة المنتج بنجاح!\n📌 **كود المنتج التلقائي:** `{prod_code}`",
        ephemeral=True,
    )
    await send_log(
        interaction.guild,
        "إضافة منتج جديد",
        f"الإداري {interaction.user.mention} أضاف المنتج `{self.prod_name.value}`"
        f" بكود تلقائي `{prod_code}`.",
    )


class EditUserModal(discord.ui.Modal, title="تعديل رصيد أو ليفل عضو"):
  user_id = discord.ui.TextInput(
      label="آي دي العضو (User ID)", placeholder="اكتب الآي دي هنا"
  )
  coins_change = discord.ui.TextInput(
      label="تعديل العملات (+ أو -)",
      placeholder="مثال: +100 أو -50",
      required=False,
  )
  level_change = discord.ui.TextInput(
      label="تعديل الليفل (رقم جديد)", placeholder="مثال: 5", required=False
  )

  async def on_submit(self, interaction: discord.Interaction):
    u_id = self.user_id.value.strip()
    u_data = database["users"].setdefault(
        u_id, {"coins": 1000, "level": 0, "messages": 0, "voice_minutes": 0}
    )

    changes_text = []
    if self.coins_change.value:
      try:
        val = int(self.coins_change.value)
        u_data["coins"] += val
        changes_text.append(f"العملات: {val:+d}")
      except ValueError:
        pass

    if self.level_change.value:
      try:
        lvl = int(self.level_change.value)
        u_data["level"] = lvl
        changes_text.append(f"المستوى أصبح: {lvl}")
      except ValueError:
        pass

    await interaction.response.send_message(
        f"✅ تم تعديل بيانات العضو `{u_id}` بنجاح: {', '.join(changes_text)}",
        ephemeral=True,
    )


class DiscountModal(discord.ui.Modal, title="إنشاء كود خصم جديد"):
  disc_code = discord.ui.TextInput(
      label="كود الخصم", placeholder="مثال: SALE50 أو BREVIX2026"
  )
  discount_val = discord.ui.TextInput(
      label="نسبة أو قيمة الخصم", placeholder="مثال: 20 (يعني 20%)"
  )

  async def on_submit(self, interaction: discord.Interaction):
    code = self.disc_code.value.strip()
    database["admin_codes"][code] = {"discount": self.discount_val.value}
    await interaction.response.send_message(
        f"✅ تم إنشاء كود الخصم `{code}` بنسبة خصم `{self.discount_val.value}%` بنجاح!",
        ephemeral=True,
    )


# ==================== الأوامر لإرسال اللوحات ====================
@bot.command(name="store")
async def send_store_panel(ctx):
  if not ctx.author.guild_permissions.administrator:
    return
  embed = discord.Embed(
      title="🛍️ لوحة متجر السيرفر الرسمي",
      description=(
          "استعرض منتجاتنا المميزة، اشتري ما تحتاجه فوراً، أو شاركنا برأيك"
          " وتقييمك لخدماتنا."
      ),
      color=discord.Color.gold(),
  )
  await ctx.send(embed=embed, view=StoreView())


@bot.command(name="panel")
async def send_user_panel(ctx):
  if not ctx.author.guild_permissions.administrator:
    return
  embed = discord.Embed(
      title="👤 لوحة خدمات الأعضاء الشخصية",
      description=(
          "تحكم برصيدك، تفاعل مع عجلة الحظ، تابع ليفلك، وحول عملاتك بكل سهولة."
      ),
      color=discord.Color.blurple(),
  )
  await ctx.send(embed=embed, view=UserView())


@bot.command(name="apanel")
async def send_admin_panel(ctx):
  if not ctx.author.guild_permissions.administrator:
    return
  embed = discord.Embed(
      title="🛠️ لوحة تحكم الإدارة المركزية",
      description=(
          "تحكم كاملاً في منتجات المتجر، تعديل رصيد وليفل الأعضاء، وإنشاء"
          " تخفيضات السيرفر."
      ),
      color=discord.Color.red(),
  )
  await ctx.send(embed=embed, view=AdminView())


# تشغيل البوت بأمان باستخدام التوكن المخفي
bot.run(os.getenv("DISCORD_TOKEN"))
