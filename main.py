const { Client, GatewayIntentBits, EmbedBuilder, ActionRowBuilder, ButtonBuilder, ButtonStyle, ChannelType, PermissionsBitField } = require('discord.js');
require('dotenv').config();

const client = new Client({
    intents: [
        GatewayIntentBits.Guilds,
        GatewayIntentBits.GuildMessages,
        GatewayIntentBits.MessageContent
    ]
});

// تعريف البيانات (الإيموجيات، الفئات، والرولات لكل زرار)
const ticketData = {
    'ticket_player': {
        name: 'شكوى ضد لاعب',
        categoryId: '1552034050816999625',
        typeText: 'تذكرة ضد لاعب',
        roles: ['1552030709026131990', '1552031186325606532', '1552031250255188138']
    },
    'ticket_faction': {
        name: 'شكوى ضد قائد فصيل',
        categoryId: '1552034692272754738',
        typeText: 'تذكرة ضد قائد فصيل',
        roles: ['1552030869483687936', '1552030964161450027', '1552030709026131990', '1552031186325606532', '1552031250255188138']
    },
    'ticket_staff': {
        name: 'شكوى ضد إداري',
        categoryId: '1552034331436781608',
        typeText: 'تذكرة ضد إداري',
        roles: ['1552026718854844427', '1552030869483687936', '1552030964161450027', '1552030709026131990', '1552031186325606532']
    },
    'ticket_support': {
        name: 'الدعم الفني',
        categoryId: '1552184064121901160',
        typeText: 'تذكرة دعم فني',
        roles: ['1552026718854844427', '1552031112413577286']
    },
    'ticket_store': {
        name: 'المتجر',
        categoryId: '1552184221135675412',
        typeText: 'تذكرة المتجر',
        roles: ['1552026718854844427', '1552034858216333414']
    }
};

client.on('ready', () => {
    console.log(`Logged in as ${client.user.tag}!`);
});

// أمر الإعداد (!setup) لإرسال الواجهة
client.on('messageCreate', async message => {
    if (message.author.bot) return;

    if (message.content === '!setup') {
        // التحقق من صلاحيات المستخدم
        if (!message.member.permissions.has(PermissionsBitField.Flags.Administrator)) {
            return message.reply('عذراً، هذا الأمر مخصص للإدارة فقط.');
        }

        const embed = new EmbedBuilder()
            .setTitle('🎫 | قـسـم التـذاكـر والـدعم الفـنـي')
            .setDescription('مرحباً بك في قسم التذاكر! إذا كانت لديك أي استفسارات أو تواجه أي مشكلة أو تحتاج إلى المساعدة، فما عليك سوى اختيار الموضوع المناسب من القائمة أدناه للتواصل مع فريق الإدارة، وسنكون سعداء بخدمتك في أقرب وقت ممكن.')
            .setImage('https://cdn.discordapp.com/attachments/1552028670900830299/1552030625693966438/IMG__.png?ex=6ab4c968&is=6ab377e8&hm=00b6d179088f91b56be8c75f43a6425bd6826d2d345ec91dedc79b7a13868d3c&')
            .setColor('#2b2d31')
            .setFooter({ text: 'يرجى الالتزام بقوانين التذاكر لتجنب التعرض للعقوبة.' });

        // الصف الأول للأزرار الأربعة الأولى
        const row1 = new ActionRowBuilder().addComponents(
            new ButtonBuilder()
                .setCustomId('ticket_player')
                .setLabel('شكوى ضد لاعب')
                .setStyle(ButtonStyle.Secondary)
                .setEmoji('📗'),
            new ButtonBuilder()
                .setCustomId('ticket_faction')
                .setLabel('شكوى ضد قائد فصيل')
                .setStyle(ButtonStyle.Secondary)
                .setEmoji('📘'),
            new ButtonBuilder()
                .setCustomId('ticket_staff')
                .setLabel('شكوى ضد إداري')
                .setStyle(ButtonStyle.Secondary)
                .setEmoji('📕'),
            new ButtonBuilder()
                .setCustomId('ticket_support')
                .setLabel('الدعم الفني')
                .setStyle(ButtonStyle.Secondary)
                .setEmoji('🛠️')
        );

        // الصف الثاني لزر المتجر وزر القواعد
        const row2 = new ActionRowBuilder().addComponents(
            new ButtonBuilder()
                .setCustomId('ticket_store')
                .setLabel('المتجر')
                .setStyle(ButtonStyle.Secondary)
                .setEmoji('🛍️'),
            new ButtonBuilder()
                .setCustomId('ticket_rules')
                .setLabel('قوانين التذاكر')
                .setStyle(ButtonStyle.Primary)
                .setEmoji('📜')
        );

        await message.channel.send({
            embeds: [embed],
            components: [row1, row2]
        });

        // حذف رسالة الأمر لتنظيف الشات
        await message.delete().catch(() => {});
    }
});

// التعامل مع الضغط على الأزرار
client.on('interactionCreate', async interaction => {
    if (!interaction.isButton()) return;

    // زر قوانين التذاكر (رسالة Ephemeral خاصة باللي داس عليه)
    if (interaction.customId === 'ticket_rules') {
        const rulesText = `**قوانين التذاكر:**

1. لن يتم قبول أي شكاوى مقدمة من طرف ثالث.
2. قد لا يتم قبول الأدلة إذا تم تسجيلها قبل أكثر من أسبوع من تاريخ فتح التذكرة.
3. يمكن تقديم طلب استئناف ضد العقوبات الصادرة من الإداريين خلال مدة أقصاها 3 أيام فقط.
4. يُمنع منعاً باتاً فتح أكثر من تذكرة لنفس الحالة أو الشكوى.
5. يجب أن يكون التاريخ، الوقت، واسم الشخص ظاهرين بوضوح تام في الأدلة المُقدمة، والا سيتم رفض الشكوى فوراً.
6. الشكاوي ليست مجهولة أو سرية؛ وقد يتم مشاركة الدليل مع الطرف الآخر عند اتخاذ الإجراءات.
7. يُمنع استخدام الإشارات (Mentions) غير الضرورية أو إساءة استخدامها للإدارة داخل التذاكر.
8. تستغرق مدة مراجعة الشكاوي، التقارير، واتخاذ الإجراءات اللازمة ما يصل إلى 24 ساعة كحد أقصى (باستثناء بعض الحالات التي تتطلب تدقيقاً خاصاً).`;

        return await interaction.reply({ content: rulesText, ephemeral: true });
    }

    // التعامل مع أزرار فتح التذاكر
    const data = ticketData[interaction.customId];
    if (!data) return;

    await interaction.deferReply({ ephemeral: true });

    try {
        const guild = interaction.guild;
        const member = interaction.member;

        // إنشاء روم التذكرة في الفئة المحددة
        const channel = await guild.channels.create({
            name: `ticket-${member.user.username}`,
            type: ChannelType.GuildText,
            parent: data.categoryId,
            permissionOverwrites: [
                {
                    id: guild.id,
                    deny: [PermissionsBitField.Flags.ViewChannel],
                },
                {
                    id: member.id,
                    allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory],
                },
                ...data.roles.map(roleId => ({
                    id: roleId,
                    allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory],
                }))
            ],
        });

        // تنسيق منشن الرولات مع الفاصل |
        const roleMentions = data.roles.map(roleId => `<@&${roleId}>`).join(' | ');

        // الرسالة الترحيبية داخل التذكرة
        const welcomeMessage = `قام <@${member.id}> بإنشاء ${data.typeText}\n${roleMentions}`;
        await channel.send({ content: welcomeMessage });

        await interaction.editReply({ content: `تم فتح تذكرتك بنجاح: ${channel}` });
    } catch (error) {
        console.error(error);
        await interaction.editReply({ content: 'حدث خطأ أثناء محاولة إنشاء التذكرة، يرجى مراجعة الإدارة.' });
    }
});

// تشغيل البوت باستخدام متغير البيئة
client.login(process.env.DISCORD_TOKEN);
