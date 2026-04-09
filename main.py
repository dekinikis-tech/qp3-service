import requests
import os
import socket
from urllib.parse import urlparse

# Ссылки на источники
SOURCES = [
    "https://github.com",
    "https://github.com",
    "https://github.com"
]

def check_server(config):
    try:
        # Извлекаем адрес и порт для базовой проверки
        content = config.split('@')[-1].split('?')[0]
        host_port = content.split(':')
        host = host_port[0]
        port = int(host_port[1].split('#')[0])
        
        # Пробуем подключиться (таймаут 2 секунды)
        with socket.create_connection((host, port), timeout=2):
            return True
    except:
        return False

def run():
    all_configs = []
    print("Скачиваю серверы...")
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            all_configs.extend(res.splitlines())
        except: continue

    unique_configs = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Всего найдено: {len(unique_configs)}. Начинаю проверку...")
    
    # Ограничим проверку первыми 500 для скорости на GitHub, или уберите срез [:500]
    working_configs = [c for c in unique_configs if check_server(c)]
    
    gist_id = os.environ['GIST_ID']
    token = os.environ['GIST_TOKEN']
    
    content = "\n".join(working_configs)
    
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
    # Название файла в Gist должно совпадать с тем, что у вас там уже есть
    data = {"files": {"all-vpn.txt": {"content": content}}}
    
    response = requests.patch(f"https://github.com{gist_id}", headers=headers, json=data)
    
    if response.status_code == 200:
        print(f"Успех! В Gist отправлено {len(working_configs)} рабочих серверов.")
    else:
        print(f"Ошибка обновления Gist: {response.status_code}")

if __name__ == "__main__":
    run()
