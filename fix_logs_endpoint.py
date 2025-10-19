"""
Исправление рекурсивного вызова в endpoint /api/logs
"""

# Читаем текущий server.py
with open('./core/services/server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Заменяем проблемный участок
old_code = '''@app.get("/api/logs")
async def get_recent_logs(limit: int = 15):
        logs = get_recent_logs(limit)
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                'level': log.level,
                'message': log.message,
                'user_id': log.user_id or 'system',
                'timestamp': log.timestamp.strftime('%H:%M:%S') if log.timestamp else 'unknown'
            })
        return {"logs": formatted_logs, "status": "success", "total": len(formatted_logs)}'''

new_code = '''@app.get("/api/logs")
async def get_recent_logs(limit: int = 15):
        from core.services.database.database import get_recent_logs as get_logs_from_db
        logs = get_logs_from_db(limit)
        formatted_logs = []
        for log in logs:
            formatted_logs.append({
                'level': log.level,
                'message': log.message,
                'user_id': log.user_id or 'system',
                'timestamp': log.timestamp.strftime('%H:%M:%S') if log.timestamp else 'unknown'
            })
        return {"logs": formatted_logs, "status": "success", "total": len(formatted_logs)}'''

if old_code in content:
    content = content.replace(old_code, new_code)
    with open('./core/services/server.py', 'w', encoding='utf-8') as f:
        f.write(content)
    print("✅ Endpoint /api/logs исправлен!")
else:
    print("❌ Код для замены не найден. Проверьте структуру файла.")
