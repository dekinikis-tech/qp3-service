import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Твои основные источники
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_vps(config):
    conf_low = config.lower()
    # Берем только то, что имеет шансы в РФ (Reality/Vision)
    if 'vless' not in conf_low or ('reality' not in conf_low and 'vision' not in conf_low):
        return None

    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        start = time.time()
        # Попытка подключения
        with socket.create_connection((host, port), timeout=0.6):
            ping = int((time.time() - start) * 1000)
            
            # Твой фильтр: от 50 до 600мс
            if ping < 50 or ping > 600:
                return None
            
            return {"config": config, "ping": ping}
    except:
        return None

def run():
    print("--- ПОЛНАЯ АВТОМАТИЧЕСКАЯ ФИЛЬТРАЦИЯ БАЗЫ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 120]))
    print(f"Всего в базе: {len(unique)} ключей. Начинаю тотальную проверку...")

    results = []
    # 150 потоков для скорости
    with concurrent.futures.ThreadPoolExecutor(max_workers=150) as executor:
        futures = {executor.submit(check_vps, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    results.sort(key=lambda x: x['ping'])
    print(f"Найдено рабочих: {len(results)}")

    if results:
        # Выгружаем ТОП-30 самых быстрых
        final_list = [item['config'] for item in results[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print(f"УСПЕХ! Твой Gist обновлен лучшими серверами.")
    else:
        print("Рабочих серверов в базе не найдено.")

if __name__ == "__main__":
    run()
