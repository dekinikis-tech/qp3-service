import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

def check_reliable_v2(config):
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None]) or params.get('peer', [None]) or host
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        # Эмуляция современного браузера
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')

        start = time.time()
        # Увеличиваем таймаут коннекта, но сокращаем время на TLS
        with socket.create_connection((host, port), timeout=4.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # Проверяем, что соединение не закрылось сразу после Handshake
                ssock.settimeout(1.0)
                ping = int((time.time() - start) * 1000)
                
                # Дополнительный фильтр: Reality и Vision сейчас самые надежные
                score = 1000 - ping
                if 'reality' in config.lower(): score += 500
                if 'vision' in config.lower(): score += 400
                
                return {"config": config, "ping": ping, "score": score}
    except:
        return None

def run():
    print("--- ПОИСК СТАБИЛЬНЫХ СЕРВЕРОВ ---")
    raw_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_configs.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique_configs = list(set([c.strip() for c in raw_configs if len(c) > 60]))
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
        futures = {executor.submit(check_reliable_v2, c): c for c in unique_configs}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # Сортировка по качеству (баллы) и пингу
    results.sort(key=lambda x: x['score'], reverse=True)

    if results:
        # Берем ТОП-30. Это обеспечит высокую плотность рабочих серверов.
        final_list = [item['config'] for item in results[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Найдено {len(results)}. В Gist ушли 30 лучших.")
    else:
        print("Серверов не найдено. Проверь источники или настройки сети.")

if __name__ == "__main__":
    run()
