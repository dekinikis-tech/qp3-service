import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def get_priority_score(config):
    conf_low = config.lower()
    score = 0
    
    # 1. Протокол и безопасность (обязательно)
    if 'vless' not in conf_low or 'reality' not in conf_low:
        return -1
    
    # 2. Маскировка под RU-ресурсы (Топ приоритет)
    ru_domains = ['vk.com', 'x5.ru', 'ads.x5.ru', 'ozon.ru', 'avito.ru', 'yandex.ru', 
                  'mail.ru', 'gosuslugi.ru', 'sberbank.ru', 'tinkoff.ru', 'ok.ru']
    if any(domain in conf_low for domain in ru_domains):
        score += 50
        
    # 3. Рабочие подсети из твоего примера
    if any(ip in conf_low for ip in ['95.163.', '5.188.', '185.129.', '193.233.']):
        score += 30
        
    # 4. Приоритетные порты
    if ':7443' in conf_low or ':443' in conf_low:
        score += 10
        
    # 5. Протоколы передачи трафика
    if 'grpc' in conf_low or 'xtls-rprx-vision' in conf_low:
        score += 20

    return score

def check_vps(config):
    score = get_priority_score(config)
    if score < 0: return None

    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        host, port = match.group(1), int(match.group(2))
        
        start = time.time()
        # Таймаут 0.4 сек для отсева всего медленного
        with socket.create_connection((host, port), timeout=0.4):
            ping = int((time.time() - start) * 1000)
            return {"config": config, "ping": ping, "score": score}
    except: return None

def run():
    print("--- ДОРАБОТКА: ПРИОРИТЕТ RU-RESOURCES ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            links = re.findall(r'vless://[^\s\'"<>]+', res)
            # Берем по 500 последних из каждого источника (самые свежие)
            raw_data.extend(links[-500:])
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 120]))
    print(f"Собрано {len(unique)} свежих ключей. Ищу 'близнецов' рабочих серверов...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_vps, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Сортировка: сначала по баллу (score), потом по пингу
    results.sort(key=lambda x: (-x['score'], x['ping']))

    if results:
        # Выгружаем ТОП-20 (самые качественные по нашей новой шкале)
        final_list = [item['config'] for item in results[:20]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print(f"УСПЕХ! Найдено {len(results)} подходящих. ТОП-20 отправлены.")
    else:
        print("Ни один сервер не прошел по критериям.")

if __name__ == "__main__":
    run()
