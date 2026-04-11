import requests, os, re, subprocess, urllib.parse, socket, concurrent.futures, time

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
        "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', 'node', '4Jadi' ]
WHITE_DOMAINS = []

def is_garbage(config):
    try:
        name = urllib.parse.unquote(config.split('#')[-1]).strip().lower()
        if not name or len(name) < 4: return True
        if name.isdigit(): return True
        if any(bad in name for bad in BLACK_LIST): return True
        if len(re.findall(r'\d', name)) > 5: return True
        return False
    except:
        return True

def get_tech_score(config):
    """Оценка технологий: Vision — самый важный параметр"""
    score = 0
    c_low = config.lower()
    
    # ПРИОРИТЕТ 1: XTLS Vision (то, что ты просил)
    if 'xtls-rprx-vision' in c_low: 
        score += 2000
    
    # ПРИОРИТЕТ 2: Твои белые домены
    if any(domain in c_low for domain in WHITE_DOMAINS): 
        score += 5000
        
    # ПРИОРИТЕТ 3: Reality
    if 'security=reality' in c_low: 
        score += 1000
        
    return score

def check_ping_fast(config_item):
    try:
        config = config_item["config"]
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        
        start = time.time()
        with socket.create_connection((host, port), timeout=2.0):
            ms = int((time.time() - start) * 1000)
            config_item["ping"] = ms
            return config_item
    except:
        return None

def run():
    print("--- СБОР И АНАЛИЗ VISION + REALITY ---")
    all_raw = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>]+', res)
            all_raw.extend(found)
        except: continue

    unique = list(set(all_raw))
    print(f"Всего уникальных: {len(unique)}")

    candidates = []
    for cfg in unique:
        if not is_garbage(cfg):
            # Мы берем только те, где есть Vision или Reality или наши домены
            # Обычный голый VLESS нам не нужен
            score = get_tech_score(cfg)
            if score > 0:
                candidates.append({
                    "config": cfg, 
                    "tech_score": score, 
                    "ping": 9999
                })

    print(f"Кандидатов с нужными протоколами: {len(candidates)}")
    
    real_alive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(check_ping_fast, item) for item in candidates]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: real_alive.append(res)

    # СОРТИРОВКА: Сначала по ТЕХНОЛОГИЯМ (чтобы Vision был в топе), потом по ПИНГУ
    # Это гарантирует, что ты получишь самые стабильные сервера из самых быстрых
    real_alive.sort(key=lambda x: (-x['tech_score'], x['ping']))

    if real_alive:
        # Оставляем ТОП-30 лучших
        to_save = [x['config'] for x in real_alive[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(to_save))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! В Gist улетели ТОП-30 Vision/Reality серверов.")
    else:
        print("Ни один современный сервер не прошел проверку.")

if __name__ == "__main__":
    run()
