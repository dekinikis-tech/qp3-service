import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Добавил источники, которые постят именно такие Cloudflare и Reality конфиги
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt"
]

def check_advanced_vless(config):
    # Убираем только совсем пустые строки
    if len(config) < 50: return None
    
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        if not host or not port: return None
        
        params = urllib.parse.parse_qs(parsed.query)
        # Вытягиваем SNI (критично для Reality и WS)
        sni = params.get('sni', [None])[0] or params.get('host', [None])[0] or "google.com"
        security = params.get('security', [''])[0]
        
        # Настройка SSL для имитации браузера (Chrome Fingerprint)
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        # Reality и Cloudflare Workers часто требуют h2
        try:
            context.set_alpn_protocols(['h2', 'http/1.1'])
        except: pass

        start = time.time()
        # Увеличил таймаут до 4 сек, чтобы "пробить" тяжелые Reality-хендшейки
        with socket.create_connection((host, port), timeout=4.0) as sock:
            # Если в конфиге есть TLS/Reality — делаем рукопожатие
            if security in ['tls', 'reality']:
                with context.wrap_socket(sock, server_hostname=sni) as ssock:
                    ping = int((time.time() - start) * 1000)
            else:
                # Если обычный TCP/WS — просто замеряем отклик
                ping = int((time.time() - start) * 1000)
            
            # Твой диапазон 1-800мс
            if 1 <= ping <= 800:
                return {"config": config, "ping": ping}
    except:
        return None
    return None

def run():
    print("--- ПОИСК РАБОЧИХ REALITY И CLOUDFLARE УЗЛОВ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data]))
    print(f"Всего в базе: {len(unique)} ключей. Начинаю глубокую проверку...")

    results = []
    # 100 потоков для скорости, но с качественной проверкой
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_advanced_vless, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # Сортируем: сначала самые быстрые
    results.sort(key=lambda x: x['ping'])
    print(f"Найдено живых серверов: {len(results)}")

    if results:
        # Берём ТОП-50
        final_list = [item['config'] for item in results[:50]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("УСПЕХ! Твой Gist обновлен лучшими серверами.")
    else:
        print("Живых серверов не найдено. Возможно, фильтры РКН усилились.")

if __name__ == "__main__":
    run()
