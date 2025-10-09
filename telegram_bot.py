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
from agent_core import AIAgent, add_activity_log
from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/stark/telegram.log', encoding='utf-8'),
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
        add_activity_log("INFO", "Пользователь запустил бота", f"tg_{user_id}")
        logger.info(f"Пользователь {user_id} запустил бота")

        await update.message.reply_text("🤖 Привет! Я Stark AI ассистент. Просто напиши мне сообщение!")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        API: Обработчик входящих сообщений Telegram
        Вход: update (данные сообщения), context (контекст бота)
        Выход: None (отправляет ответ пользователю)
        Логика: Преобразование в user_id формата "tg_12345", вызов agent.process_message()
        """
        user_id = str(update.effective_user.id)
        user_message = update.message.text

        add_activity_log("INFO", f"Telegram сообщение: '{user_message}'", f"tg_{user_id}")
        logger.info(f"Обработка сообщения от {user_id}: {user_message}")

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            response = await self.agent.process_message(f"tg_{user_id}", user_message)
            await update.message.reply_text(response)
            add_activity_log("INFO", "Ответ отправлен в Telegram", f"tg_{user_id}")
            logger.info(f"Ответ отправлен пользователю {user_id}")

        except Exception as e:
            error_msg = f"Ошибка Telegram бота: {e}"
            await update.message.reply_text("❌ Произошла ошибка")
            add_activity_log("ERROR", error_msg, f"tg_{user_id}")
            logger.error(f"Ошибка Telegram бота для пользователя {user_id}: {e}")

    def run(self):
        """
        API: Запуск Telegram бота
        Вход: None
        Выход: None (блокирующий вызов)
        Логика: Создает отдельный event loop, настраивает обработчики, запускает polling
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            application = Application.builder().token(self.token).build()
            application.add_handler(CommandHandler("start", self.start))
            application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

            add_activity_log("INFO", "Запуск Telegram бота")
            logger.info("Telegram bot starting...")

            application.run_polling()

        except Exception as e:
            error_msg = f"Критическая ошибка Telegram бота: {e}"
            add_activity_log("ERROR", error_msg)
            logger.error(error_msg)