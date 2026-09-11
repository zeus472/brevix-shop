import datetime
import os
import random
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

# قاعدة بيانات متكاملة في الذاكرة مع حماية الأرصدة
database = {
    # {user_id: {"coins": 1000, "level": 0, "messages": 0, "voice_minutes": 0, "inventory": [], "discount_codes": {}, "daily_wheels": 3, "last_wheel_date": ""}}
    "users": {},
    # {prod_code: {"name": "", "desc": "", "price": 0, "allow_discount": True, "is_role": True, "role_id": None, "duration_days": 0}} (duration_days: 0 means permanent)
    "products": {},
    # {level_num: {"req_msg": 0, "req_voice": 0, "reward": 0}}
    "levels": {},
    # {code: {"discount": 0, "expiry_date": None, "max_uses": None, "uses": 0, "role_id": None}}
    "admin_codes": {},
    # تتبع الأدوار المؤقتة: {[user_id, role_id]: expire_timestamp}
    "temp_roles": {},
}

# الآي ديوهات الثابتة المطلوبة (لا يتم تغييرها نهائياً)
DEFAULT_ROLE_ID = 1541620051033985085
LEVEL_LOG_CHANNEL = 1544834419544821780
REVIEW_CHANNEL = 1547726880134664273
STORE_TEAM_ROLE = 1547655214507622481
WHEEL_LOG_CHANNEL = 1547732226358120579
LOGS_CHANNEL = 1547668485340012575
LUCKY_STAR_ROLE = 1547731648982945792
VIP_ROLE = 1541619810230730762
STORE_BANNER_URL = "https://cdn.discordapp.com/attachments/1545435584749903882/1548020817277751377/1789145923944.png?ex=6aa58a3b&is=6aa438bb&hm=756e27bc34d552ee22628d1b0f5306b22d118fb35eb2c8ef817260865c0d60a6&"


# دالة مساعدة لإرسال اللوج العام بأمان
async def send_log(guild, title, description, color=discord.Color.blue()):
  channel = guild.get_channel(LOGS_CHANNEL)
  if channel:
    try:
      embed = discord.Embed(
          title=f"📋 {title}", description=description, color=color
      )
      embed.set_footer(text="Brevix Secure System Logs")
      await channel.send(embed=embed)
    except Exception:
      pass


@bot.event
async def on_ready():
  print(f"Logged in as {bot.user.name} (ID: {bot.user.id})")
  print("--- Brevix Secure Bot is ready and running successfully! ---")
  if not check_temp_roles.is_running():
    check_temp_roles.start()


# ==================== مهمة فحص الأدوار المؤقتة (Background Task) ====================
@tasks.loop(minutes=1)
async def check_temp_roles():
  now = datetime.datetime.now()
  expired_entries = []
  for key, expire_time in list(database["temp_roles"].items()):
    if now >= expire_time:
      expired_entries.append(key)

  for user_id_str, role_id in expired_entries:
    for guild in bot.guilds:
      member = guild.get_member(int(user_id_str))
      if member:
        role = guild.get_role(role_id)
        if role and role in member.roles:
          try:
            await member.remove_roles(role)
            await send_log(
                guild,
                "انتهاء صلاحية منتج دور",
                f"تم سحب الرول المؤقت {role.mention} من العضو"
                f" {member.mention} لانتهاء مدة الصلاحية.",
                discord.Color.orange(),
            )
          except Exception:
            pass
    database["temp_roles"].pop((user_id_str, role_id), None)


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
        title="🛒 متجر بريفكس الرسمي - المنتجات المتاحة",
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
        prod_type = (
            "رول فوري (سحب آلي)" if p["is_role"] else "منتج عادي (فتح تيكت)"
        )
        disc_status = (
            "مسموح بالخصم ✅" if p.get("allow_discount", True) else "غير مسموح ❌"
        )
        duration_text = (
            "دائم ♾️"
            if p["duration_days"] == 0
            else f"مؤقت ({p['duration_days']} يوم)"
        )
        embed.add_field(
            name=f"📦 {p['name']} | (الكود: `{code}`)",
            value=(
                f"📝 **الوصف:** {p['desc']}\n💰 **السعر:** {p['price']} BX"
                f" Coins\n🏷️ **النوع:** {prod_type}\n⏳ **الصلاحية:**"
                f" {duration_text}\n🏷️ **الخصومات:** {disc_status}"
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
      placeholder="اكتب كود الخصم الخاص بك إن وجد",
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
            "level": 0,
            "messages": 0,
            "voice_minutes": 0,
        },
    )

    # حماية ضد إعادة شراء الرول إذا كان يمتلكها بالفعل
    if (
        product["is_role"]
        and product.get("role_id")
        and product["role_id"] in [r.id for r in interaction.user.roles]
    ):
      await interaction.response.send_message(
          "⚠️ أنت تمتلك هذا الرول بالفعل على حسابك!", ephemeral=True
      )
      return

    final_price = product["price"]
    discount_applied_text = "بدون خصم"

    # معالجة كود الخصم بأمان وتأكيد الشروط
    if d_code:
      if not product.get("allow_discount", True):
        await interaction.response.send_message(
            "❌ هذا المنتج غير مسموح بتطبيق أكواد الخصم عليه!", ephemeral=True
        )
        return

      valid_code_found = False
      discount_percent = 0

      # 1. فحص الأكواد الخاصة بالعضو
      user_discounts = user_data.get("discount_codes", {})
      if d_code in user_discounts:
        discount_percent = user_discounts[d_code]
        valid_code_found = True
        del user_discounts[d_code]  # استخدام لمرة واحدة وحذفه فورا

      # 2. فحص الأكواد الإدارية العامة أو الخاصة بالرول
      elif d_code in database["admin_codes"]:
        ac_data = database["admin_codes"][d_code]
        # تحقق من الصلاحية بالأيام
        if ac_data["expiry_date"] and datetime.datetime.now() > ac_data[
            "expiry_date"
        ]:
          await interaction.response.send_message(
              "❌ عذراً، انتهت صلاحية كود الخصم هذا!", ephemeral=True
          )
          return
        # تحقق من عدد الاستخدامات
        if (
            ac_data["max_uses"] is not None
            and ac_data["uses"] >= ac_data["max_uses"]
        ):
          await interaction.response.send_message(
              "❌ عذراً، تم استنفاد الحد الأقصى لاستخدام هذا الكود!",
              ephemeral=True,
          )
          return
        # تحقق من الرول المطلوبة للكود
        if ac_data["role_id"]:
          role_required = interaction.guild.get_role(ac_data["role_id"])
          if not role_required or role_required not in interaction.user.roles:
            await interaction.response.send_message(
                "❌ هذا الكود مخصص لأعضاء يحملون رول معينة لا تمتلكها!",
                ephemeral=True,
            )
            return

        discount_percent = ac_data["discount"]
        ac_data["uses"] += 1
        valid_code_found = True

      if valid_code_found:
        discount_amount = int(final_price * (discount_percent / 100))
        final_price = max(0, final_price - discount_amount)
        discount_applied_text = (
            f"خصم {discount_percent}% (وفرت {discount_amount} عملة)"
        )
      else:
        await interaction.response.send_message(
            "❌ كود الخصم غير صالح، انتهت صلاحيته، أو غير مخصص لك!",
            ephemeral=True,
        )
        return

    # فحص كفاية رصيد العضو بدقة تامة
    if user_data["coins"] < final_price:
      await interaction.response.send_message(
          f"❌ رصيدك غير كافٍ! السعر المطلوب بعد الخصم هو {final_price} BX"
          f" Coins (رصيدك الحالي: {user_data['coins']}).",
          ephemeral=True,
      )
      return

    # تنفيذ الخصم وتحديث المخزون
    user_data["coins"] -= final_price
    user_data["inventory"].append(code)

    if product["is_role"] and product.get("role_id"):
      role = interaction.guild.get_role(product["role_id"])
      if role:
        await interaction.user.add_roles(role)

      duration_msg = "دائم ♾️"
      if product["duration_days"] > 0:
        expire_time = datetime.datetime.now() + datetime.timedelta(
            days=product["duration_days"]
        )
        database["temp_roles"][(user_id, product["role_id"])] = expire_time
        duration_msg = f"مؤقت لمدة {product['duration_days']} يوم"

      await interaction.response.send_message(
          f"✅ تم شراء المنتج `{product['name']}` بنجاح بسعر `{final_price}`"
          f" ({discount_applied_text}) وإضافة الرول إليك ({duration_msg})!",
          ephemeral=True,
      )
    else:
      # فتح تيكت تواصل آمنة واحترافية
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
        "عملية شراء ناجحة ومؤمنة",
        f"المستخدم {interaction.user.mention} اشترى المنتج `{product['name']}`"
        f" (`{code}`) بسعر `{final_price}`. التفاصيل: {discount_applied_text}.",
        discord.Color.green(),
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
            f"مرحباً بك يا {interaction.user.mention} في عجلة الحظ الآمنة!\nلديك"
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

    embed = discord.Embed(
        title="💸 تفاصيل عملية تحويل ناجحة ومؤمنة",
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


# ==================== نظام عجلة الحظ الآمن (Wheel Views & Logic) ====================
def spin_single_reward(user, guild_obj):
  reward_type = random.choices(
      ["coins", "discount", "role", "spin"], weights=[65, 25, 5, 5]
  )[0]
  if reward_type == "coins":
    won_coins = random.choice([10, 20, 30, 50, 100])
    user["coins"] += won_coins
    return f"ربحت {won_coins} BX Coins 🪙", "عملات", won_coins
  elif reward_type == "discount":
    disc_pct = random.choice([15, 25, 35, 50])
    d_code = f"WHEEL-{random.randint(100,999)}-{disc_pct}"
    user["discount_codes"][d_code] = disc_pct
    return (
        f"ربحت كود خصم حصري بشفرة: `{d_code}` (بنسبة خصم {disc_pct}%)",
        "كود خصم",
        disc_pct,
    )
  elif reward_type == "role":
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

    # حماية تأمينية صارمة ضد الثغرات واللف بالمجان
    today_str = datetime.datetime.now().strftime("%Y-%m-%d")
    if user_data.get("last_wheel_date") != today_str:
      user_data["daily_wheels"] = 3
      user_data["last_wheel_date"] = today_str

    if user_data["daily_wheels"] <= 0:
      await interaction.response.send_message(
          "❌ لقد استنفدت جميع لفاتك المجانية اليومية! يمكنك استخدام اللفات"
          " المدفوعة بالكوينز أدناه.",
          ephemeral=True,
      )
      return

    user_data["daily_wheels"] -= 1
    res_text, r_type, r_val = spin_single_reward(user_data, interaction.guild)

    await interaction.response.send_message(
        f"🎡 **نتيجة عجلة الحظ (المجانية):**\n{res_text}", ephemeral=True
    )

    wheel_ch = interaction.guild.get_channel(WHEEL_LOG_CHANNEL)
    if wheel_ch:
      embed = discord.Embed(
          title="🎡 سجل عجلة الحظ - لفة مجانية آمنة",
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
    res_text, r_type, r_val = spin_single_reward(user_data, interaction.guild)

    await interaction.response.send_message(
        f"🎡 **نتيجة عجلة الحظ (مدفوعة - 200 كوينز):**\n{res_text}",
        ephemeral=True,
    )

    wheel_ch = interaction.guild.get_channel(WHEEL_LOG_CHANNEL)
    if wheel_ch:
      embed = discord.Embed(
          title="🎡 سجل عجلة الحظ - لفة مدفوعة آمنة",
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

    for i in range(10):
      txt, _, _ = spin_single_reward(user_data, interaction.guild)
      results_list.append(f"• اللفة {i+1}: {txt}")

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


# ==================== لوحة الإدارة الكاملة (Admin Panel - 7 Buttons) ====================
class AdminView(discord.ui.View):

  def __init__(self):
    super().__init__(timeout=None)

  @discord.ui.button(
      label="1. إضافة منتج",
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
      label="2. حذف منتج",
      style=discord.ButtonStyle.danger,
      emoji="🗑️",
      custom_id="admin_delete_product",
  )
  async def delete_product(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ هذا الزر مخصص للإدارة فقط!", ephemeral=True
      )
      return
    await interaction.response.send_modal(DeleteProductModal())

  @discord.ui.button(
      label="3. تعديل رصيد",
      style=discord.ButtonStyle.primary,
      emoji="🪙",
      custom_id="admin_edit_balance",
  )
  async def edit_balance(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ هذا الزر مخصص للإدارة فقط!", ephemeral=True
      )
      return
    await interaction.response.send_modal(EditBalanceModal())

  @discord.ui.button(
      label="4. تعديل الليفل",
      style=discord.ButtonStyle.secondary,
      emoji="⭐",
      custom_id="admin_edit_level",
  )
  async def edit_level(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ هذا الزر مخصص للإدارة فقط!", ephemeral=True
      )
      return
    await interaction.response.send_modal(EditLevelModal())

  @discord.ui.button(
      label="5. متطلبات الليفل",
      style=discord.ButtonStyle.primary,
      emoji="📊",
      custom_id="admin_level_reqs",
  )
  async def level_reqs(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ هذا الزر مخصص للإدارة فقط!", ephemeral=True
      )
      return
    await interaction.response.send_modal(LevelRequirementsModal())

  @discord.ui.button(
      label="6. أكواد الخصم",
      style=discord.ButtonStyle.success,
      emoji="🏷️",
      custom_id="admin_discount_mgmt",
  )
  async def discount_mgmt(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ هذا الزر مخصص للإدارة فقط!", ephemeral=True
      )
      return
    await interaction.response.send_modal(DiscountManagementModal())

  @discord.ui.button(
      label="7. استعلام عن لاعب",
      style=discord.ButtonStyle.secondary,
      emoji="🔍",
      custom_id="admin_inspect_user",
  )
  async def inspect_user(
      self, interaction: discord.Interaction, button: discord.ui.Button
  ):
    if not interaction.user.guild_permissions.administrator:
      await interaction.response.send_message(
          "❌ هذا الزر مخصص للإدارة فقط!", ephemeral=True
      )
      return
    await interaction.response.send_modal(InspectUserModal())


# Modals للوحة الإدارة (الأزرار الـ 7)
class AddProductModal(discord.ui.Modal, title="إضافة منتج جديد للمتجر"):
  prod_name = discord.ui.TextInput(
      label="اسم المنتج", placeholder="مثال: رول مميز / خدمة تفعيل"
  )
  prod_desc = discord.ui.TextInput(
      label="وصف المنتج",
      style=discord.TextStyle.paragraph,
      placeholder="اكتب تفاصيل المنتج...",
  )
  prod_price = discord.ui.TextInput(
      label="السعر (بالعملات)", placeholder="مثال: 500"
  )
  allow_disc = discord.ui.TextInput(
      label="السماح بالخصومات؟ (نعم / لا)", placeholder="نعم", max_length=3
  )
  is_role = discord.ui.TextInput(
      label="هل هو رول فوري؟ (نعم / لا)", placeholder="نعم", max_length=3
  )
  role_id = discord.ui.TextInput(
      label="آي دي الرول (أو فارغ لو تيكت)",
      required=False,
      placeholder="1541620051...",
  )
  duration_days = discord.ui.TextInput(
      label="الصلاحية بالأيام (0 = دائم)", placeholder="0 أو 7 أو 30", max_length=4
  )

  async def on_submit(self, interaction: discord.Interaction):
    try:
      price = int(self.prod_price.value.strip())
      duration = int(self.duration_days.value.strip())
    except ValueError:
      await interaction.response.send_message(
          "❌ السعر وعدد أيام الصلاحية يجب أن تكون أرقاماً صحيحة!",
          ephemeral=True,
      )
      return

    prod_code = str(random.randint(100000, 999999))
    while prod_code in database["products"]:
      prod_code = str(random.randint(100000, 999999))

    is_r = (
        True
        if self.is_role.value.strip().lower() in ["نعم", "yes", "y"]
        else False
    )
    allow_d = (
        False
        if self.allow_disc.value.strip().lower() in ["لا", "no", "n"]
        else True
    )
    r_id = (
        int(self.role_id.value.strip())
        if self.role_id.value.strip().isdigit()
        else None
    )

    database["products"][prod_code] = {
        "name": self.prod_name.value.strip(),
        "desc": self.prod_desc.value.strip(),
        "price": price,
        "allow_discount": allow_d,
        "is_role": is_r,
        "role_id": r_id,
        "duration_days": duration,
    }

    dur_text = "دائم ♾️" if duration == 0 else f"مؤقت ({duration} يوم)"
    await interaction.response.send_message(
        f"✅ تم إضافة المنتج بنجاح!\n📌 **كود المنتج:** `{prod_code}`\n⏳"
        f" **الصلاحية:** {dur_text}",
        ephemeral=True,
    )
    await send_log(
        interaction.guild,
        "إضافة منتج جديد",
        f"الإداري {interaction.user.mention} أضاف المنتج `{self.prod_name.value}`"
        f" بكود `{prod_code}` بصلاحية: {dur_text}.",
        discord.Color.green(),
    )


class DeleteProductModal(discord.ui.Modal, title="حذف منتج من المتجر"):
  prod_code = discord.ui.TextInput(
      label="كود المنتج المراد حذفه", placeholder="مثال: 482910", max_length=6
  )

  async def on_submit(self, interaction: discord.Interaction):
    code = self.prod_code.value.strip()
    if code in database["products"]:
      p_name = database["products"][code]["name"]
      del database["products"][code]
      await interaction.response.send_message(
          f"✅ تم حذف المنتج `{p_name}` (`{code}`) بنجاح من قاعدة البيانات.",
          ephemeral=True,
      )
      await send_log(
          interaction.guild,
          "حذف منتج",
          f"الإداري {interaction.user.mention} حذف المنتج `{p_name}` (`{code}`).",
          discord.Color.red(),
      )
    else:
      await interaction.response.send_message(
          "❌ كود المنتج غير موجود!", ephemeral=True
      )


class EditBalanceModal(discord.ui.Modal, title="تعديل رصيد عضو (إضافة / سحب)"):
  user_id = discord.ui.TextInput(
      label="آي دي العضو (User ID)", placeholder="اكتب الآي دي هنا"
  )
  coins_change = discord.ui.TextInput(
      label="العملات (+ للإضافة أو - للخصم)", placeholder="مثال: +100 أو -50"
  )

  async def on_submit(self, interaction: discord.Interaction):
    u_id = self.user_id.value.strip()
    u_data = database["users"].setdefault(
        u_id,
        {
            "coins": 1000,
            "level": 0,
            "messages": 0,
            "voice_minutes": 0,
            "discount_codes": {},
            "inventory": [],
        },
    )

    try:
      val = int(self.coins_change.value.strip())
      u_data["coins"] = max(0, u_data["coins"] + val)
    except ValueError:
      await interaction.response.send_message(
          "❌ برجاء إدخال رقم صحيح للعملات!", ephemeral=True
      )
      return

    await interaction.response.send_message(
        f"✅ تم تعديل رصيد العضو `{u_id}` بنجاح وأصبح رصيده: `{u_data['coins']}`"
        " BX Coins.",
        ephemeral=True,
    )
    await send_log(
        interaction.guild,
        "تعديل رصيد إداري",
        f"الإداري {interaction.user.mention} عدل رصيد العضو `<@{u_id}>` بقيمة"
        f" `{val:+d}`.",
        discord.Color.blue(),
    )


class EditLevelModal(discord.ui.Modal, title="تعديل مستوى (ليفل) عضو"):
  user_id = discord.ui.TextInput(
      label="آي دي العضو (User ID)", placeholder="اكتب الآي دي هنا"
  )
  new_level = discord.ui.TextInput(
      label="المستوى الجديد (رقم)", placeholder="مثال: 5"
  )

  async def on_submit(self, interaction: discord.Interaction):
    u_id = self.user_id.value.strip()
    try:
      lvl = int(self.new_level.value.strip())
    except ValueError:
      await interaction.response.send_message(
          "❌ المستوى يجب أن يكون رقماً صحيحاً!", ephemeral=True
      )
      return

    u_data = database["users"].setdefault(
        u_id,
        {
            "coins": 1000,
            "level": 0,
            "messages": 0,
            "voice_minutes": 0,
            "discount_codes": {},
            "inventory": [],
        },
    )
    u_data["level"] = lvl

    await interaction.response.send_message(
        f"✅ تم تحديث مستوى العضو `{u_id}` إلى المستوى `{lvl}` بنجاح.",
        ephemeral=True,
    )

    # إرسال رسالة تهنئة احترافية في روم الليفل الثابت
    try:
      member = await interaction.guild.fetch_member(int(u_id))
    except Exception:
      member = None

    lvl_channel = interaction.guild.get_channel(LEVEL_LOG_CHANNEL)
    if lvl_channel and member:
      embed = discord.Embed(
          title="🎉 مبروك الترقية الجديدة!",
          description=(
              f"نبارك للعضو {member.mention} وصوله الإستثنائي إلى **Level {lvl}**"
              " بقرار إداري!"
          ),
          color=discord.Color.gold(),
          timestamp=discord.utils.utcnow(),
      )
      embed.set_thumbnail(url=member.display_avatar.url)
      embed.set_footer(text="Brevix Level System")
      await lvl_channel.send(embed=embed)


class LevelRequirementsModal(discord.ui.Modal, title="تحديد متطلبات ومكافآت الليفل"):
  level_num = discord.ui.TextInput(
      label="رقم المستوي المراد ضبطه", placeholder="مثال: 1"
  )
  req_msg = discord.ui.TextInput(
      label="عدد الرسائل المطلوبة", placeholder="مثال: 100"
  )
  req_voice = discord.ui.TextInput(
      label="الدقائق الصوتية المطلوبة", placeholder="مثال: 60"
  )
  reward_coins = discord.ui.TextInput(
      label="مكافأة الكوينز عند الترقية", placeholder="مثال: 200"
  )

  async def on_submit(self, interaction: discord.Interaction):
    try:
      lvl = int(self.level_num.value.strip())
      msgs = int(self.req_msg.value.strip())
      voice = int(self.req_voice.value.strip())
      rew = int(self.reward_coins.value.strip())
    except ValueError:
      await interaction.response.send_message(
          "❌ كافة الحقول يجب أن تحتوي على أرقام صحيحة!", ephemeral=True
      )
      return

    database["levels"][lvl] = {
        "req_msg": msgs,
        "req_voice": voice,
        "reward": rew,
    }
    await interaction.response.send_message(
        f"✅ تم حفظ قواعد ومتطلبات **Level {lvl}** بنجاح (رسائل: {msgs},"
        f" صوتي: {voice}د, مكافأة: {rew} كوينز).",
        ephemeral=True,
    )


class DiscountManagementModal(discord.ui.Modal, title="إنشاء أو إنهاء كود خصم إداري"):
  action_type = discord.ui.TextInput(
      label="الإجراء (انشاء أو انهاء)", placeholder="اكتب: انشاء أو انهاء"
  )
  disc_code = discord.ui.TextInput(
      label="كود الخصم", placeholder="مثال: BREVIX50"
  )
  discount_val = discord.ui.TextInput(
      label="نسبة الخصم (لو انشاء)", placeholder="مثال: 25", required=False
  )
  expiry_days = discord.ui.TextInput(
      label="الصلاحية بالأيام (لو انشاء)", placeholder="مثال: 7", required=False
  )
  max_uses = discord.ui.TextInput(
      label="الحد الأقصى للاستخدام (لو انشاء)",
      placeholder="مثال: 10 أو فارغ للغير محدود",
      required=False,
  )
  role_id = discord.ui.TextInput(
      label="آي دي الرول المطلوبة للكود (اختياري)",
      placeholder="1541620051...",
      required=False,
  )

  async def on_submit(self, interaction: discord.Interaction):
    act = self.action_type.value.strip().lower()
    code = self.disc_code.value.strip()

    if act in ["انشاء", "create"]:
      try:
        d_val = int(self.discount_val.value.strip())
        days = (
            int(self.expiry_days.value.strip())
            if self.expiry_days.value.strip().isdigit()
            else None
        )
        uses = (
            int(self.max_uses.value.strip())
            if self.max_uses.value.strip().isdigit()
            else None
        )
        r_id = (
            int(self.role_id.value.strip())
            if self.role_id.value.strip().isdigit()
            else None
        )
      except ValueError:
        await interaction.response.send_message(
            "❌ نسبة الخصم والأيام والحد الأقصى يجب أن تكون أرقاماً صحيحة!",
            ephemeral=True,
        )
        return

      expiry_dt = (
          datetime.datetime.now() + datetime.timedelta(days=days)
          if days
          else None
      )

      database["admin_codes"][code] = {
          "discount": d_val,
          "expiry_date": expiry_dt,
          "max_uses": uses,
          "uses": 0,
          "role_id": r_id,
      }
      await interaction.response.send_message(
          f"✅ تم إنشاء كود الخصم الإداري `{code}` بنسبة `{d_val}%` بنجاح!",
          ephemeral=True,
      )

    elif act in ["انهاء", "delete", "end"]:
      if code in database["admin_codes"]:
        del database["admin_codes"][code]
        await interaction.response.send_message(
            f"✅ تم إنهاء وإلغاء صلاحية كود الخصم `{code}` تماماً (يشرب ميته!).",
            ephemeral=True,
        )
      else:
        await interaction.response.send_message(
            "❌ كود الخصم غير موجود أساساً!", ephemeral=True
        )
    else:
      await interaction.response.send_message(
          "❌ برجاء كتابة الإجراء بشكل صحيح (انشاء أو انهاء).", ephemeral=True
      )


class InspectUserModal(discord.ui.Modal, title="استعلام عن بيانات وممتلكات لاعب"):
  user_id = discord.ui.TextInput(
      label="آي دي العضو (User ID)", placeholder="اكتب الآي دي هنا"
  )

  async def on_submit(self, interaction: discord.Interaction):
    u_id = self.user_id.value.strip()
    u_data = database["users"].get(u_id)

    if not u_data:
      await interaction.response.send_message(
          "❌ لا توجد بيانات مسجلة لهذا العضو في النظام!", ephemeral=True
      )
      return

    try:
      member = await interaction.guild.fetch_member(int(u_id))
      member_name = member.name
      avatar_url = member.display_avatar.url
    except Exception:
      member_name = f"User ID: {u_id}"
      avatar_url = interaction.guild.icon.url if interaction.guild.icon else None

    discounts = u_data.get("discount_codes", {})
    disc_list = (
        ", ".join([f"`{c}` ({v}%)" for c, v in discounts.items()])
        if discounts
        else "لا توجد"
    )
    inv = u_data.get("inventory", [])
    inv_list = ", ".join([f"`{p}`" for p in inv]) if inv else "فارغ"

    embed = discord.Embed(
        title=f"🔍 تقرير ممتلكات وبيانات العضو: {member_name}",
        color=discord.Color.blurple(),
    )
    if avatar_url:
      embed.set_thumbnail(url=avatar_url)
    embed.add_field(
        name="🪙 الرصيد الحالي",
        value=f"{u_data.get('coins', 0)} BX Coins",
        inline=True,
    )
    embed.add_field(
        name="⭐ المستوى (Level)",
        value=f"Level {u_data.get('level', 0)}",
        inline=True,
    )
    embed.add_field(
        name="💬 الرسائل والدقائق",
        value=(
            f"رسائل: {u_data.get('messages', 0)} | صوتي:"
            f" {u_data.get('voice_minutes', 0)}د"
        ),
        inline=False,
    )
    embed.add_field(
        name="🏷️ أكواد الخصم النشطة", value=disc_list, inline=False
    )
    embed.add_field(
        name="📦 مشتريات المخزون (أكواد المنتجات)", value=inv_list, inline=False
    )

    await interaction.response.send_message(embed=embed, ephemeral=True)


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
      title="🛠️ لوحة تحكم الإدارة المركزية (المطورة والمؤمنة)",
      description=(
          "تحكم كامل في المنتجات، رصيد الأعضاء، الليفل، أكواد الخصم، والصلاحيات"
          " بنظام حماية عالي."
      ),
      color=discord.Color.red(),
  )
  await ctx.send(embed=embed, view=AdminView())


# تشغيل البوت بأمان باستخدام التوكن المخفي
bot.run(os.getenv("DISCORD_TOKEN"))
