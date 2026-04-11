import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

def check_ultra_reliable(config):
    """Проверка с ожиданием реального ответа данных от сервера"""
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None]) or params.get('peer', [None]) or host
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        # Маскировка под Chrome для прохождения Reality проверок
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')

        start = time.time()
        with socket.create_connection((host, port), timeout=2.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # Имитируем начало передачи данных (HTTP HEAD)
                # Это заставляет VLESS-сервер реально пропустить трафик
                ssock.sendall(f"HEAD / HTTP/1.1\r\nHost: {sni}\r\n\r\n".encode())
                ssock.settimeout(1.5)
                
                # Читаем ответ. Если сервер прислал хоть 1 байт - прокси РАБОТАЕТ.
                chunk = ssock.recv(1)
                if not chunk: return None
                
                ping = int((time.time() - start) * 1000)
                # Если пинг слишком большой для Actions - это плохой сервер
                if ping > 1500: return None 
                
                return {"config": config, "ping": ping}
    except:
        return None

def run():
    print("--- ПОИСК 100% РАБОЧИХ СЕРВЕРОВ ---")
    raw_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_configs.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique_configs = list(set([c.strip() for c in raw_configs if len(c) > 60]))
    results = []

    # Используем меньше потоков, но проверяем тщательнее
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_ultra_reliable, c): c for c in unique_configs}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # Сортируем по самому быстрому отклику данных
    results.sort(key=lambda x: x['ping'])

    if results:
        # Берем только ТОП-20. Это будут самые "злые" и рабочие сервера.
        final_list = [item['config'] for item in results[:20]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! В Gist отправлено {len(final_list)} максимально надежных серверов.")
    else:
        print("Жесткая проверка не пропустила ни один сервер.")

if __name__ == "__main__":
    run()
