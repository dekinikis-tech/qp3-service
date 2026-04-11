import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Твои проверенные источники
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

def check_simple(config):
    """Возвращаемся к самой легкой проверке, которая точно не блокируется"""
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, parsed.port
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None]) or params.get('peer', [None]) or host
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        start = time.time()
        with socket.create_connection((host, port), timeout=3.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                ping = int((time.time() - start) * 1000)
                return {"config": config, "ping": ping}
    except:
        return None

def run():
    print("--- СБОР ДАННЫХ ---")
    raw_configs = []
    for url in SOURCES:
        try:
            # Добавляем Headers, чтобы GitHub не забанили как бота
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(url, timeout=15, headers=headers).text
            
            # Расширенный поиск: ищем всё, что похоже на vless
            found = re.findall(r'vless://[^\s\'"<>|]+', res)
            print(f"Источник {url[:40]}... | Найдено: {len(found)}")
            raw_configs.extend(found)
        except Exception as e:
            print(f"Ошибка источника {url[:40]}: {e}")

    unique_configs = list(set([c.strip() for c in raw_configs if len(c) > 30]))
    print(f"Всего уникальных: {len(unique_configs)}")

    if not unique_configs:
        print("Критическая ошибка: Список ссылок пуст!")
        return

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_simple, c): c for c in unique_configs}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    results.sort(key=lambda x: x['ping'])

    if results:
        # Берем ТОП-50, этого за глаза хватит для идеальной работы
        final_list = [item['config'] for item in results[:50]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Найдено живых: {len(results)}. В Gist улетели ТОП-50.")
    else:
        print("Проверка не прошла: все найденные сервера не ответили.")

if __name__ == "__main__":
    run()
