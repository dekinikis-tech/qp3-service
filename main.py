import requests, os, socket, re, time, subprocess, concurrent.futures, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt"
]

def get_priority(config):
    """Баллы за 'правильные' параметры из твоего списка"""
    score = 0
    c = config.lower()
    # Твои любимчики: SNI РФ и Cloudflare
    if any(x in c for x in ['vk.com', 'yandex', 'x5.ru', 'rbc.ru', 'mail.ru', 'yastatic']): score += 100
    if 'workers.dev' in c: score += 80
    # Протокол Vision
    if 'vision' in c: score += 50
    # Наличие Reality
    if 'reality' in c: score += 30
    return score

def check_vps(config):
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        if not host or not port: return None
        
        start = time.time()
        # Простая TCP проверка: если порт открыт - сервер ЖИВ для нас
        with socket.create_connection((host, port), timeout=2.5):
            ping = int((time.time() - start) * 1000)
            
            if 1 <= ping <= 800:
                priority = get_priority(config)
                return {"config": config, "ping": ping, "priority": priority}
    except:
        return None

def run():
    print("--- ГИБКИЙ ПОИСК С ПРИОРИТЕТОМ РАБОЧИХ ПАРАМЕТРОВ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 60]))
    print(f"Взято из источников: {len(unique)} ссылок.")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_vps, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # ГЛАВНОЕ: Сначала сортируем по ПРИОРИТЕТУ (нашим признакам), потом по ПИНГУ
    results.sort(key=lambda x: (-x['priority'], x['ping']))
    print(f"Найдено живых серверов: {len(results)}")

    if results:
        # Сохраняем ТОП-50 самых качественных
        final_list = [item['config'] for item in results[:50]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("УСПЕХ! Gist обновлен.")
    else:
        print("Ничего не найдено. Проверь интернет или SOURCES.")

if __name__ == "__main__":
    run()
