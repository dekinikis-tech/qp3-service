import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Источники, где больше REALITY (самое живучее)
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_vless_tls(config):
    """Полноценная проверка TLS-рукопожатия для Reality/VLESS"""
    try:
        # Парсим конфиг
        parsed = urllib.parse.urlparse(config)
        host = parsed.hostname
        port = parsed.port
        params = urllib.parse.parse_qs(parsed.query)
        
        # SNI (Server Name Indication) - крайне важен для обхода блоков
        sni = params.get('sni', [None])[0] or params.get('peer', [None])[0] or "google.com"
        
        if not host or not port: return None

        # Создаем SSL контекст, который игнорирует проверку сертификата (для Reality это норма)
        context = ssl._create_unverified_context()
        
        start = time.time()
        # 1. TCP коннект
        with socket.create_connection((host, port), timeout=3) as sock:
            # 2. TLS коннект (имитируем рукопожатие)
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                ping = int((time.time() - start) * 1000)
                return {"config": config, "ping": ping}
    except:
        return None

def run():
    print("--- ГЛУБОКАЯ ПРОВЕРКА TLS HANDSHAKE ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            # Собираем только VLESS (Shadowsocks сейчас бесполезен)
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 100]))
    print(f"Загружено {len(unique)} потенциальных ключей. Начинаю тест...")

    results = []
    # 50 потоков достаточно для глубокой проверки
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_vless_tls, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                results.append(res)
                print(f"Пройден TLS Handshake: {len(results)}")

    results.sort(key=lambda x: x['ping'])

    if results:
        final_list = [item['config'] for item in results[:50]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("УСПЕХ: Gist обновлен проверенными ключами.")
    else:
        print("Ни один сервер не прошел проверку TLS. Возможно, пора обновить источники.")

if __name__ == "__main__":
    run()
