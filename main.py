import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Добавляем источники, где чаще всего выкладывают именно Reality/Vision
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def is_vps_working_in_rf(config):
    """
    Ищем только те параметры, которые есть в твоих рабочих ссылках
    """
    conf_low = config.lower()
    
    # 1. СТРОЖАЙШИЙ ФИЛЬТР: Только Reality или Vision
    # Если в ссылке нет этих слов - она 100% не заработает у тебя сейчас
    if 'reality' not in conf_low and 'vision' not in conf_low:
        return None

    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        # 2. Проверка порта (от 50 до 600мс)
        start = time.time()
        with socket.create_connection((host, port), timeout=0.6):
            ping = int((time.time() - start) * 1000)
            if ping < 50 or ping > 600: return None
            
            return {"config": config, "ping": ping}
    except: return None

def run():
    print("--- ПОИСК REALITY & VISION (РФ СТАНДАРТ) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 100]))
    print(f"Всего ключей: {len(unique)}. Фильтруем 'элиту'...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(is_vps_working_in_rf, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    results.sort(key=lambda x: x['ping'])

    if results:
        # Выгружаем ТОП-20 (нам не нужны сотни мусора)
        final_list = [item['config'] for item in results[:20]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print(f"УСПЕХ! Найдено {len(results)} серверов Reality/Vision. ТОП-20 в Gist.")
    else:
        print("Подходящих Reality серверов не найдено.")

if __name__ == "__main__":
    run()
