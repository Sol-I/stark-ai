from openai import OpenAI
import logging
import asyncio
from config import OPENROUTER_API_KEY, MODEL_RANKING

logging.basicConfig(level=logging.WARNING)

class AIAgent:
    def __init__(self, api_key: str = OPENROUTER_API_KEY):
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self.conversations = {}
        self.max_history = 3
        self.model_ranking = MODEL_RANKING
        self.current_model_index = 0
        self.available_models = set()
        
    async def check_model_availability(self, model_name: str) -> bool:
        """Проверяет доступность модели"""
        try:
            test_message = [{"role": "user", "content": "test"}]
            completion = self.client.chat.completions.create(
                extra_headers={
                    "HTTP-Referer": "http://94.228.123.86:8000",
                    "X-Title": "Stark AI",
                },
                model=model_name,
                messages=test_message,
                max_tokens=10
            )
            return True
        except Exception:
            return False
    
    async def find_best_available_model(self) -> str:
        """Находит лучшую доступную модель"""
        for i, model in enumerate(self.model_ranking):
            if await self.check_model_availability(model["name"]):
                self.current_model_index = i
                print(f"✅ Переключился на модель: {model['name']} ({model['params']}B)")
                return model["name"]
        
        # Если ничего не доступно, возвращаем последнюю работающую
        return self.model_ranking[-1]["name"]
    
    async def process_message(self, user_id: str, message: str) -> str:
        if user_id not in self.conversations:
            self.conversations[user_id] = []
        
        current_history = self.conversations[user_id][-self.max_history:]
        current_history.append({"role": "user", "content": message})
        
        try:
            current_model = self.model_ranking[self.current_model_index]
            
            # Пробуем текущую модель
            try:
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://94.228.123.86:8000",
                        "X-Title": "Stark AI",
                    },
                    model=current_model["name"],
                    messages=current_history,
                    max_tokens=1024
                )
                
                ai_response = completion.choices[0].message.content
                model_info = f"\n\n---\n*Отвечает {current_model['provider']} ({current_model['params']}B параметров)*"
                
            except Exception:
                # Если текущая модель не работает, ищем лучшую доступную
                best_model_name = await self.find_best_available_model()
                best_model = self.model_ranking[self.current_model_index]
                
                completion = self.client.chat.completions.create(
                    extra_headers={
                        "HTTP-Referer": "http://94.228.123.86:8000", 
                        "X-Title": "Stark AI",
                    },
                    model=best_model_name,
                    messages=current_history,
                    max_tokens=1024
                )
                
                ai_response = completion.choices[0].message.content
                model_info = f"\n\n---\n*Автоматически переключился на {best_model['provider']} ({best_model['params']}B)*"
            
            current_history.append({"role": "assistant", "content": ai_response})
            self.conversations[user_id] = current_history[-self.max_history:]
            
            return ai_response + model_info
            
        except Exception as e:
            return f"Ошибка: {str(e)}"
    
    async def background_model_checker(self):
        """Фоновая проверка доступности лучших моделей"""
        while True:
            try:
                # Проверяем доступность моделей с высоким рейтингом
                for i in range(3):  # Проверяем топ-3 модели
                    if i != self.current_model_index and await self.check_model_availability(self.model_ranking[i]["name"]):
                        if i < self.current_model_index:  # Если нашли модель лучше текущей
                            self.current_model_index = i
                            print(f"🎯 Вернулся к лучшей модели: {self.model_ranking[i]['name']}")
                            break
                
                await asyncio.sleep(300)  # Проверяем каждые 5 минут
            except Exception:
                await asyncio.sleep(60)
    
    def clear_history(self, user_id: str):
        if user_id in self.conversations:
            del self.conversations[user_id]
