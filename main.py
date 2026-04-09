import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Оставим только самые актуальные источники
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_vps(config):
    conf_low = config.lower()
    # Фильтруем только то, что работает в РФ (Reality/Vision)
    if 'vless' not in conf_low or 'reality' not in conf_low:
        return None

    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        start = time.time()
        # Жесткий таймаут 0.5с на уровне системы
        with socket.create_connection((host, port), timeout=0.5):
            ping = int((time.time() - start) * 1000)
            
            # Твой честный диапазон 50-600мс
            if ping < 50 or ping > 600:
                return None
            
            # Проверка RU-маскировки для приоритета
            priority = 1
            if any(s in conf_low for s in ['vk.com', 'x5.ru', 'ozon', 'sber', 'yandex']):
                priority = 2
            
            return {"config": config, "ping": ping, "priority": priority}
    except:
        return None

def run():
    print("--- ЗАПУСК ОПТИМИЗИРОВАННОЙ ПРОВЕРКИ ---")
    raw_data = []
    for url in SOURCES:
        try:
            print(f"Качаю источник: {url}")
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except Exception as e:
            print(f"Пропуск источника {url}: {e}")

    unique = list(set([c.strip() for c in raw_data if len(c) > 120]))
    print(f"Уникальных ключей: {len(unique)}. Начинаю быструю фильтрацию...")

    results = []
    # 60 потоков - золотая середина для GitHub Actions
    with concurrent.futures.ThreadPoolExecutor(max_workers=60) as executor:
        futures = {executor.submit(check_vps, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            try:
                res = future.result(timeout=2) # Лимит 2 секунды на возврат результата
                if res: results.append(res)
            except: continue
    
    # Сортировка по приоритету и пингу
    results.sort(key=lambda x: (-x['priority'], x['ping']))
    print(f"Найдено рабочих: {len(results)}")

    if results:
        # Берем ТОП-20 самых качественных
        final_list = [item['config'] for item in results[:20]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        print("Обновляю Gist через CLI...")
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print("УСПЕХ! Всё готово.")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
