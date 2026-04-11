import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Расширенный список источников для максимального охвата
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

def check_server(config):
    try:
        # 1. Сразу отсекаем цифровой мусор (как на твоем скришоте)
        name = urllib.parse.unquote(config.split('#')[-1]) if '#' in config else ""
        if not name or name.isdigit() or len(name) < 3:
            return None

        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        if not host or not port: return None
        
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None])[0] or params.get('peer', [None])[0] or host
        security = params.get('security', [''])[0]

        # 2. Быстрая проверка TCP порта
        start = time.time()
        sock = socket.create_connection((host, port), timeout=2.5)
        
        # 3. TLS Handshake с эмуляцией браузера (для Reality)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        # Набор шифров как у Chrome
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384')
        
        with context.wrap_socket(sock, server_hostname=sni) as ssock:
            ping = int((time.time() - start) * 1000)
            
            # 4. Система баллов (Приоритет)
            score = 0
            if security == 'reality': score += 500 # Reality — топ
            if any(x in config.lower() for x in ['ru', 'varya', 'russia', 'vision']): score += 300
            
            return {"config": config, "ping": ping, "score": score}
    except:
        return None

def run():
    print("--- СУПЕР-ПОИСК РАБОЧИХ СЕРВЕРОВ ---")
    raw_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            # Ищем все vless ссылки
            found = re.findall(r'vless://[^\s\'"<>]+', res)
            raw_configs.extend(found)
            print(f"Из источника {url[:30]}... получено {len(found)}")
        except: continue

    # Чистим дубликаты
    unique_configs = list(set([c.strip() for c in raw_configs if len(c) > 50]))
    print(f"Всего уникальных после сбора: {len(unique_configs)}")

    results = []
    # 100 потоков для скорости
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_server, c): c for c in unique_configs}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # Сортировка: сначала по баллам (Reality и РФ), потом по пингу
    results.sort(key=lambda x: (-x['score'], x['ping']))

    if results:
        # Берем ТОП-100 лучших
        final_list = [item['config'] for item in results[:100]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            # Твой рабочий метод отправки
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Найдено живых: {len(results)}. В Gist улетели лучшие 100.")
    else:
        print("Критическая ошибка: Рабочих серверов не найдено вообще.")

if __name__ == "__main__":
    run()
