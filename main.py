import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Оставим только самые мощные источники
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def is_vps_working_in_rf(config):
    conf_low = config.lower()
    
    # 1. ЖЕСТКИЙ ПАРАМЕТРИЧЕСКИЙ ФИЛЬТР
    # Ищем признаки "бронебойных" конфигов: XTLS Vision или gRPC с маскировкой
    has_vision = 'xtls-rprx-vision' in conf_low
    has_grpc = 'type=grpc' in conf_low
    has_reality = 'security=reality' in conf_low
    
    # Если это не Reality + (Vision или gRPC), то в 2026 году это скорее всего мусор
    if not (has_reality and (has_vision or has_grpc)):
        return None

    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        # 2. ПРОВЕРКА ПОРТА (диапазон 50-500мс)
        # Уменьшаем таймаут до 0.5, чтобы отсеять лагающие сервера
        start = time.time()
        with socket.create_connection((host, port), timeout=0.5):
            ping = int((time.time() - start) * 1000)
            if ping < 50 or ping > 500: return None
            
            # Дополнительный балл за маскировку под RU-сайты (как в твоих примерах)
            priority = 0
            if 'vk.com' in conf_low or 'x5.ru' in conf_low or 'ozon' in conf_low:
                priority = 1
            
            return {"config": config, "ping": ping, "priority": priority}
    except: return None

def run():
    print("--- ЗАПУСК УЛЬТРА-СИТО (Vision & gRPC) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 120]))
    print(f"Загружено {len(unique)} длинных ключей. Ищем XTLS Vision и gRPC...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(is_vps_working_in_rf, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Сортировка: Сначала те, что с RU-маскировкой, потом по пингу
    results.sort(key=lambda x: (-x['priority'], x['ping']))

    if results:
        # Выгружаем ТОП-15 (самые качественные)
        final_list = [item['config'] for item in results[:15]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print(f"УСПЕХ! Найдено {len(results)} элитных серверов. ТОП-15 в Gist.")
    else:
        print("Элитных серверов не найдено. Попробуй позже.")

if __name__ == "__main__":
    run()
