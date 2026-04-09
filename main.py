import requests
import os
import socket
import re

# --- НАСТРОЙКИ ---
GIST_ID = os.environ.get('GIST_ID')
GIST_TOKEN = os.environ.get('GIST_TOKEN')
TARGET_FILE = "vps.txt" 

# Ссылки как они есть (уже проверил, они работают)
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_server(config):
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match:
            match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if match:
            host, port = match.group(1), int(match.group(2))
            with socket.create_connection((host, port), timeout=1.5):
                return True
    except: pass
    return False

def run():
    print("--- СТАРТ ПРОВЕРКИ ---")
    all_configs = []
    
    for url in SOURCES:
        try:
            print(f"Загружаю: {url}")
            res = requests.get(url, timeout=20).text
            # Ищем ключи vless, vmess, ss
            found = re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res)
            print(f"Найдено в этом файле: {len(found)}")
            all_configs.extend(found)
        except Exception as e:
            print(f"Ошибка при чтении {url}: {e}")

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Всего уникальных ключей: {len(unique)}")

    if not unique:
        print("ОШИБКА: Ключи не найдены. Проверьте формат файлов.")
        return

    # Проверяем первые 500
    print("Начинаю проверку на доступность...")
    working = [c for c in unique[:500] if check_server(c)]
    print(f"Рабочих найдено: {len(working)}")

    if working:
        api_url = f"https://github.com{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        data = {"files": {TARGET_FILE: {"content": "\n".join(working)}}}
        
        r = requests.patch(api_url, headers=headers, json=data)
        if r.status_code == 200:
            print("ПОБЕДА! Gist обновлен.")
        else:
            print(f"Ошибка API: {r.status_code}")
    else:
        print("РЕЗУЛЬТАТ: Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
