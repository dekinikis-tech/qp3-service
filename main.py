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
        match = re.search(r'@([^:/]+):(\d+)', config)
        if not match:
            # Для Shadowsocks старого типа
            match = re.search(r'ss://[^@]+@([^:/]+):(\d+)', config)
        
        if match:
            host = match.group(1)
            port = int(match.group(2))
            with socket.create_connection((host, port), timeout=1):
                return True
    except:
        pass
    return False

def run():
    all_configs = []
    print("Загрузка источников...")
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            # Ищем всё, что похоже на vless://, vmess:// или ss://
            found = re.findall(r'(?:vless|vmess|ss)://[^\s]+', res)
            all_configs.extend(found)
        except Exception as e:
            print(f"Ошибка загрузки {url}: {e}")

    unique_configs = list(set([c.strip() for c in all_configs]))
    print(f"Найдено уникальных ключей: {len(unique_configs)}")
    
    # Проверяем первые 300 для теста, чтобы не ждать долго
    working_configs = []
    for c in unique_configs[:300]:
        if check_server(c):
            working_configs.append(c)
    
    print(f"Рабочих серверов найдено: {len(working_configs)}")

    if not working_configs:
        print("Рабочих серверов не найдено, Gist не обновлен.")
        return

    gist_id = os.environ['GIST_ID']
    token = os.environ['GIST_TOKEN']
    
    content = "\n".join(working_configs)
    headers = {"Authorization": f"token {token}"}
    
    # Название файла ВНУТРИ вашего Gist (должно быть точным)
    # По вашей ссылке файл называется '635b44b708e61127ccb3c672316590e5' или по умолчанию
    # Попробуем обновить первый доступный файл в этом Gist
    try:
        gist_data = requests.get(f"https://github.com{gist_id}", headers=headers).json()
        filename = list(gist_data['files'].keys())[0]
        
        data = {"files": {filename: {"content": content}}}
        res = requests.patch(f"https://github.com{gist_id}", headers=headers, json=data)
        if res.status_code == 200:
            print("Gist успешно обновлен!")
        else:
            print(f"Ошибка API: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"Ошибка при связи с Gist: {e}")

if __name__ == "__main__":
    run()
