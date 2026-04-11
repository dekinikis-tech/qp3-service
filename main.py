import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

def check_real_handshake(config):
    """Улучшенная проверка: теперь имитирует реальный запрос данных"""
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None])[0] or params.get('peer', [None])[0] or host
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        start = time.time()
        with socket.create_connection((host, port), timeout=2.5) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # ВОТ ТУТ УЛУЧШЕНИЕ: отправляем байты, чтобы сервер начал работать
                # Это заставляет v2rayNG видеть "задержку", а не просто открытый порт
                ssock.sendall(b"GET / HTTP/1.1\r\nHost: " + sni.encode() + b"\r\n\r\n")
                ssock.settimeout(1.0)
                ssock.recv(1) # Ждем ответный байт
                
                ping = int((time.time() - start) * 1000)
                priority = 0
                if any(x in config.lower() for x in ['vk.com', 'yandex', 'x5.ru', 'vision']):
                    priority = 100
                
                return {"config": config, "ping": ping, "priority": priority}
    except:
        return None

def run():
    print("--- ЗАПУСК ПРОВЕРКИ (КАК ТЫ ПРОСИЛ) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 60]))
    results = []

    # 100 потоков, как в твоем первом коде
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_real_handshake, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    results.sort(key=lambda x: (-x['priority'], x['ping']))

    if results:
        # Берем ТОП-100
        final_list = [item['config'] for item in results[:100]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            # Твой оригинальный способ отправки через GH CLI
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Отправлено в Gist. Найдено живых: {len(results)}")
    else:
        print("Ни один сервер не прошел проверку.")

if __name__ == "__main__":
    run()
