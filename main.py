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
        # Улучшенный поиск хоста и порта
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match:
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
    gist_id = os.environ.get('GIST_ID')
    token = os.environ.get('GIST_TOKEN')
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}

    print("--- Начинаю работу ---")
    
    # 1. Проверяем связь с Gist
    g_res = requests.get(f"https://github.com{gist_id}", headers=headers).json()
    if 'files' not in g_res:
        print(f"Ошибка доступа к Gist: {g_res}")
        return
    
    # Берем имя первого файла в Gist
    file_names = list(g_res['files'].keys())
    target_filename = file_names[0] 
    print(f"Целевой файл в Gist: {target_filename}")

    # 2. Собираем конфиги
    all_configs = []
    for url in SOURCES:
        try:
            print(f"Загружаю: {url}")
            res = requests.get(url, timeout=15).text
            found = re.findall(r'(?:vless|vmess|ss)://[^\s]+', res)
            all_configs.extend(found)
        except Exception as e:
            print(f"Ошибка загрузки {url}: {e}")

    unique_configs = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Найдено уникальных ключей: {len(unique_configs)}")

    # 3. Проверка (чекаем только первые 500 для теста)
    working_configs = []
    for c in unique_configs[:500]:
        if check_server(c):
            working_configs.append(c)
    
    print(f"Рабочих серверов после проверки: {len(working_configs)}")

    if not working_configs:
        print("Рабочих серверов не найдено. Обновление отменено.")
        return

    # 4. Обновляем Gist
    content = "\n".join(working_configs)
    data = {"files": {target_filename: {"content": content}}}
    
    update_res = requests.patch(f"https://github.com{gist_id}", headers=headers, json=data)
    
    if update_res.status_code == 200:
        print("БИНГО! Список успешно обновлен в Gist.")
    else:
        print(f"Ошибка при обновлении: {update_res.status_code}")
        print(update_res.text)

if __name__ == "__main__":
    run()
