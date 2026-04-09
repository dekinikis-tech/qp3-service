import requests
import os
import socket
import re

# --- НАСТРОЙКИ ---
GID = os.environ.get('GIST_ID')
GTK = os.environ.get('GIST_TOKEN')
FILE_NAME = "vps.txt" 

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
            with socket.create_connection((host, port), timeout=1.2):
                return True
    except: pass
    return False

def run():
    print("--- СТАРТ ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=20).text
            found = re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res)
            all_configs.extend(found)
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Всего ключей: {len(unique)}")

    # Проверяем 500 штук
    working = [c for c in unique[:500] if check_server(c)]
    print(f"Рабочих найдено: {len(working)}")

    if working:
        # ЖЕСТКО ПРОПИСАННЫЙ АДРЕС API БЕЗ ПЕРЕМЕННЫХ В ХОСТЕ
        final_url = f"https://github.com{GID}"
        headers = {"Authorization": f"token {GTK}"}
        payload = {"files": {FILE_NAME: {"content": "\n".join(working)}}}
        
        r = requests.patch(final_url, headers=headers, json=payload)
        if r.status_code == 200:
            print("УСПЕХ! Gist обновлен.")
        else:
            print(f"Ошибка API: {r.status_code}")
    else:
        print("Рабочих нет.")

if __name__ == "__main__":
    run()
