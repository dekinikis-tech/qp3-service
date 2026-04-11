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

def is_alive(config):
    """Быстрая проверка порта. Если порт закрыт - сервер труп."""
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        # Тайм-аут 2 секунды - если порт не ответил, нам такой сервер не нужен
        with socket.create_connection((host, port), timeout=2.0):
            return True
    except:
        return False

def get_quality_score(config):
    score = 0
    c_low = config.lower()
    # Приоритет твоим доменам
    if any(domain in c_low for domain in WHITE_DOMAINS): score += 5000
    # Приоритет технологиям
    if 'xtls-rprx-vision' in c_low: score += 1000
    if 'security=reality' in c_low: score += 500
    return score

def is_garbage(config):
    name = urllib.parse.unquote(config.split('#')[-1]).strip() if '#' in config else ""
    # Фильтр: 3+ цифры подряд (0640), короткие имена, черный список
    if re.search(r'\d{3,}', name) or len(name) < 4 or any(bad in name.lower() for bad in BLACK_LIST):
        return True
    return False

def run():
    print("--- СБОР И АВТО-ФИЛЬТРАЦИЯ МЕРТВЫХ ---")
    all_raw = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=12, headers=headers).text
            all_raw.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set(all_raw))
    print(f"Найдено в источниках: {len(unique)}")

    # 1. Сначала отбираем потенциально крутые и чистые сервера
    candidates = []
    for cfg in unique:
        if not is_garbage(cfg):
            score = get_quality_score(cfg)
            if score > 0:
                candidates.append({"config": cfg, "score": score})

    # Сортируем, чтобы проверять в первую очередь самых лучших
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    # 2. Проверяем только топ-70 кандидатов на "живость", чтобы не тратить время
    real_alive = []
    print(f"Проверяем доступность топ-{len(candidates[:70])} серверов...")
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        # Запускаем проверку порта
        check_tasks = {executor.submit(is_alive, item["config"]): item for item in candidates[:70]}
        for future in concurrent.futures.as_completed(check_tasks):
            item = check_tasks[future]
            if future.result(): # Если порт открыт
                real_alive.append(item)

    # 3. Финальная сортировка по качеству
    real_alive.sort(key=lambda x: x['score'], reverse=True)

    if real_alive:
        # Берем ТОП-30 реально живых и качественных
        to_save = [x['config'] for x in real_alive[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(to_save))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! В Gist улетели {len(to_save)} живых элитных серверов.")
    else:
        print("Живых серверов после проверки порта не найдено.")

if __name__ == "__main__":
    run()
