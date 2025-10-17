#!/usr/bin/env python3
from database import get_recent_logs

if __name__ == "__main__":
    logs = get_recent_logs(50)
    for log in logs:
        print(f"{log.timestamp.strftime('%H:%M:%S')} [{log.level}] {log.user_id or 'system'}: {log.message}")