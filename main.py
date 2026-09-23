import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

bot = commands.Bot(command_prefix="!", intents=intents)

# بيانات التذاكر (الفئات والرولات)
ticket_data = {
    'ticket_player': {
        'name': 'شكوى ضد لاعب',
        'category_id': 1552034050816999625,
        'type_text': 'تذكرة ضد لاعب',
        'roles': [1552030709026131990, 1552031186325606532, 1552031250255188138]
    },
    'ticket_faction': {
        'name': 'شكوى ضد قائد فصيل',
        'category_id': 1552034692272754738,
        'type_text': 'تذكرة ضد قائد فصيل',
        'roles': [1552030869483687936, 1552030964161450027, 1552030709026131990, 1552031186325606532, 1552031250255188138]
    },
    'ticket_staff': {
        'name': 'شكوى ضد إداري',
        'category_id': 1552034331436781608,
        'type_text': 'تذكرة ضد إداري',
        'roles': [1552026718854844427, 1552030869483687936, 1552030964161450027, 1552030709026131990, 1552031186325606532]
    },
    'ticket_support': {
        'name': 'الدعم الفني',
        'category_id': 1552184064121901160,
        'type_text': 'تذكرة دعم فني',
        'roles': [1552026718854844427, 1552031112413577286]
    },
    'ticket_store': {
        'name': 'المتجر',
        'category_id': 1552184221135675412,
        'type_text': 'تذكرة المتجر',
        'roles': [1552026718854844427, 1552034858216333414]
    }
}

class TicketSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="شكوى ضد لاعب", value="ticket_player", emoji="📗", description="لتقديم البلاغات ضد اللاعبين والاستفسار عن العقوبات"),
            discord.SelectOption(label="شكوى ضد قائد فصيل", value="ticket_faction", emoji="📘", description="لتقديم الشكاوى ضد قادة الفصائل وتجاوزاتهم"),
            discord.SelectOption(label="شكوى ضد إداري", value="ticket_staff", emoji="📕", description="للإبلاغ عن تجاوز أو سوء استخدام للسلطة للإدارة"),
            discord.SelectOption(label="الدعم الفني", value="ticket_support", emoji="🛠️", description="للمساعدة العامة وحل المشاكل التقنية"),
            discord.SelectOption(label="المتجر", value="ticket_store", emoji="🛍️")
        ]
        super().__init__(placeholder="يرجى اختيار الموضوع المناسب", min_values=1, max_values=1, options=options, custom_id="ticket_select_menu")

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        key = self.values[0]
        data = ticket_data[key]
        guild = interaction.guild
        member = interaction.user

        category = guild.get_channel(data['category_id'])
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            member: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }

        for role_id in data['roles']:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        channel = await guild.create_text_channel(
            name=f"ticket-{member.name}",
            category=category,
            overwrites=overwrites
        )

        role_mentions = " | ".join([f"<@&{r}>" for r in data['roles']])
        welcome_msg = f"قام <@{member.id}> بإنشاء {data['type_text']}\n{role_mentions}"
        
        await channel.send(welcome_msg)
        await interaction.followup.send(f"تم فتح تذكرتك بنجاح: {channel.mention}", ephemeral=True)

class TicketView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        # إضافة القائمة المنسدلة في الصف الأول
        self.add_item(TicketSelect())

    # زر قوانين التذاكر في الصف الثاني
    @discord.ui.button(label="قوانين التذاكر", style=discord.ButtonStyle.primary, emoji="📜", custom_id="ticket_rules", row=1)
    async def rules_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        rules_text = (
            "**قوانين التذاكر:**\n\n"
            "1. لن يتم قبول أي شكاوى مقدمة من طرف ثالث.\n"
            "2. قد لا يتم قبول الأدلة إذا تم تسجيلها قبل أكثر من أسبوع من تاريخ فتح التذكرة.\n"
            "3. يمكن تقديم طلب استئناف ضد العقوبات الصادرة من الإداريين خلال مدة أقصاها 3 أيام فقط.\n"
            "4. يُمنع منعاً باتاً فتح أكثر من تذكرة لنفس الحالة أو الشكوى.\n"
            "5. يجب أن يكون التاريخ، الوقت، واسم الشخص ظاهرين بوضوح تام في الأدلة المُقدمة، والا سيتم رفض الشكوى فوراً.\n"
            "6. الشكاوي ليست مجهولة أو سرية؛ وقد يتم مشاركة الدليل مع الطرف الآخر عند اتخاذ الإجراءات.\n"
            "7. يُمنع استخدام الإشارات (Mentions) غير الضرورية أو إساءة استخدامها للإدارة داخل التذاكر.\n"
            "8. تستغرق مدة مراجعة الشكاوي، التقارير، واتخاذ الإجراءات اللازمة ما يصل إلى 24 ساعة كحد أقصى (باستثناء بعض الحالات التي تتطلب تدقيقاً خاصاً)."
        )
        await interaction.response.send_message(rules_text, ephemeral=True)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}!")
    bot.add_view(TicketView())

@bot.command(name="setup")
@commands.has_permissions(administrator=True)
async def setup(ctx):
    embed = discord.Embed(
        title="🎫 | قـسـم التـذاكـر والـدعم الفـنـي",
        description="مرحباً بك في قسم التذاكر! إذا كانت لديك أي استفسارات أو تواجه أي مشكلة أو تحتاج إلى المساعدة، فما عليك سوى اختيار الموضوع المناسب من القائمة أدناه للتواصل مع فريق الإدارة، وسنكون سعداء بخدمتك في أقرب وقت ممكن.",
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
