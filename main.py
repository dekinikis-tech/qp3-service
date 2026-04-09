import requests
import os
import socket
import re

# Настройки вашего Gist (пропишем вручную для надежности)
GIST_ID = os.environ.get('GIST_ID')
GIST_TOKEN = os.environ.get('GIST_TOKEN')
TARGET_FILE = "vps.txt"  # Имя вашего файла в Gist

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
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            found = re.findall(r'(?:vless|vmess|ss)://[^\s]+', res)
            all_configs.extend(found)
        except: continue

    unique = list(set([c.strip() for c in all_configs]))
    print(f"Найдено серверов: {len(unique)}")

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
