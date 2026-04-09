import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

# Список "безопасных" SNI для подмены, если в конфиге мусор
SAFE_SNIS = ["://samsung.com", "://microsoft.com", "://google.com"]

def check_vless_tls(config):
    try:
        parsed = urllib.parse.urlparse(config)
        host = parsed.hostname
        port = parsed.port
        if not host or not port: return None
        
        params = urllib.parse.parse_qs(parsed.query)
        # Пробуем взять SNI из конфига, если нет - ставим системный
        sni = params.get('sni', [None])[0] or params.get('peer', [None])[0] or "://microsoft.com"
        
        context = ssl._create_unverified_context()
        start = time.time()
        
        with socket.create_connection((host, port), timeout=3.5) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                ping = int((time.time() - start) * 1000)
                
                # НОВЫЙ ФИЛЬТР: от 10мс до 2500мс
                if 10 <= ping <= 2500:
                    # Добавляем в название сервера инфо о пинге для удобства в приложении
                    new_name = f"Ping_{ping}ms"
                    new_config = config.split('#')[0] + f"#{new_name}"
                    return {"config": new_config, "ping": ping}
    except:
        return None
    return None

def run():
    print("--- ПОИСК С ШИРОКИМ ДИАПАЗОНОМ ПИНГА ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 100]))
    results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=60) as executor:
        futures = {executor.submit(check_vless_tls, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # Сортируем от меньшего пинга к большему
    results.sort(key=lambda x: x['ping'])
    print(f"Найдено живых: {len(results)}")

    if results:
        # Берем топ 50 самых быстрых из найденных
        final_list = [item['config'] for item in results[:50]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("Готово! Проверь приложение.")
    else:
        print("Ничего не найдено.")

if __name__ == "__main__":
    run()
