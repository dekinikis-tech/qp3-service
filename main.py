import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Источники, где больше всего таких "умных" конфигов
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_vps(config):
    conf_low = config.lower()
    
    # ФИЛЬТР: Ищем Reality/Vision или Cloudflare Workers
    is_reality = 'reality' in conf_low or 'xtls-rprx-vision' in conf_low
    is_worker = 'workers.dev' in conf_low or 'eu.org' in conf_low
    
    if not (is_reality or is_worker):
        return None

    try:
        # Извлекаем адрес и порт
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        # Начисляем баллы за "правильные" признаки
        score = 0
        if 'workers.dev' in conf_low: score += 50
        if any(ru in conf_low for ru in ['vk.com', 'rutube', 'perekrestok', 'x5.ru', 'yandex']): score += 100
        if 'xtls-rprx-vision' in conf_low: score += 30

        start = time.time()
        # Проверка коннекта (50-600мс)
        with socket.create_connection((host, port), timeout=0.5):
            ping = int((time.time() - start) * 1000)
            if ping < 50 or ping > 600: return None
            
            return {"config": config, "ping": ping, "score": score}
    except: return None

def run():
    print("--- ПОИСК 'УМНЫХ' КОНФИГОВ (WORKERS & RU-SNI) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 100]))
    print(f"Загружено {len(unique)} ключей. Фильтрую по твоим примерам...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
        futures = {executor.submit(check_vps, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Сортировка: Сначала по "похожести" (score), потом по пингу
    results.sort(key=lambda x: (-x['score'], x['ping']))

    if results:
        # Выгружаем ТОП-30 лучших
        final_list = [item['config'] for item in results[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print(f"УСПЕХ! В Gist выгружено {len(final_list)} серверов.")
    else:
        print("Ничего подходящего не найдено.")

if __name__ == "__main__":
    run()
