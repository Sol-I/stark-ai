import asyncio
import threading
import time
from server import run_server
from telegram_bot import TelegramBot
from terminal_client import TerminalClient
import sys

def start_telegram_bot():
    bot = TelegramBot()
    bot.run()

async def start_terminal():
    client = TerminalClient()
    await client.chat_loop()

async def main():
    print("🚀 Запуск Stark AI с умным выбором моделей...")
    print("📊 Рейтинг моделей по параметрам:")
    
    from config import MODEL_RANKING
    for i, model in enumerate(MODEL_RANKING, 1):
        print(f"{i}. {model['provider']} - {model['params']}B параметров")
    
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    
    print("⏳ Ожидаем запуск сервера...")
    time.sleep(5)
    print("✅ Сервер запущен на http://localhost:8000")
    print("🌐 Веб-интерфейс: http://94.228.123.86:8000")
    print("🔄 Фоновая проверка моделей запущена...")
    
    # Запускаем фоновую проверку моделей
    from agent_core import AIAgent
    agent = AIAgent()
    background_task = asyncio.create_task(agent.background_model_checker())
    
    await start_terminal()

if __name__ == "__main__":
    asyncio.run(main())
