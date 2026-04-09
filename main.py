import requests, os, socket, re, time, subprocess, concurrent.futures

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def ultra_check(config):
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if not match: return None
        
        host, port = match.group(1), int(match.group(2))
        
        # ШАГ 1: Очень быстрый TCP коннект
        start = time.time()
        with socket.create_connection((host, port), timeout=0.5):
            ping = int((time.time() - start) * 1000)
            
            # ШАГ 2: Пытаемся отправить реальный HTTP запрос на порт прокси
            # Живой сервер V2Ray/Xray часто настроен отклонять такие запросы, 
            # но сам факт быстрого ответа на прикладном уровне — признак жизни.
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.8)
            s.connect((host, port))
            # Посылаем типичный заголовок
            s.send(f"GET / HTTP/1.1\r\nHost: {host}\r\n\r\n".encode())
            
            # Ждем хоть какой-то ответ. Мертвый прокси промолчит или закроет сокет.
            response = s.recv(10)
            s.close()
            
            if not response: return None
            
            # Ограничиваем пинг до 350мс для РФ (всё что выше - мусор)
            if ping > 350: return None
            
            return {"link": config.split("#")[0], "ping": ping}
    except:
        return None

def run():
    print("--- ФИЛЬТРАЦИЯ: ТОЛЬКО ЖИВЫЕ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 40]))
    
    valid_servers = []
    # 150 потоков для тотальной зачистки
    with concurrent.futures.ThreadPoolExecutor(max_workers=150) as executor:
        futures = {executor.submit(ultra_check, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_servers.append(res)
    
    valid_servers.sort(key=lambda x: x['ping'])
    
    # Теперь мы не берем всё подряд. Мы берем только ТОП-20.
    # Если их будет 3000 - мы всё равно возьмем только 20 лучших.
    if valid_servers:
        top_results = valid_servers[:20]
        print(f"Из 4000 отобрано 20 лучших (Пинг до 350мс и ответ на запрос)")
        
        final_list = [f"{item['link']}#🚀_TOP_{i+1}_[{item['ping']}ms]" for i, item in enumerate(top_results)]
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print("УСПЕХ! В Gist теперь только 20 'ядерных' серверов.")
    else:
        print("Ни один сервер не прошел ультра-проверку.")

if __name__ == "__main__":
    run()
