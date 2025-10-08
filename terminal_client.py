import asyncio
import httpx
import logging
from agent_core import add_activity_log

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/root/stark/terminal.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class TerminalClient:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.user_id = "terminal_user"
        add_activity_log("INFO", "Терминальный клиент инициализирован", self.user_id)
        logger.info("Терминальный клиент инициализирован")

    async def chat_loop(self):
        add_activity_log("INFO", "Запуск терминального интерфейса", self.user_id)
        logger.info("🤖 Stark AI Terminal Interface")

        print("🤖 Stark AI Terminal")
        print("Команды: 'quit' - выход, 'clear' - очистка истории")
        print("-" * 50)

        while True:
            try:
                user_input = input("\n👤 Вы: ").strip()

                if user_input.lower() == 'quit':
                    add_activity_log("INFO", "Выход из терминала", self.user_id)
                    logger.info("Выход из терминала")
                    break
                elif user_input.lower() == 'clear':
                    await self.clear_history()
                    add_activity_log("INFO", "История очищена", self.user_id)
                    print("✅ История очищена")
                    continue
                elif not user_input:
                    continue

                add_activity_log("INFO", f"Терминальный запрос: '{user_input}'", self.user_id)
                logger.info(f"Обработка терминального запроса: {user_input}")

                print("🤖 Агент думает...", end="", flush=True)

                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.api_url}/api/chat",
                        json={"user_id": self.user_id, "message": user_input},
                        timeout=30.0
                    )

                    if response.status_code == 200:
                        data = response.json()
                        print(f"\r🤖 AI: {data['response']}")
                        add_activity_log("INFO", "Ответ сгенерирован в терминале", self.user_id)
                        logger.info("Ответ отправлен в терминал")
                    else:
                        error_msg = f"Ошибка API: {response.status_code}"
                        print(f"\r❌ Ошибка: {response.status_code}")
                        add_activity_log("ERROR", error_msg, self.user_id)
                        logger.error(error_msg)

            except KeyboardInterrupt:
                add_activity_log("INFO", "Выход из терминала (Ctrl+C)", self.user_id)
                logger.info("Выход из терминала по Ctrl+C")
                print("\n👋 Выход...")
                break
            except Exception as e:
                error_msg = f"Ошибка терминала: {e}"
                print(f"\r❌ Ошибка: {e}")
                add_activity_log("ERROR", error_msg, self.user_id)
                logger.error(error_msg)

    async def clear_history(self):
        """Очистка истории диалога"""
        try:
            async with httpx.AsyncClient() as client:
                await client.post(f"{self.api_url}/api/clear", params={"user_id": self.user_id})
        except Exception as e:
            error_msg = f"Ошибка очистки истории: {e}"
            add_activity_log("ERROR", error_msg, self.user_id)
            logger.error(error_msg)


async def main():
    client = TerminalClient()
    await client.chat_loop()


if __name__ == "__main__":
    asyncio.run(main())