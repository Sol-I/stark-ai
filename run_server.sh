#!/bin/bash
cd ~/stark

# Создаем полный config
cat > config.py << 'CONFIG'
"""
Configuration Module - настройки Stark AI системы
API: Централизованное хранение всех конфигурационных параметров
Основные возможности: управление моделями, лимитами, таймаутами, провайдерами
"""

# API Keys - ключи доступа к провайдерам
OPENROUTER_API_KEY = "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"
DEEPSEEK_API_KEY = "sk-c485a699d55f486fba42442eefc92e88"
TELEGRAM_BOT_TOKEN = "7973196668:AAGCFQYMe4cm6WCGSyZHT6iihj43cnT7qk4"

# Server Configuration - настройки сервера
HOST = "0.0.0.0"
PORT = 8000

# AI Agent Configuration - настройки AI агента
MAX_HISTORY_LENGTH = 10  # глубина истории для передачи llm
REQUEST_TIMEOUT = 30  # максимальное время ожидания ответа от llm

# API Endpoints - базовые URL провайдеров
API_ENDPOINTS = {
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com"
}

# API Strategies - полные конфигурации провайдеров
API_STRATEGIES = {
    'openrouter': {
        'url': '{endpoint}/chat/completions',
        'headers': {
            'Authorization': 'Bearer {api_key}',
            'Content-Type': 'application/json',
            'HTTP-Referer': 'https://stark-ai.com',
            'X-Title': 'Stark AI Assistant'
        },
        'body_template': {
            'model': '{model_name}',
            'messages': [{'role': 'user', 'content': '{prompt}'}],
            'max_tokens': 1000,
            'temperature': 0.7
        },
        'response_parser': 'openai_format'
    },
    'deepseek': {
        'url': '{endpoint}/chat/completions',
        'headers': {
            'Authorization': 'Bearer {api_key}',
            'Content-Type': 'application/json'
        },
        'body_template': {
            'model': 'deepseek-chat',
            'messages': [{'role': 'user', 'content': '{prompt}'}],
            'max_tokens': 1000,
            'temperature': 0.7,
            'stream': False
        },
        'response_parser': 'openai_format'
    }
}
CONFIG

echo "✅ Config обновлен"

# Запускаем сервер
source venv/bin/activate
python main.py
