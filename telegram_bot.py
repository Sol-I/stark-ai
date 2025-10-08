from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import httpx
import logging
from config import TELEGRAM_BOT_TOKEN

logging.basicConfig(level=logging.INFO)

class TelegramBot:
    def __init__(self, token: str = TELEGRAM_BOT_TOKEN):
        self.token = token
        self.api_url = "http://localhost:8000"
        
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🤖 Привет! Я AI ассистент. Просто напиши мне сообщение!")
    
    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = str(update.effective_user.id)
        user_message = update.message.text
        
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.api_url}/api/chat",
                    json={"user_id": user_id, "message": user_message},
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    await update.message.reply_text(data["response"])
                else:
                    await update.message.reply_text("❌ Ошибка при обработке запроса")
                    
        except Exception as e:
            await update.message.reply_text("❌ Произошла ошибка")
    
    def run(self):
        application = Application.builder().token(self.token).build()
        application.add_handler(CommandHandler("start", self.start))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_message))
        application.run_polling()
