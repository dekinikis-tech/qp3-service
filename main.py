import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Добавил еще пару источников, чтобы было из чего выбирать лучшие 20
SOURCES = [
        "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

def check_perfect_server(config):
    """Максимально строгая проверка на выживаемость"""
    try:
        # Фильтр мусорных имен (цифры и коротыши)
        name = urllib.parse.unquote(config.split('#')[-1]) if '#' in config else ""
        if name.isdigit() or len(name) < 3:
            return None

        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None])[0] or params.get('peer', [None])[0] or host
        
        # Создаем контекст, который требует от сервера реальной работы
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE 
        # Маскировка под TLS Chrome
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')

        start = time.time()
        # Даем серверу 3 секунды на ответ (для надежности)
        with socket.create_connection((host, port), timeout=3.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # Если мы дошли сюда, TLS Handshake завершен успешно
                ping = int((time.time() - start) * 1000)
                
                # ЖЕСТКИЙ ОТБОР: если дата-центр видит пинг > 1200мс, 
                # для твоего телефона это будет лагающий мусор. Выкидываем.
                if ping > 1200: return None
                
                # Вес сервера (Reality в приоритете)
                score = 2000 - ping
                if 'reality' in config.lower(): score += 1000
                if 'vision' in config.lower(): score += 500
                
                return {"config": config, "score": score}
    except:
        return None

def run():
    print("--- ЗАПУСК ЭЛИТНОЙ ПРОВЕРКИ (20 из 20) ---")
    raw_configs = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>|]+', res)
            raw_configs.extend(found)
        except: continue

    unique_configs = list(set([c.strip() for c in raw_configs if len(c) > 60]))
    print(f"Собрано кандидатов: {len(unique_configs)}")

    results = []
    # Снижаем потоки до 40 для более стабильной проверки каждого сервера
    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
        futures = {executor.submit(check_perfect_server, c): c for c in unique_configs}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # Сортировка по качеству
    results.sort(key=lambda x: x['score'], reverse=True)

    if results:
        # Берем только ТОП-25 самых надежных (с запасом под 20 рабочих)
        final_list = [item['config'] for item in results[:25]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"ГОТОВО! В Gist ушли {len(final_list)} элитных серверов.")
    else:
        print("Ни один сервер не прошел строгий отбор.")

if __name__ == "__main__":
    run()

