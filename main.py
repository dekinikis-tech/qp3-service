import requests, os, socket, re, time, subprocess, concurrent.futures

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_real_work(config):
    try:
        # Проверка на наличие защиты (Reality/TLS)
        is_modern = any(x in config.lower() for x in ['reality', 'tls', 'security=vless', 'flow=xtls'])
        
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        
        host, port = match.group(1), int(match.group(2))
        
        start = time.time()
        # Попытка подключения
        with socket.create_connection((host, port), timeout=0.8):
            ping = int((time.time() - start) * 1000)
            
            # Если сервер старый и тупит - в мусор
            if not is_modern and ping > 400: return None
            # Если сервер с Reality - даем шанс до 800мс
            if is_modern and ping > 800: return None
            
            return {"config": config, "ping": ping, "modern": is_modern}
    except: return None

def run():
    print("--- ФИЛЬТРАЦИЯ БЕЗ ПЕРЕИМЕНОВАНИЯ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 50]))
    print(f"Всего ключей: {len(unique)}")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_real_work, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Сортировка: сначала Reality, потом по пингу. 
    # Самые лучшие окажутся в самом верху Gist.
    results.sort(key=lambda x: (not x['modern'], x['ping']))

    if results:
        # Выгружаем ТОП-50 лучших (без изменения названий)
        final_list = [item['config'] for item in results[:50]]
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"УСПЕХ! В Gist выгружено {len(final_list)} оригинальных ссылок.")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
