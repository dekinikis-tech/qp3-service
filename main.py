import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Источники конфигов
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_ru_availability(host, port):
    """Проверка доступности порта через российский узел Check-Host"""
    try:
        # Запрашиваем проверку TCP порта из Москвы (ir1.check-host.net)
        url = f"https://check-host.net{host}:{port}&node=ir1.check-host.net"
        headers = {'Accept': 'application/json'}
        res = requests.get(url, headers=headers, timeout=10).json()
        
        # Даем сервису 3 секунды на выполнение теста
        time.sleep(3)
        
        # Получаем результат
        request_id = res.get('request_id')
        if not request_id: return False
        
        result_url = f"https://check-host.net{request_id}"
        check_res = requests.get(result_url, headers=headers, timeout=10).json()
        
        # Если хотя бы один запрос из РФ прошел (1 - успех)
        status = check_res.get('ir1.check-host.net')
        if status and status[0] and status[0].get('status') == 1:
            return True
    except:
        pass
    return False

def check_vps(config):
    conf_low = config.lower()
    # Фильтруем протоколы, которые лучше всего работают в РФ
    if 'vless' not in conf_low or ('reality' not in conf_low and 'vision' not in conf_low):
        return None

    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        # 1. Быстрая проверка сокетом (локально с GitHub), чтобы отсеять совсем мертвые
        with socket.create_connection((host, port), timeout=0.8):
            # 2. Глубокая проверка: доступен ли этот IP:PORT из России
            if check_ru_availability(host, port):
                return {"config": config}
    except:
        return None
    return None

def run():
    print("--- ЗАПУСК ФИЛЬТРАЦИИ С ПРОВЕРКОЙ ИЗ РФ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 120]))
    print(f"Всего в базе: {len(unique)} ключей. Начинаю проверку...")

    results = []
    # Важно: уменьшил потоки до 10, чтобы Check-Host не блокировал за частые запросы
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(check_vps, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: 
                results.append(res)
                print(f"Найдено рабочее соединение из РФ: {len(results)}")
            
            # Небольшая пауза для обхода лимитов API
            time.sleep(0.5)
    
    if results:
        final_list = [item['config'] for item in results[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Gist обновлен (найдено {len(results)} шт).")
        else:
            print("Файл vps.txt создан локально (MY_GIST_ID не найден).")
    else:
        print("Рабочих серверов для РФ не найдено.")

if __name__ == "__main__":
    run()
