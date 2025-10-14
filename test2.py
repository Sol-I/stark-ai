import requests
import json

# Модели с поддержкой Inference API
url = "https://huggingface.co/api/models"
params = {
    'filter': 'text-generation-inference',
    'sort': 'downloads',
    'direction': '-1',
    'limit': 20
}

response = requests.get(url, params=params)
models = response.json()

print(f"🤗 Модели с Inference API (бесплатный тариф): {len(models)}")

for i, model in enumerate(models):
    print(f"  {i+1}. {model['id']} - 💾 {model.get('downloads', 0):,} downloads")

# Детали первой модели
if models:
    first_model = models[0]
    print(f"\n📊 Параметры '{first_model['id']}':")
    print(f"  - ID: {first_model['id']}")
    print(f"  - Загрузок: {first_model.get('downloads', 0):,}")
    print(f"  - Тэги: {first_model.get('tags', [])}")
    print(f"  - Лицензия: {first_model.get('license', 'N/A')}")
    print(f"  - Загрузки: {first_model.get('downloads', 0):,}")