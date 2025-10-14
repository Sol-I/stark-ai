import requests
import json

url = "https://openrouter.ai/api/v1/models"
headers = {
    "Authorization": "Bearer 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"
}

response = requests.get(url, headers=headers)
models = response.json()

# Список бесплатных моделей
free_models = []
for model in models['data']:
    pricing = model.get('pricing', {})
    if (pricing.get('prompt') == "0" and
        pricing.get('completion') == "0" and
        pricing.get('request') == "0"):
        free_models.append(model['id'])

print(f"🆓 Бесплатных моделей: {len(free_models)}")
for model in free_models:
    print(f"  - {model}")

# Детали первой бесплатной модели
if free_models:
    first_free = free_models[0]
    for model in models['data']:
        if model['id'] == first_free:
            print(f"\n📊 Параметры модели '{first_free}':")
            print(json.dumps(model, indent=2, ensure_ascii=False))
            break