import requests, os, re, subprocess, urllib.parse, socket, concurrent.futures, time

# Константы из твоего окружения
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Твои проверенные источники
SOURCES = [
        "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

# Черный список на основе твоих скриншотов
BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', 'node']
WHITE_DOMAINS = ['union.monster', 'tcpnet.fun', 'mutabor-sec.ru', 'whoshere.site', 'deepseek', 'vpnsz.net']

def is_garbage(config):
    """Жесткий фильтр мусора: убирает цифры, Anycast, Oneclick и прочий шлак"""
    try:
        name = urllib.parse.unquote(config.split('#')[-1]).strip().lower()
        # 1. Если имени нет или оно короче 4 символов
        if not name or len(name) < 4: return True
        # 2. Если имя состоит только из цифр (0640, 1122 и т.д.)
        if name.isdigit(): return True
        # 3. Проверка по черному списку
        if any(bad in name for bad in BLACK_LIST): return True
        # 4. Если в имени слишком много цифр (например, 50@oneclick...)
        if len(re.findall(r'\d', name)) > 5: return True
        return False
    except:
        return True

def get_tech_score(config):
    """Оценка элитности конфига по твоим рабочим примерам"""
    score = 0
    c_low = config.lower()
    # Твои эталонные домены - высший приоритет
    if any(domain in c_low for domain in WHITE_DOMAINS): score += 5000
    # Технологии XTLS Vision и Reality
    if 'xtls-rprx-vision' in c_low: score += 1000
    if 'security=reality' in c_low: score += 500
    return score

def check_ping_fast(config_item):
    """Быстрый замер пинга порта без лишних проверок"""
    try:
        config = config_item["config"]
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        
        start = time.time()
        # Таймаут 2 секунды - если порт не ответил, сервер в мусор
        with socket.create_connection((host, port), timeout=2.0):
            ms = int((time.time() - start) * 1000)
            config_item["ping"] = ms
            return config_item
    except:
        return None

def run():
    print("--- ЗАПУСК ПОЛНОГО СКАНЕРА (КАЧЕСТВО + ПИНГ) ---")
    all_raw = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    # 1. Сбор всех ссылок из всех источников
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>]+', res)
            all_raw.extend(found)
            print(f"Источник: {url[:35]}... | Собрано: {len(found)}")
        except: continue

    unique = list(set(all_raw))
    print(f"Всего уникальных ссылок: {len(unique)}")

    # 2. Первичный фильтр мусора по именам
    candidates = []
    for cfg in unique:
        if not is_garbage(cfg):
            candidates.append({
                "config": cfg, 
                "tech_score": get_tech_score(cfg), 
                "ping": 9999
            })

    print(f"Кандидатов после чистки имен: {len(candidates)}")
    
    # 3. Массовая проверка пинга (безлимитно по всему списку)
    real_alive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(check_ping_fast, item) for item in candidates]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: real_alive.append(res)

    print(f"Живых серверов найдено: {len(real_alive)}")

    # 4. Финальная сортировка: Сначала по ПИНГУ, затем по ТЕХНОЛОГИЯМ
    # Самые быстрые и качественные сервера будут первыми
    real_alive.sort(key=lambda x: (x['ping'], -x['tech_score']))

    if real_alive:
        # Оставляем ТОП-30 лучших из лучших
        to_save = [x['config'] for x in real_alive[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(to_save))
            
        if GID:
            # Твой рабочий метод через GH CLI
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! В Gist улетело {len(to_save)} элитных серверов.")
    else:
        print("Ни один сервер не прошел проверку.")

if __name__ == "__main__":
    run()
