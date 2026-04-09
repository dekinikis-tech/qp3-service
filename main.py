import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt"
]

def get_priority(config):
    """Определяет 'крутость' сервера на основе твоих рабочих примеров"""
    score = 0
    conf_low = config.lower()
    # Приоритет за правильные домены маскировки
    if any(x in conf_low for x in ['vk.com', 'yandex', 'mail.ru', 'x5.ru', 'rbc.ru', 'workers.dev']):
        score += 50
    # Приоритет за современный протокол
    if 'vision' in conf_low:
        score += 30
    # Приоритет за Cloudflare
    if 'workers.dev' in conf_low or 'cloudflare' in conf_low:
        score += 20
    return score

def check_vless_pro(config):
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        if not host or not port: return None
        
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None]) or params.get('host', [None]) or "google.com"
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        try: context.set_alpn_protocols(['h2', 'http/1.1'])
        except: pass

        start = time.time()
        # Ставим 2.0 секунды, чтобы отсеять потенциальные "deadline"
        with socket.create_connection((host, port), timeout=2.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni if isinstance(sni, str) else sni[0]) as ssock:
                ping = int((time.time() - start) * 1000)
                
                # Сохраняем только если пинг вменяемый
                if 1 <= ping <= 800:
                    priority = get_priority(config)
                    return {"config": config, "ping": ping, "priority": priority}
    except:
        return None

def run():
    print("--- ГЛУБОКАЯ ФИЛЬТРАЦИЯ ПО ТВОИМ ПАРАМЕТРАМ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data]))
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_vless_pro, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # СОРТИРОВКА: сначала по приоритету (надежности), потом по пингу
    results.sort(key=lambda x: (-x['priority'], x['ping']))

    if results:
        # Забираем лучшие 50
        final_list = [item['config'] for item in results[:50]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Найдено живых: {len(results)}. Топ-50 загружен.")
    else:
        print("Живых серверов не найдено.")

if __name__ == "__main__":
    run()
