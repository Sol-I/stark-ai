from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import httpx
import logging
import asyncio
from config import TELEGRAM_BOT_TOKEN
from agent_core import add_activity_log

# Настройка логирования
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
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN):
        self.token = token
        self.api_url = "http://localhost:8000"
        self.application = None
        add_activity_log("INFO", "Telegram бот инициализирован")
        logger.info("Telegram бот инициализирован")

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        add_activity_log("INFO", "Пользователь запустил бота", f"tg_{user_id}")
        logger.info(f"Пользователь {user_id} запустил бота")

        await update.message.reply_text("🤖 Привет! Я Stark AI ассистент. Просто напиши мне сообщение!")

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user_message = update.message.text

        add_activity_log("INFO", f"Telegram сообщение: '{user_message}'", f"tg_{user_id}")
        logger.info(f"Обработка сообщения от {user_id}: {user_message}")

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/api/chat",
                    json={"user_id": f"tg_{user_id}", "message": user_message},
                    timeout=30.0
                )

                if response.status_code == 200:
                    data = response.json()
                    await update.message.reply_text(data["response"])
                    add_activity_log("INFO", "Ответ отправлен в Telegram", f"tg_{user_id}")
                    logger.info(f"Ответ отправлен пользователю {user_id}")
                else:
                    error_msg = f"Ошибка API: {response.status_code}"
                    await update.message.reply_text("❌ Ошибка при обработке запроса")
                    add_activity_log("ERROR", error_msg, f"tg_{user_id}")
                    logger.error(f"Ошибка API для пользователя {user_id}: {response.status_code}")

        except Exception as e:
            error_msg = f"Ошибка Telegram бота: {e}"
            await update.message.reply_text("❌ Произошла ошибка")
            add_activity_log("ERROR", error_msg, f"tg_{user_id}")
            logger.error(f"Ошибка Telegram бота для пользователя {user_id}: {e}")

    def setup_handlers(self):
        """Настройка обработчиков"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))

    async def run_async(self):
        """Асинхронный запуск бота"""
        try:
            self.application = Application.builder().token(self.token).build()
            self.setup_handlers()

            add_activity_log("INFO", "Запуск Telegram бота (async)")
            logger.info("Telegram bot starting async...")

            await self.application.run_polling()

        except Exception as e:
            error_msg = f"Критическая ошибка Telegram бота: {e}"
            add_activity_log("ERROR", error_msg)
            logger.error(error_msg)

    def run(self):
        """Синхронный запуск бота (для отдельного потока)"""
        try:
            self.application = Application.builder().token(self.token).build()
            self.setup_handlers()

            add_activity_log("INFO", "Запуск Telegram бота")
            logger.info("Telegram bot started...")

            # Запускаем в отдельном event loop
            self.application.run_polling()

        except Exception as e:
            error_msg = f"Критическая ошибка Telegram бота: {e}"
            add_activity_log("ERROR", error_msg)
            logger.error(error_msg)