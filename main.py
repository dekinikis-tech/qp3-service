import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Источники, где лежат самые полные (со всеми параметрами) ссылки
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def is_vps_valid(config):
    conf_low = config.lower()
    
    # 1. СТРОГАЯ ПРОВЕРКА СОСТАВА ССЫЛКИ
    # Настоящая рабочая Reality ссылка ОБЯЗАНА иметь pbk и sid (как в твоих примерах)
    has_reality = 'security=reality' in conf_low
    has_pbk = 'pbk=' in conf_low
    has_sid = 'sid=' in conf_low
    has_vision = 'xtls-rprx-vision' in conf_low
    
    # Если это не Reality со всеми ключами и не Vision - это 100% мусор
    if not (has_reality and has_pbk and has_sid) and not has_vision:
        return None

    try:
        # Парсим хост и порт
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        start = time.time()
        # Проверка коннекта (строго 50-600мс)
        with socket.create_connection((host, port), timeout=0.5):
            ping = int((time.time() - start) * 1000)
            if ping < 50 or ping > 600: return None
            
            # Дополнительный балл за "правильный" SNI (как в твоих примерах)
            score = 0
            if any(x in conf_low for x in ['vk.com', 'rutube', 'x5.ru', 'perekrestok', 'yandex']):
                score += 100
            
            return {"config": config, "ping": ping, "score": score}
    except:
        return None

def run():
    print("--- ЗАПУСК ГЛУБОКОГО АНАЛИЗА ПАРАМЕТРОВ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            # Ищем только VLESS
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 150])) # Берем только длинные!
    print(f"Всего длинных ключей: {len(unique)}. Ищу полные Reality-конфиги...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
        futures = {executor.submit(is_vps_valid, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Сортировка: сначала по баллам (наличие RU SNI), потом по пингу
    results.sort(key=lambda x: (-x['score'], x['ping']))

    if results:
        # Выгружаем ТОП-20 самых полных и быстрых
        final_list = [item['config'] for item in results[:20]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print(f"УСПЕХ! В Gist ушли {len(final_list)} максимально полных конфигов.")
    else:
        print("Ни одного полного Reality-конфига не найдено.")

if __name__ == "__main__":
    run()
