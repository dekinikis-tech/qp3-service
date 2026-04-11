import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Те самые источники
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

def check_real_handshake(config):
    """Имитация 'Проверки задержки', а не просто 'Проверки профиля'"""
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None])[0] or params.get('peer', [None])[0] or "://google.com"
        
        # Создаем контекст как у реального браузера
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        start = time.time()
        with socket.create_connection((host, port), timeout=2.5) as sock:
            # Пытаемся сделать TLS Handshake (это и есть 'задержка' в v2ray)
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # Если мы дошли сюда, значит сервер РЕАЛЬНО ответил данными
                ping = int((time.time() - start) * 1000)
                
                # Добавляем баллы за "правильные" для РФ параметры (из твоих примеров)
                priority = 0
                if any(x in config.lower() for x in ['vk.com', 'yandex', 'x5.ru', 'vision']):
                    priority = 100
                
                return {"config": config, "ping": ping, "priority": priority}
    except:
        return None

def run():
    print("--- РЕАЛЬНАЯ ПРОВЕРКА (HANDSHAKE TEST) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 60]))
    results = []

    # 100 потоков, проверяем честный TLS
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_real_handshake, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # Сортировка: сначала приоритетные по SNI, потом по пингу
    results.sort(key=lambda x: (-x['priority'], x['ping']))

    if results:
        # Берем ТОП-100, чтобы из них точно нашлось 30-40 рабочих на телефоне
        final_list = [item['config'] for item in results[:100]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Найдено реально живых: {len(results)}")
    else:
        print("Ни один сервер не прошел Handshake.")

if __name__ == "__main__":
    run()
