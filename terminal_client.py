import asyncio
import httpx

class TerminalClient:
    def __init__(self, api_url: str = "http://localhost:8000"):
        self.api_url = api_url
        self.user_id = "terminal_user"
        
    async def chat_loop(self):
        print("🤖 Stark AI Terminal")
        print("Команды: 'quit' - выход, 'clear' - очистка истории")
        print("-" * 50)
        
        while True:
            try:
                user_input = input("\n👤 Вы: ").strip()
                
                if user_input.lower() == 'quit':
                    break
                elif user_input.lower() == 'clear':
                    await self.clear_history()
                    print("✅ История очищена")
                    continue
                
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.api_url}/api/chat",
                        json={"user_id": self.user_id, "message": user_input},
                        timeout=30.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        print(f"🤖 AI: {data['response']}")
                    else:
                        print(f"❌ Ошибка: {response.status_code}")
                        
            except KeyboardInterrupt:
                print("\n👋 Выход...")
                break
            except Exception as e:
                print(f"❌ Ошибка: {e}")
    
    async def clear_history(self):
        async with httpx.AsyncClient() as client:
            await client.post(f"{self.api_url}/api/clear", params={"user_id": self.user_id})

async def main():
    client = TerminalClient()
    await client.chat_loop()
