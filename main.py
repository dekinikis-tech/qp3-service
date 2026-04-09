import requests
import os
import socket
import re

# --- НАСТРОЙКИ ---
GIST_ID = os.environ.get('GIST_ID')
GIST_TOKEN = os.environ.get('GIST_TOKEN')
TARGET_FILE = "vps.txt" # Убедитесь, что файл в Gist называется именно так

# Сюда вставляйте любые ссылки на GitHub (скрипт сам их поправит)
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt"
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_server(config):
    try:
        # Ищем хост и порт (vless, vmess, ss)
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match:
            match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if match:
            host, port = match.group(1), int(match.group(2))
            # Проверка коннекта за 1 секунду
            with socket.create_connection((host, port), timeout=1):
                return True
    except: pass
    return False

def run():
    print("--- СТАРТ ПРОВЕРКИ ---")
    all_configs = []
    
    for url in SOURCES:
        try:
            # Исправляем ссылки github, если они не raw
            url = url.replace("github.com", "://githubusercontent.com").replace("/blob/", "/").replace("/raw/", "/")
            print(f"Читаю: {url}")
            
            res = requests.get(url, timeout=15).text
            # Ищем любые ключи в тексте
            found = re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res)
            all_configs.extend(found)
        except: continue

    unique = list(set([c.strip() for c in all_configs]))
    print(f"Всего найдено ключей: {len(unique)}")

    if not unique:
        print("ОШИБКА: Серверы не найдены в источниках!")
        return

    # Проверяем на доступность (первые 500 штук)
    print("Начинаю пинговать...")
    working = [c for c in unique[:500] if check_server(c)]
    print(f"Рабочих найдено: {len(working)}")

    if working:
        # Отправка в Gist
        api_url = f"https://github.com{GIST_ID}"
        headers = {"Authorization": f"token {GIST_TOKEN}"}
        data = {"files": {TARGET_FILE: {"content": "\n".join(working)}}}
        
        r = requests.patch(api_url, headers=headers, json=data)
        if r.status_code == 200:
            print("ПОБЕДА: Gist обновлен!")
        else:
            print(f"API Ошибка: {r.status_code}")
    else:
        print("РЕЗУЛЬТАТ: Все серверы из списка сейчас недоступны.")

if __name__ == "__main__":
    run()
