import requests, os, socket, re, time, concurrent.futures, ssl, urllib.parse, subprocess

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

def check_real_handshake(config):
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [host])[0]

        # Создаем "тяжелый" контекст (имитация браузера)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        start = time.time()
        with socket.create_connection((host, port), timeout=3.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # ГЛАВНОЕ: Отправляем байты, чтобы заставить VLESS ответить
                # Это имитирует реальный запрос, который делает v2rayNG
                ssock.sendall(b"GET / HTTP/1.1\r\nHost: " + sni.encode() + b"\r\n\r\n")
                ssock.settimeout(1.5)
                # Если сервер прислал хоть что-то в ответ — он живой
                response = ssock.recv(5)
                ping = int((time.time() - start) * 1000)
                return {"config": config, "ping": ping}
    except:
        return None

def run():
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 60]))
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_real_handshake, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    results.sort(key=lambda x: x['ping'])

    if results:
        final_list = [item['config'] for item in results[:100]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
        
        if GID:
            # Обновление через официальный CLI GitHub
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"Готово! Найдено рабочих: {len(results)}")
    else:
        print("Живых серверов не найдено.")

if __name__ == "__main__":
    run()
