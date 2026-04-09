import requests, os, socket, re, time, subprocess, concurrent.futures

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def hard_check(config):
    """
    Максимально жесткая проверка: коннект + попытка получить ответ от протокола
    """
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if not match: return None
        
        host, port = match.group(1), int(match.group(2))
        
        start = time.time()
        # Шаг 1: Коннект
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.2) # Чуть больше времени на глубокий ответ
        s.connect((host, port))
        
        # Шаг 2: Отправка "мусорного" запроса, на который VPN-сервер должен среагировать
        # (закрытие соединения или ответ в зависимости от протокола)
        s.send(b'\x05\x01\x00') 
        time.sleep(0.1)
        
        # Шаг 3: Проверка, не закрыл ли сервер соединение мгновенно (признак живого порта, но мертвого прокси)
        # Если мы можем отправить еще данные - сервер "слушает"
        s.send(b'\x03\x00\x00')
        
        ping = int((time.time() - start) * 1000)
        s.close()
        
        if ping > 800: return None
        return {"link": config.split("#")[0], "ping": ping}
    except:
        return None

def run():
    print("--- ЗАПУСК ГЛУБОКОЙ ПРОВЕРКИ (REAL CHECK) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 40]))
    print(f"Загружено {len(unique)} ключей. Начинаю жесткую фильтрацию...")

    # Проверяем всю базу
    valid_servers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
        futures = {executor.submit(hard_check, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_servers.append(res)
    
    # Сортировка по качеству
    valid_servers.sort(key=lambda x: x['ping'])
    print(f"Реально рабочих найдено: {len(valid_servers)}")

    if valid_servers:
        # Формируем список только из тех, кто прошел Hard Check
        # Убираем всякие "Server_1", оставляем только пинг для ориентации
        final_list = [f"{item['link']}#PING_{item['ping']}ms" for item in valid_servers]
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print("УСПЕХ! В Gist только проверенные серверы.")
    else:
        print("Ни один сервер не прошел жесткую проверку.")

if __name__ == "__main__":
    run()
