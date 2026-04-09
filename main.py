import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
   "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
"https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_vless_tls(config):
    if "[openRay]" in config: return None
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        if not host or not port: return None
        
        params = urllib.parse.parse_qs(parsed.query)
        # Извлекаем SNI, если нет - ставим дефолт
        sni = params.get('sni', [None])[0] or params.get('peer', [None])[0] or "://google.com"
        
        # СОЗДАЕМ ГИБКИЙ SSL-КОНТЕКСТ
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        # Добавляем ALPN, так как многие Reality серверы без него сбрасывают связь
        context.set_alpn_protocols(['h2', 'http/1.1'])
        
        start = time.time()
        with socket.create_connection((host, port), timeout=3.5) as sock:
            # Выполняем само TLS-рукопожатие
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                ping = int((time.time() - start) * 1000)
                
                # Твой диапазон 1-800мс
                if 1 <= ping <= 800:
                    return {"config": config, "ping": ping}
    except:
        return None
    return None

def run():
    print("--- ГЛУБОКИЙ ТЕСТ TLS (1-800 MS, БЕЗ OPENRAY) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 100]))
    print(f"Загружено: {len(unique)} ссылок. Проверяю...")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_vless_tls, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    results.sort(key=lambda x: x['ping'])
    print(f"Найдено живых (TLS OK): {len(results)}")

    if results:
        final_list = [item['config'] for item in results[:200]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("Успех! Gist обновлен.")
    else:
        print("0 серверов прошли TLS. Проверь SNI или источники.")

if __name__ == "__main__":
    run()
