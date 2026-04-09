import requests
import os
import socket
import re
import base64

GIST_ID = os.environ.get('GIST_ID')
GIST_TOKEN = os.environ.get('GIST_TOKEN')
TARGET_FILE = "vps.txt"

SOURCES = [
    "https://github.com",
    "https://github.com",
    "https://github.com"
]

def check_server(config):
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match:
            match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if match:
            host, port = match.group(1), int(match.group(2))
            with socket.create_connection((host, port), timeout=1):
                return True
    except: pass
    return False

def run():
    print("--- ЗАПУСК ОЧИСТКИ ---")
    raw_configs = []
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            # Если текст похож на Base64 (без пробелов), пробуем декодировать
            if "://" not in res and len(res) > 20:
                try:
                    res = base64.b64decode(res).decode('utf-8')
                except: pass
            
            found = re.findall(r'(?:vless|vmess|ss)://[^\s]+', res)
            raw_configs.extend(found)
        except: continue

    unique = list(set([c.strip() for c in raw_configs]))
    print(f"Найдено уникальных ключей: {len(unique)}")

    if not unique:
        print("Ошибка: ключи не найдены. Проверьте источники.")
        return

    # Проверяем первые 300
    working = [c for c in unique[:300] if check_server(c)]
    print(f"Рабочих найдено: {len(working)}")

    if working:
        url = f"https://github.com{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        data = {"files": {TARGET_FILE: {"content": "\n".join(working)}}}
        
        r = requests.patch(url, headers=headers, json=data)
        if r.status_code == 200:
            print("УСПЕХ: Gist обновлен!")
        else:
            print(f"ОШИБКА API: {r.status_code}")
    else:
        print("НЕТ РАБОЧИХ СЕРВЕРОВ")

if __name__ == "__main__":
    run()
