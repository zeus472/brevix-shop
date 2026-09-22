import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

# إعدادات البوت الأساسية
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# أيدي (IDs) الفئات المخفية الخاصة بالتذاكر (قم بتغيير الأرقام بأيدي الفئات في سيرفرك)
CATEGORY_IDS = {
    "player": 123456789012345678,  # فئة تذاكر اللاعبين
    "faction": 123456789012345678, # فئة تذاكر قادة الفصائل
    "staff": 123456789012345678,   # فئة تذاكر الإداريين
}

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    async def create_ticket(self, interaction: discord.Interaction, category_key: str, ticket_name: str):
        guild = interaction.guild
        category_id = CATEGORY_IDS.get(category_key)
        category = guild.get_channel(category_id)

        if not category:
            await interaction.response.send_message("❌ خطأ: لم يتم العثور على فئة التذاكر المخصصة لهذا القسم!", ephemeral=True)
            return

        # صلاحيات الروم (خاصة لصاحب التذكرة والإدارة فقط)
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        }

        # إنشاء روم التذكرة داخل الفئة المخفية
        ticket_channel = await guild.create_text_channel(
            name=f"{ticket_name}-{interaction.user.name}",
            category=category,
            overwrites=overwrites
        )

        await interaction.response.send_message(f"✅ تم إنشاء تذكرتك بنجاح: {ticket_channel.mention}", ephemeral=True)

        # رسالة ترحيبية داخل روم التذكرة
        embed = discord.Embed(
            title="🎫 تذكرة جديدة",
            description=f"مرحباً بك {interaction.user.mention}\nيرجى توضيح مشكلتك أو شكواك بكافة الأدلة وسيتم الرد عليك في أقرب وقت.",
            color=discord.Color.blue()
        )
        await ticket_channel.send(embed=embed)

    @discord.ui.button(label="شكوى ضد لاعب", style=discord.ButtonStyle.green, emoji="🟩", custom_id="ticket_player")
    async def player_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "player", "player-ticket")

    @discord.ui.button(label="شكوى ضد قائد فصيل", style=discord.ButtonStyle.blurple, emoji="🟦", custom_id="ticket_faction")
    async def faction_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "faction", "faction-ticket")

    @discord.ui.button(label="شكوى ضد إداري", style=discord.ButtonStyle.red, emoji="🟥", custom_id="ticket_staff")
    async def staff_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.create_ticket(interaction, "staff", "staff-ticket")

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    bot.add_view(TicketView())

# أمر إرسال بانر وقوانين التذاكر
@bot.command()
@commands.has_permissions(administrator=True)
async def setup_tickets(ctx):
    try:
        await ctx.message.delete()
    except:
        pass
    
    embed = discord.Embed(
        description=(
            "**شكاوى اللاعبين**\n"
            "🟩 مخصصة لتقديم البلاغات ضد اللاعبين أو الاستفسار عن العقوبات.\n"
            "> تقديم شكوي ضد لاعب\n\n"
            "**شكاوى قادة الفصائل**\n"
            "🟦 مخصصة لتقديم الشكاوى ضد قادة الفصائل وتجاوزاتهم داخل السيرفر.\n"
            "> تقديم شكوي ضد قائد فصيل\n\n"
            "**شكاوى الإداريين**\n"
            "🟥 مخصصة للإبلاغ عن أي تجاوز أو سوء استخدام للسلطة من قبل طاقم الإدارة.\n"
            "> تقديم شكوي ضد إداري\n\n"
            "--- \n\n"
            "**📋 قوانين التذاكر:**\n"
            "1. لن يتم قبول أي شكاوى مقدمة من طرف ثالث.\n"
            "2. قد لا يتم قبول الأدلة إذا تم تسجيلها قبل أكثر من أسبوع من تاريخ فتح التذكرة.\n"
            "3. يمكن تقديم طلب استئناف ضد العقوبات الصادرة من الإداريين خلال مدة أقصاها 3 أيام فقط.\n"
            "4. يُمنع منعاً باتاً فتح أكثر من تذكرة لنفس الحالة أو الشكوى.\n"
            "5. يجب أن يكون التاريخ، الوقت، واسم الشخص ظاهرين بوضوح تام في الأدلة المُقدمة، والا سيتم رفض الشكوى فوراً.\n"
            "6. الشكاوي ليست مجهولة أو سرية؛ وقد يتم مشاركة الدليل مع الطرف الآخر عند اتخاذ الإجراءات.\n"
            "7. يُمنع استخدام الإشارات (Mentions) غير الضرورية أو إساءة استخدامها للإدارة داخل التذاكر.\n"
            "8. تستغرق مدة مراجعة الشكاوي، التقارير، واتخاذ الإجراءات اللازمة ما يصل إلى 24 ساعة كحد أقصى (باستثناء بعض الحالات التي تتطلب تدقيقاً خاصاً).\n\n"
            "**⚠️ يرجى الإلتزام بقواعد تقديم التذاكر لعدم تعرضك للعقوبة**"
        ),
        color=discord.Color.from_rgb(30, 30, 30)
    )
    
    # تعيين البانر المطلوب في أعلى الـ Embed
    embed.set_image(url="https://cdn.discordapp.com/attachments/1552028670900830299/1552030625693966438/IMG__.png?ex=6ab420a8&is=6ab2cf28&hm=b39bcdaea4948e39f53fe59ec4d645c371b3ef26285d113a350caf79a24f4339&")

    view = TicketView()
    await ctx.send(embed=embed, view=view)

bot.run(os.getenv("DISCORD_TOKEN"))
