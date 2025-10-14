# telegram_bot.py
"""
Telegram Bot - интерфейс для мессенджера
API: Обработка команд и сообщений из Telegram
Команды:
- /start - приветствие
- текстовые сообщения - обработка через AI Agent
"""

import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from agent_core import AIAgent

# Импорт системы логирования
try:
    from database import add_activity_log
except ImportError:
    # Fallback если БД не доступна
    def add_activity_log(level: str, message: str, user_id: str = None):
        print(f"📝 [{level}] {message} (user: {user_id})")

from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('telegram.log', encoding='utf-8', mode='a'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramBot:
    """
    Telegram Bot - интерфейс для мессенджера
    API: Обработка команд и сообщений из Telegram
    Основные возможности: асинхронная обработка сообщений, интеграция с AI Agent
    """
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN):
        """
        API: Инициализация Telegram бота
        Вход: token (API токен бота)
        Выход: None (создает экземпляр бота)
        Логика: Создает собственный экземпляр AI Agent для изоляции
        """
        self.token = token
        self.agent = AIAgent()
        add_activity_log("INFO", "Telegram бот инициализирован с собственным агентом")
        logger.info("Telegram бот инициализирован с собственным агентом")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        API: Обработчик команды /start
        Вход: update (данные обновления), context (контекст бота)
        Выход: None (отправляет приветственное сообщение)
        Логика: Регистрирует нового пользователя, отправляет приветствие
        """
        user_id = update.effective_user.id
        tg_user_id = f"tg_{user_id}"

        add_activity_log("INFO", "Пользователь запустил бота", tg_user_id)
        logger.info(f"Пользователь {user_id} запустил бота")

        user_info = f"{update.effective_user.first_name} {update.effective_user.last_name or ''} (@{update.effective_user.username or 'no_username'})"
        add_activity_log("DEBUG", f"Инфо пользователя: {user_info}", tg_user_id)

        await update.message.reply_text("🤖 Привет! Я Stark AI ассистент. Просто напиши мне сообщение!")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        API: Обработчик входящих сообщений Telegram
        Вход: update (данные сообщения), context (контекст бота)
        Выход: None (отправляет ответ пользователю)
        Логика: Преобразование в user_id формата "tg_12345", вызов agent.process_message()
        """
        user_id = update.effective_user.id
        tg_user_id = f"tg_{user_id}"
        user_message = update.message.text

        add_activity_log("INFO", f"Telegram сообщение: '{user_message}'", tg_user_id)
        logger.info(f"Обработка сообщения от {user_id}: {user_message}")

        # Логируем информацию о чате
        chat_info = f"chat_id: {update.effective_chat.id}, type: {update.effective_chat.type}"
        add_activity_log("DEBUG", chat_info, tg_user_id)

        # Показываем индикатор набора сообщения
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            add_activity_log("DEBUG", "Начало обработки AI агентом", tg_user_id)
            response = await self.agent.process_message(tg_user_id, user_message)

            add_activity_log("INFO", f"Ответ отправлен в Telegram ({len(response)} символов)", tg_user_id)
            await update.message.reply_text(response)

            logger.info(f"Ответ отправлен пользователю {user_id}")

        except Exception as e:
            error_msg = f"Ошибка Telegram бота: {e}"
            add_activity_log("ERROR", error_msg, tg_user_id)
            logger.error(f"Ошибка Telegram бота для пользователя {user_id}: {e}")

            await update.message.reply_text("❌ Произошла ошибка при обработке сообщения")

    async def handle_error(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        API: Обработчик ошибок бота
        Вход: update (данные обновления), context (контекст с ошибкой)
        Выход: None (логирует ошибку)
        Логика: Перехватывает и логирует все исключения в боте
        """
        error = context.error
        user_id = f"tg_{update.effective_user.id}" if update and update.effective_user else "unknown"

        add_activity_log("ERROR", f"Ошибка в Telegram боте: {error}", user_id)
        logger.error(f"Ошибка в Telegram боте: {error}")

    def run(self):
        """
        API: Запуск Telegram бота
        Вход: None
        Выход: None (блокирующий вызов)
        Логика: Простой запуск без создания event loop
        """
        application = Application.builder().token(self.token).build()

        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.add_error_handler(self.handle_error)

        logger.info("Telegram bot starting...")
        application.run_polling()
# Глобальный экземпляр для легкого доступа
telegram_bot = TelegramBot()

def main():
    """Запуск бота напрямую"""
    bot = TelegramBot()
    bot.run()

if __name__ == "__main__":
    main()