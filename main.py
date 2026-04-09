import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

# Список стран, которые сейчас стабильнее всего работают из РФ
GOOD_LOCATIONS = ['NL', 'DE', 'FI', 'FR', 'KZ', 'TR', 'AE']

def get_ip_info(host):
    """Определяем страну IP-адреса через бесплатный API (без лимитов на малые запросы)"""
    try:
        # Если хост - домен, резолвим в IP
        ip = socket.gethostbyname(host)
        res = requests.get(f"https://ipapi.co{ip}/country/", timeout=5).text.strip()
        return res
    except:
        return None

def check_vps(config):
    conf_low = config.lower()
    # Оставляем только Reality/Vision (самое живучее в РФ)
    if 'vless' not in conf_low or ('reality' not in conf_low and 'vision' not in conf_low):
        return None

    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        # 1. Проверка физической доступности (сокет)
        start = time.time()
        with socket.create_connection((host, port), timeout=1.5):
            ping = int((time.time() - start) * 1000)
            
            # 2. Проверка локации (Гео-фильтр)
            country = get_ip_info(host)
            
            # Если страна в нашем списке "надежных" или не определилась
            if country in GOOD_LOCATIONS or country is None:
                return {"config": config, "ping": ping, "country": country}
    except:
        return None
    return None

def run():
    print("--- ЗАПУСК ГЕО-ФИЛЬТРАЦИИ ДЛЯ РФ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 120]))
    print(f"Всего в базе: {len(unique)} ключей. Фильтруем...")

    results = []
    # 50 потоков — золотая середина
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_vps, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: 
                results.append(res)
                print(f"Найдено: {res.get('country', '??')} | {res['ping']}ms")

    # Сортируем: сначала те, что из GOOD_LOCATIONS, потом по пингу
    results.sort(key=lambda x: (x['country'] not in GOOD_LOCATIONS, x['ping']))

    if results:
        final_list = [item['config'] for item in results[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Gist обновлен. Найдено {len(results)} подходящих серверов.")
        else:
            print("Файл vps.txt сохранен (GID не найден).")
    else:
        print("Ничего не найдено. Возможно, источники пусты или лежат.")

if __name__ == "__main__":
    run()
