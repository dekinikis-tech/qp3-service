import requests
import os
import socket
import re

SOURCES = [
    "https://github.com",
    "https://github.com",
    "https://github.com"
]

def check_server(config):
    try:
        # Ищем хост и порт в разных форматах ссылок
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match:
            # Для Shadowsocks без @
            match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
            
        if match:
            host = match.group(1)
            port = int(match.group(2))
            with socket.create_connection((host, port), timeout=1.5):
                return True
    except:
        pass
    return False

def run():
    gist_id = os.environ['GIST_ID']
    token = os.environ['GIST_TOKEN']
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    # 1. Получаем список файлов из Gist, чтобы знать, что обновлять
    print("Получаю инфо о Gist...")
    g_res = requests.get(f"https://github.com{gist_id}", headers=headers).json()
    if 'files' not in g_res:
        print("Ошибка: не удалось найти файлы в Gist. Проверьте GIST_ID.")
        return
    
    # Берем имя первого файла в Gist (у вас это vps.txt)
    target_filename = list(g_res['files'].keys())[0]
    print(f"Буду обновлять файл: {target_filename}")

    # 2. Собираем конфиги
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            found = re.findall(r'(?:vless|vmess|ss)://[^\s]+', res)
            all_configs.extend(found)
        except: continue

    unique_configs = list(set([c.strip() for c in all_configs]))
    print(f"Найдено ключей: {len(unique_configs)}")

    # 3. Проверка (берем первые 500 для стабильности)
    working_configs = []
    for c in unique_configs[:500]:
        if check_server(c):
            working_configs.append(c)
    
    print(f"Рабочих: {len(working_configs)}")

    if not working_configs:
        print("Рабочих нет, отмена.")
        return

    # 4. Отправка в Gist
    content = "\n".join(working_configs)
    data = {"files": {target_filename: {"content": content}}}
    
    final_res = requests.patch(f"https://github.com{gist_id}", headers=headers, json=data)
    
    if final_res.status_code == 200:
        print("УРА! Gist успешно обновлен.")
    else:
        print(f"Ошибка API: {final_res.status_code}")

if __name__ == "__main__":
    run()
