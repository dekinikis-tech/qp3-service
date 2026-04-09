import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_vless_tls(config):
    try:
        parsed = urllib.parse.urlparse(config)
        host = parsed.hostname
        port = parsed.port
        if not host or not port: return None
        
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None]) or params.get('peer', [None]) or "://google.com"
        
        context = ssl._create_unverified_context()
        start = time.time()
        
        # Минимальный таймаут для сверхзвуковых серверов
        with socket.create_connection((host, port), timeout=2.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni[0] if isinstance(sni, list) else sni) as ssock:
                ping = int((time.time() - start) * 1000)
                
                # ФИЛЬТР: Только "сверхзвук" (от 0 до 50мс по меркам GitHub)
                if 0 <= ping <= 50:
                    return {"config": config, "ping": ping}
    except:
        return None
    return None

def run():
    print("--- ЗАПУСК: ПОИСК СВЕРХЗВУКОВЫХ СЕРВЕРОВ (0-50ms) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 100]))
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=80) as executor:
        futures = {executor.submit(check_vless_tls, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # Сортируем: самые быстрые в начало
    results.sort(key=lambda x: x['ping'])
    print(f"Найдено сверхзвуковых: {len(results)}")

    if results:
        # Берем ТОП-50 самых быстрых
        final_list = [item['config'] for item in results[:50]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Сверхзвуковой список обновлен.")
    else:
        print("Сверхзвуковых серверов не найдено. Попробуй расширить диапазон до 100мс.")

if __name__ == "__main__":
    run()
