import requests, os, re, subprocess, urllib.parse, socket, concurrent.futures, time

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

WHITE_DOMAINS = ['union.monster', 'tcpnet.fun', 'mutabor-sec.ru', 'whoshere.site', 'deepseek', 'vpnsz.net']
BLACK_LIST = ['meshky', '4mohsen', 'white', '708087']

def check_ping_fast(config_item):
    """Максимально быстрый замер пинга порта"""
    try:
        config = config_item["config"]
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        
        start = time.time()
        # Таймаут 2.0 секунды, чтобы не ждать безнадежных
        with socket.create_connection((host, port), timeout=2.0):
            ms = int((time.time() - start) * 1000)
            config_item["ping"] = ms
            return config_item
    except:
        return None

def is_garbage(config):
    """Жесткий фильтр мусора по именам"""
    name = urllib.parse.unquote(config.split('#')[-1]).strip() if '#' in config else ""
    if re.search(r'\d{3,}', name) or len(name) < 4 or any(bad in name.lower() for bad in BLACK_LIST):
        return True
    return False

def get_tech_score(config):
    """Приоритет технологиям обхода (для сортировки при равном пинге)"""
    c_low = config.lower()
    score = 0
    if any(domain in c_low for domain in WHITE_DOMAINS): score += 5000
    if 'xtls-rprx-vision' in c_low: score += 1000
    if 'security=reality' in c_low: score += 500
    return score

def run():
    print("--- ГЛОБАЛЬНЫЙ СКАНЕР ВСЕХ ИСТОЧНИКОВ ---")
    all_raw = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            all_raw.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set(all_raw))
    print(f"Всего ссылок в базе: {len(unique)}")

    # 1. Сначала фильтруем только по именам
    candidates = []
    for cfg in unique:
        if not is_garbage(cfg):
            candidates.append({"config": cfg, "tech_score": get_tech_score(cfg), "ping": 9999})

    print(f"Кандидатов после фильтрации имен: {len(candidates)}")
    print(f"Запускаем массовую проверку пинга в 100 потоков...")
    
    real_alive = []
    # Используем 100 потоков — это позволит прогнать 2000+ серверов очень быстро
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(check_ping_fast, item) for item in candidates]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: real_alive.append(res)

    print(f"Найдено живых серверов: {len(real_alive)}")

    # 2. ФИНАЛЬНАЯ СОРТИРОВКА:
    # Главный критерий теперь — ПИНГ (от меньшего к большему).
    # Если пинг одинаковый, смотрим на технологичность (Vision/Reality).
    real_alive.sort(key=lambda x: (x['ping'], -x['tech_score']))

    if real_alive:
        # Берем ТОП-30 самых быстрых из реально живых
        to_save = [x['config'] for x in real_alive[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(to_save))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! В Gist улетели 30 самых скоростных серверов.")
    else:
        print("Ни один сервер из всех источников не ответил.")

if __name__ == "__main__":
    run()
