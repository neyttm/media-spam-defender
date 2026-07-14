import discord
from discord.ext import commands
import time
from collections import defaultdict
import config

class AntiRaid(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Хранилище истории сообщений новичков
        # Структура: {user_id: [ (timestamp, attachment_hash_or_url) ]}
        self.media_history = defaultdict(list)
        # Хранилище предупреждений (число нарушений)
        self.violations = defaultdict(int)

    def is_protected_tag(self, member: discord.Member) -> bool:
        """Проверка, является ли пользователь 'своим' по тегу сервера."""
        # 1. Проверяем официальный тег сервера по ID (если у бота есть доступ к профилю)
        if member.public_flags.clan:
            # Сверяем ID клана с целевым сервером
            if member.public_flags.clan.guild_id == config.GUILD_ID:
                return True
            # Сверяем по названию тега, если это дружественный ZOV-клан с другого сервера
            if member.public_flags.clan.tag and member.public_flags.clan.tag.upper() == "ZOV":
                return True

        # 2. Дополнительная проверка по никнейму или статусу на случай, если тег прописан вручную
        display_name = member.display_name.upper()
        global_name = (member.global_name or "").upper()
        
        if "ZOV" in display_name or "ZOV" in global_name:
            return True
            
        return False

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Игнорируем сообщения самого бота, личные сообщения и системные сообщения
        if message.author.bot or not message.guild or message.guild.id != config.GUILD_ID:
            return

        member = message.author
        now = time.time()

        # 1. Если у пользователя есть тег ZOV (наш или сторонний) — игнорируем любые проверки
        if self.is_protected_tag(member):
            return

        # 2. Проверяем время нахождения на сервере (Карантин)
        join_time = member.joined_at.timestamp() if member.joined_at else now
        time_on_server = now - join_time

        # Если пользователь на сервере больше установленного времени карантина — не трогаем его
        if time_on_server > (config.QUARANTINE_MINUTES * 60):
            return

        # 3. Проверка на период иммунитета (первые 30 секунд после захода бот не трогает сообщения)
        if time_on_server < config.IMMUNITY_SECONDS:
            return

        # 4. Проверяем наличие медиафайлов (картинки, видео, гифки) или ссылок на медиа-хостинги
        has_media = False
        media_identifier = None

        if message.attachments:
            has_media = True
            # Используем размер файла и имя в качестве простого хэша для уникальности
            media_identifier = f"{message.attachments[0].size}_{message.attachments[0].filename}"
        elif "tenor.com" in message.content or "giphy.com" in message.content:
            has_media = True
            media_identifier = message.content  # Ссылка на гифку выступает идентификатором

        if not has_media or not media_identifier:
            return

        # Записываем событие отправки медиа
        user_id = member.id
        self.media_history[user_id].append((now, media_identifier))

        # Очищаем старую историю медиа, вышедшую за рамки окна проверки (2 минуты)
        self.media_history[user_id] = [
            (t, h) for t, h in self.media_history[user_id]
            if now - t <= config.MEDIA_CHECK_WINDOW
        ]

        user_media = self.media_history[user_id]

        # 5. Если количество медиа превысило лимит за 2 минуты
        if len(user_media) > config.MAX_MEDIA_COUNT:
            # Считаем количество уникальных файлов в истории
            unique_files = set(h for _, h in user_media)

            # Если уникальных файлов мало — детектируем зацикленный спам
            if len(unique_files) <= config.MIN_UNIQUE_MEDIA:
                self.violations[user_id] += 1

                # ШАГ 1: Первая зачистка сообщений
                if self.violations[user_id] == 1:
                    try:
                        # Удаляем спам-сообщения за последние 2 минуты
                        async for msg in message.channel.history(limit=50):
                            if msg.author.id == user_id and (now - msg.created_at.timestamp()) <= config.MEDIA_CHECK_WINDOW:
                                await msg.delete()
                    except discord.Forbidden:
                        pass  # Недостаточно прав для удаления сообщений

                # ШАГ 2: Рецидив (Второй спам-цикл) -> БАН
                elif self.violations[user_id] > 1:
                    try:
                        # Баним с очисткой истории сообщений за 7 дней
                        await member.ban(reason="AntiRaid: Repeated media spam patterns", delete_message_days=7)
                        
                        # Очищаем локальные данные пользователя
                        if user_id in self.media_history:
                            del self.media_history[user_id]
                        if user_id in self.violations:
                            del self.violations[user_id]
                    except discord.Forbidden:
                        pass  # Недостаточно прав для бана

def setup(bot):
    bot.add_cog(AntiRaid(bot))
