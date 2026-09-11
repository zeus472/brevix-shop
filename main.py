import datetime
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
    "users": {},  # {user_id: {"coins": 1000, "level": 0, "messages": 0, "voice_minutes": 0, "inventory": [], "discount_codes": {}, "daily_wheels": 3, "last_wheel_date": ""}}
    "products": {},  # {prod_code: {"name": "", "desc": "", "price": 0, "is_role": True, "role_id": None}}
    "levels": {},
    "admin_codes": {},  # {code: {"discount": value}}
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
STORE_BANNER_URL = "https://cdn.discordapp.com/attachments/1545435584749903882/1548020817277751377/1789145923944.png?ex=6aa58a3b&is=6aa438bb&hm=756e27bc34d552ee22628d1b0f5306b22d118fb35eb2c8ef817260865c0d60a6&"


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
    embed.set_image(url=STORE_BANNER_URL)
    if not database["products"]:
      embed.add_field(
          name="تنبيه",
          value="لا توجد منتجات مضافة حالياً من قبل الإدارة.",
          inline=False,
      )
    else:
      for code, p in database["products"].items():
        prod_type = "رول فوري (سحب آلي)" if p["is_role"] else "منتج عادي (فتح تيكت)"
        embed.add_field(
            name=f"📦 {p['name']} | (الكود: `{code}`)",
            value=(
                f"📝 **الوصف:** {p['desc']}\n💰 **السعر الأساسي:** {p['price']}"
                f" BX Coins\n🏷️ **نوع المنتج:** {prod_type}"
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
      placeholder="اكتب كود الخصم الخاص بك إن وجدت",
      required=False,
  )

  async def on_submit(self, interaction: discord.Interaction):
    code = self.prod_code.value.strip()
    d_code = self.discount_code.value.strip()
    user_id = str(interaction.user.id)

    if code not in database["products"]:
      await interaction.response.send_message(
          "❌ كود المنتج غير صحيح!", ephemeral=True
      )
      return

    product = database["products"][code]
    user_data = database["users"].setdefault(
        user_id,
        {
            "coins": 1000,
            "inventory": [],
            "discount_codes": {},
            "daily_wheels": 3,
        },
    )

    if (
        product["is_role"]
        and product["role_id"] in [r.id for r in interaction.user.roles]
    ):
      await interaction.response.send_message(
          "⚠️ أنت تمتلك هذا المنتج والرول بالفعل!", ephemeral=True
      )
      return

    final_price = product["price"]
    discount_applied_text = "بدون خصم"

    # التحقق من كود الخصم إذا تم إدخاله
    if d_code:
      user_discounts = user_data.get("discount_codes", {})
      if d_code in user_discounts:
        discount_percent = user_discounts[d_code]
        # خصم المبلغ بنسبة الخصم
        discount_amount = int(final_price * (discount_percent / 100))
        final_price = max(0, final_price - discount_amount)
        discount_applied_text = f"خصم {discount_percent}% (وفرت {discount_amount} عملة)"
        # مسح الكود لأنه يستخدم مرة واحدة فقط
        del user_discounts[d_code]
      elif d_code in database["admin_codes"]:
        discount_percent = database["admin_codes"][d_code]["discount"]
        discount_amount = int(final_price * (discount_percent / 100))
        final_price = max(0, final_price - discount_amount)
        discount_applied_text = f"خصم إداري {discount_percent}%"
      else:
        await interaction.response.send_message(
            "❌ كود الخصم غير صالح، أو انتهت صلاحيته، أو غير مخصص لك!",
            ephemeral=True,
        )
        return

    if user_data["coins"] < final_price:
      await interaction.response.send_message(
          f"❌ رصيدك غير كافٍ! السعر المطلوب بعد الخصم هو {final_price} BX"
          f" Coins.",
          ephemeral=True,
      )
      return

    user_data["coins"] -= final_price
    user_data["inventory"].append(code)

    if product["is_role"] and product.get("role_id"):
      role = interaction.guild.get_role(product["role_id"])
      if role:
        await interaction.user.add_roles(role)
      await interaction.response.send_message(
          f"✅ تم شراء المنتج `{product['name']}` بنجاح بسعر `{final_price}`"
          f" ({discount_applied_text}) وإضافة الرول إليك!",
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
          f"مرحباً {interaction.user.mention}, لقد طلبت المنتج `{product['name']}`"
          f" بسعر `{final_price}` ({discount_applied_text}). فريق المتجر"
          f" {interaction.guild.get_role(STORE_TEAM_ROLE).mention} سيقوم بخدمتك"
          " قريباً."
      )
      await interaction.response.send_message(
          f"✅ تم إرسال طلبك بنجاح! تم فتح تيكت لك هنا: {channel.mention}",
          ephemeral=True,
      )

    await send_log(
        interaction.guild,
        "عملية شراء جديدة",
        f"المستخدم {interaction.user.mention} اشترى المنتج `{product['name']}`"
        f" بالكود `{code}` بسعر `{final_price}` بتفاصيل: {discount_applied_text}.",
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
      embed.set_thumbnail(url=interaction.user.display_avatar.url)
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
        {"coins": 1000, "discount_codes": {}, "level": 0},
    )
    discounts = user_data.get("discount_codes", {})
    disc_list = (
        "\n".join([f"• `{code}` (خصم {val}%)" for code, val in discounts.items()])
        if discounts
        else "لا توجد أكواد خصم نشطة حالياً"
    )

    embed = discord.Embed(
        title="💰 رصيدك ومعلوماتك الشخصية", color=discord.Color.blurple()
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(
        name="العملات الحالية",
        value=f"🪙 **{user_data['coins']}** BX Coins",
        inline=False,
    )
    embed.add_field(
        name="🏷️ أكواد الخصم الخاصة بك (صالحة للاستخدام مرة واحدة)",
        value=disc_list,
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
    embed = discord.Embed(
        title="📊 إحصائيات المستوى والتفاعل الشخصي", color=discord.Color.teal()
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(
        name="المستوى الحالي (Level)",
        value=f"⭐ Level {user_data['level']}",
        inline=True,
    )
    embed.add_field(
        name="عدد الرسائل", value=f"💬 {user_data['messages']} رسالة", inline=True
    )
    embed.add_field(
        name="الدقائق الصوتية",
        value=f"🎙️ {user_data['voice_minutes']} دقيقة",
        inline=True,
    )
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
    # التحقق من تجديد اللفات اليومية
    user_id = str(interaction.user.id)
    user_data = database["users"].setdefault(
        user_id,
        {
            "coins": 1000,
            "discount_codes": {},
            "daily_wheels": 3,
            "last_wheel_date": "",
        },
    )

    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if user_data.get("last_wheel_date") != today_str:
      user_data["daily_wheels"] = 3
      user_data["last_wheel_date"] = today_str

    embed = discord.Embed(
        title="🎡 عجلة الحظ الكبرى - Brevix Wheel",
        description=(
            f"مرحباً بك يا {interaction.user.mention} في عجلة الحظ!\nلديك"
            f" **{user_data['daily_wheels']}** لفات مجانية متبقية لليوم.\n\nاختر"
            " طريقة اللف المناسبة لك من الأزرار بالأسفل:"
        ),
        color=discord.Color.red(),
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    await interaction.response.send_message(
        embed=embed, view=WheelButtonsView(), ephemeral=True
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

    if amt <= 10:
      await interaction.response.send_message(
          "❌ المبلغ صغير جداً ولا يغطي رسوم التحويل!", ephemeral=True
      )
      return

    fee = int(amt * 0.1)  # 10% رسوم تحويل
    net_amount = amt - fee

    sender_id = str(interaction.user.id)
    sender_data = database["users"].setdefault(
        sender_id, {"coins": 1000, "discount_codes": {}, "daily_wheels": 3}
    )

    if sender_data["coins"] < amt:
      await interaction.response.send_message(
          "❌ رصيدك لا يكفي لإتمام التحويل مع رسوم الخدمة (10%)!", ephemeral=True
      )
      return

    receiver_id = self.target_id.value.strip()
    try:
      receiver_member = await interaction.guild.fetch_member(int(receiver_id))
    except Exception:
      receiver_member = None

    if not receiver_member:
      await interaction.response.send_message(
          "❌ لم يتم العثور على هذا المستخدم في السيرفر! تأكد من الآي دي.",
          ephemeral=True,
      )
      return

    if receiver_id == sender_id:
      await interaction.response.send_message(
          "❌ لا يمكنك تحويل عملات لنفسك!", ephemeral=True
      )
      return

    sender_data["coins"] -= amt
    receiver_data = database["users"].setdefault(
        receiver_id, {"coins": 1000, "discount_codes": {}, "daily_wheels": 3}
    )
    receiver_data["coins"] += net_amount

    now_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # رسالة مؤكدة ومنظمة بشكل احترافي للعضو
    embed = discord.Embed(
        title="💸 تفاصيل عملية تحويل ناجحة",
        color=discord.Color.green(),
        timestamp=discord.utils.utcnow(),
    )
    embed.set_thumbnail(url=interaction.user.display_avatar.url)
    embed.add_field(
        name="👤 المُرسِل",
        value=f"{interaction.user.mention} (`{interaction.user.name}`)",
        inline=False,
    )
    embed.add_field(
        name="📥 المُستلم",
        value=f"{receiver_member.mention} (`{receiver_member.name}`)",
        inline=False,
    )
    embed.add_field(
        name="💰 المبلغ المحول", value=f"{amt} BX Coins", inline=True
    )
    embed.add_field(
        name="📉 رسوم التحويل (10%)", value=f"{fee} BX Coins", inline=True
    )
    embed.add_field(
        name="✅ المبلغ المستلم صافي", value=f"{net_amount} BX Coins", inline=False
    )
    embed.add_field(name="🕒 تاريخ التوقيت", value=now_time, inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


# ==================== نظام عجلة الحظ (Wheel Views & Logic) ====================
def spin_single_reward(user, user_id):
  reward_type = random.choices(
      ["coins", "discount", "role", "spin"], weights=[65, 25, 5, 5]
  )[0]
  if reward_type == "coins":
    won_coins = random.choice([10, 20, 30, 50, 100])
    user["coins"] += won_coins
    return f"ربحت {won_coins} BX Coins 🪙", "عملات", won_coins
  elif reward_type == "discount":
    # كود خصم بنسبة تظهر في آخره (مثلاً 25 أو 50)
    disc_pct = random.choice([15, 25, 35, 50])
    d_code = f"WHEEL-{random.randint(100,999)}-{disc_pct}"
    user["discount_codes"][d_code] = disc_pct
    return f"ربحت كود خصم حصري بشفرة: `{d_code}` (بنسبة خصم {disc_pct}%)", "كود خصم", disc_pct
  elif reward_type == "role":
    role = user.guild.get_role(VIP_ROLE) if hasattr(user, "guild") else None
    return "ربحت رول VIP المميزة! 👑", "رول VIP", 0
  else:
    return "ربحت لفة مجانية إضافية! 🎡", "لفة مجانية", 0


class WheelButtonsView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="لفة مجانية (إن وجدت)",
      style=discord.ButtonStyle.primary,
      emoji="🎁",
      custom_id="wheel_free_spin",
  )
  async def free_spin(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    user_id = str(interaction.user.id)
    user_data = database["users"].setdefault(
        user_id, {"coins": 1000, "discount_codes": {}, "daily_wheels": 3}
    )

    if user_data["daily_wheels"] <= 0:
      await interaction.response.send_message(
          "❌ لقد استنفدت جميع لفاتك المجانية اليومية! يمكنك استخدام اللفات"
          " المدفوعة بالكوينز أدناه.",
          ephemeral=True,
      )
      return

    user_data["daily_wheels"] -= 1
    res_text, r_type, r_val = spin_single_reward(
        database["users"][user_id], user_id
    )

    await interaction.response.send_message(
        f"🎡 **نتيجة عجلة الحظ (المجانية):**\n{res_text}", ephemeral=True
    )

    # إرسال لوج عجلة الحظ الاحترافي
    wheel_ch = interaction.guild.get_channel(WHEEL_LOG_CHANNEL)
    if wheel_ch:
      embed = discord.Embed(
          title="🎡 سجل عجلة الحظ - لفة مجانية",
          color=discord.Color.gold(),
          timestamp=discord.utils.utcnow(),
      )
      embed.set_thumbnail(url=interaction.user.display_avatar.url)
      embed.add_field(
          name="المستخدم", value=interaction.user.mention, inline=True
      )
      embed.add_field(name="نوع اللفة", value="مجانية 🎁", inline=True)
      embed.add_field(name="النتيجة", value=res_text, inline=False)
      await wheel_ch.send(embed=embed)

  @discord.ui.button(
      label="لفة واحدة (200 كوينز)",
      style=discord.ButtonStyle.success,
      emoji="🪙",
      custom_id="wheel_paid_spin",
  )
  async def paid_spin(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    user_id = str(interaction.user.id)
    user_data = database["users"].setdefault(
        user_id, {"coins": 1000, "discount_codes": {}}
    )

    if user_data["coins"] < 200:
      await interaction.response.send_message(
          "❌ رصيدك لا يكفي! تحتاج إلى 200 BX Coins لعمل هذه اللفة.",
          ephemeral=True,
      )
      return

    user_data["coins"] -= 200
    res_text, r_type, r_val = spin_single_reward(user_data, user_id)

    await interaction.response.send_message(
        f"🎡 **نتيجة عجلة الحظ (مدفوعة - 200 كوينز):**\n{res_text}",
        ephemeral=True,
    )

    wheel_ch = interaction.guild.get_channel(WHEEL_LOG_CHANNEL)
    if wheel_ch:
      embed = discord.Embed(
          title="🎡 سجل عجلة الحظ - لفة مدفوعة",
          color=discord.Color.green(),
          timestamp=discord.utils.utcnow(),
      )
      embed.set_thumbnail(url=interaction.user.display_avatar.url)
      embed.add_field(
          name="المستخدم", value=interaction.user.mention, inline=True
      )
      embed.add_field(
          name="نوع اللفة", value="مدفوعة مفردة (200 كوينز)", inline=True
      )
      embed.add_field(name="النتيجة", value=res_text, inline=False)
      await wheel_ch.send(embed=embed)

  @discord.ui.button(
      label="10 لفات دفعة واحدة (1500 كوينز + هدية 11 إضافية)",
      style=discord.ButtonStyle.danger,
      emoji="🔥",
      custom_id="wheel_10x_spin",
  )
  async def spin_10x(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    user_id = str(interaction.user.id)
    user_data = database["users"].setdefault(
        user_id, {"coins": 2000, "discount_codes": {}}
    )

    if user_data["coins"] < 1500:
      await interaction.response.send_message(
          "❌ رصيدك لا يكفي! تحتاج إلى 1500 BX Coins لعمل الـ 10 لفات.",
          ephemeral=True,
      )
      return

    user_data["coins"] -= 1500
    results_list = []

    # تنفيذ 10 لفات طبيعية
    for i in range(10):
      txt, _, _ = spin_single_reward(user_data, user_id)
      results_list.append(f"• اللفة {i+1}: {txt}")

    # الهدية رقم 11 الإضافية النادرة (أقل من 10% نسبة - هدية قيمة كبرى)
    extra_coins = random.choice([300, 500, 1000])
    user_data["coins"] += extra_coins
    bonus_text = (
        f"🎁 **الهدية الـ 11 الإضافية النادرة:** ربحت مكافأة كبرى بقيمة"
        f" `{extra_coins}` BX Coins!"
    )
    results_list.append(bonus_text)

    full_response = "\n".join(results_list)
    if len(full_response) > 1900:
      full_response = full_response[:1900] + "\n...(تم اختصار النص لطوله)"

    await interaction.response.send_message(
        f"🎡 **نتائج الـ 10 لفات + الهدية الكبرى الـ 11:**\n{full_response}",
        ephemeral=True,
    )

    wheel_ch = interaction.guild.get_channel(WHEEL_LOG_CHANNEL)
    if wheel_ch:
      embed = discord.Embed(
          title="🎡 سجل عجلة الحظ - 10 لفات + الهدية الخارقة الـ 11",
          color=discord.Color.purple(),
          timestamp=discord.utils.utcnow(),
      )
      embed.set_thumbnail(url=interaction.user.display_avatar.url)
      embed.add_field(
          name="المستخدم", value=interaction.user.mention, inline=True
      )
      embed.add_field(
          name="نوع اللفة", value="10 لفات مدفوعة (1500 كوينز)", inline=True
      )
      embed.add_field(
          name="تفاصيل الجوائز والهدية الـ 11", value=full_response, inline=False
      )
      await wheel_ch.send(embed=embed)


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
      label="نسبة أو قيمة الخصم (رقم فقط)", placeholder="مثال: 20 (يعني 20%)"
  )

  async def on_submit(self, interaction: discord.Interaction):
    code = self.disc_code.value.strip()
    try:
      d_val = int(self.discount_val.value.strip())
    except ValueError:
      await interaction.response.send_message(
          "❌ نسبة الخصم يجب أن تكون رقماً صحيحاً!", ephemeral=True
      )
      return

    database["admin_codes"][code] = {"discount": d_val}
    await interaction.response.send_message(
        f"✅ تم إنشاء كود الخصم العام `{code}` بنسبة خصم `{d_val}%` بنجاح!",
        ephemeral=True,
    )


# ==================== الأوامر لإرسال اللوحات ====================
@bot.command(name="store")
async def send_store_panel(ctx):
  if not ctx.author.guild_permissions.administrator:
    return
  embed = discord.Embed(
      title="🛍️  متجر بريفكس الرسمي | Brevix Official Store",
      description=(
          "استعرض منتجاتنا المميزة، اشتري ما تحتاجه فوراً، أو شاركنا برأيك"
          " وتقييمك لخدمتنا."
      ),
      color=discord.Color.gold(),
  )
  embed.set_image(url=STORE_BANNER_URL)
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
