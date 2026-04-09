import requests
import os
import socket
import re

# Ссылки на источники
SOURCES = [
    "https://github.com",
    "https://github.com",
    "https://github.com"
]

def check_server(config):
    try:
        # Регулярка для поиска хоста и порта в vless/vmess/ss
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match:
            match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
            
        if match:
            host = match.group(1)
            port = int(match.group(2))
            # Быстрая проверка доступности порта
            with socket.create_connection((host, port), timeout=1.5):
                return True
    except:
        pass
    return False

def run():
    gist_id = os.environ.get('GIST_ID')
    token = os.environ.get('GIST_TOKEN')
    
    # Прямой адрес API для работы с Gists
    api_url = f"https://github.com{gist_id}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }

    print("--- Начинаю проверку ---")
    
    # 1. Получаем текущие файлы Gist
    try:
        g_res = requests.get(api_url, headers=headers).json()
        file_names = list(g_res['files'].keys())
        target_filename = file_names[0]
        print(f"Обновляем файл: {target_filename}")
    except Exception as e:
        print(f"Ошибка доступа к API Gist: {e}")
        return

    # 2. Собираем конфиги из всех источников
    all_configs = []
    for url in SOURCES:
        try:
            print(f"Загрузка: {url}")
            res = requests.get(url, timeout=10).text
            found = re.findall(r'(?:vless|vmess|ss)://[^\s]+', res)
            all_configs.extend(found)
        except Exception as e:
            print(f"Пропуск источника {url} из-за ошибки")

    unique_configs = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Уникальных ссылок найдено: {len(unique_configs)}")

    # 3. Чекаем серверы (первые 400 для скорости)
    working_configs = []
    for c in unique_configs[:400]:
        if check_server(c):
            working_configs.append(c)
    
    print(f"Рабочих найдено: {len(working_configs)}")

    if not working_configs:
        print("Ни одного рабочего сервера не найдено. Отмена обновления.")
        return

    # 4. Сохраняем результат
    content = "\n".join(working_configs)
    data = {"files": {target_filename: {"content": content}}}
    
    final_res = requests.patch(api_url, headers=headers, json=data)
    
    if final_res.status_code == 200:
        print("ГОТОВО! Gist успешно обновлен.")
    else:
        print(f"Ошибка обновления: {final_res.status_code}")

if __name__ == "__main__":
    run()
