import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Источники
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_for_rf(config):
    conf_low = config.lower()
    
    # 1. ПРИОРИТЕТ RU-МАСКИРОВКИ (SNI)
    # Если сервер притворяется российским сайтом, он пройдёт через фильтры РФ
    ru_marks = ['vk.com', 'x5.ru', 'ozon', 'avito', 'yandex', 'mail.ru', 'gosuslugi']
    has_ru_sni = any(mark in conf_low for mark in ru_marks)
    
    # 2. Только Vision или Reality (база для РФ)
    if 'reality' not in conf_low and 'vision' not in conf_low:
        return None

    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        # 3. ТЕСТ: Если сервер в РФ, коннект из США будет долгим, но нам важен сам факт
        start = time.time()
        with socket.create_connection((host, port), timeout=0.5):
            ping = int((time.time() - start) * 1000)
            
            # Если есть RU-маскировка, мы верим этому серверу больше
            priority = 2 if has_ru_sni else 1
            if '95.163.' in host or '5.188.' in host: # Твои рабочие подсети
                priority = 3
                
            return {"config": config, "ping": ping, "priority": priority}
    except: return None

def run():
    print("--- ФИЛЬТРАЦИЯ С УЧЕТОМ РФ-СПЕЦИФИКИ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 120]))
    print(f"Всего ключей: {len(unique)}. Ищу RU-адаптированные...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_for_rf, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Сортировка по приоритету (RU маскировка и подсети в топе)
    results.sort(key=lambda x: (-x['priority'], x['ping']))

    if results:
        # Выгружаем ТОП-15 самых перспективных для России
        final_list = [item['config'] for item in results[:15]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print(f"УСПЕХ! Найдено {len(results)} подходящих серверов. ТОП-15 в Gist.")
    else:
        print("Подходящих под критерии РФ серверов не найдено.")

if __name__ == "__main__":
    run()
