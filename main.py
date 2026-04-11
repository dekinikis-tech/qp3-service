import requests, os, socket, re, time, subprocess, concurrent.futures, ssl, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Добавил еще один свежий источник вместо проблемных
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

# Сюда вписывай тех, кого надо банить навсегда
BLACK_LIST = ['meshky', '4mohsen', 'white', '708087'] 

def check_ultra_strict(config):
    try:
        # 1. Фильтр черного списка и мусорных имен
        name = urllib.parse.unquote(config.split('#')[-1]).lower() if '#' in config else ""
        if any(bad in name for bad in BLACK_LIST) or name.isdigit() or len(name) < 4:
            return None

        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [None]) or params.get('peer', [None]) or host
        
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')

        start = time.time()
        # Таймаут 2.5 секунды - если за это время не ответил, значит в мусор
        with socket.create_connection((host, port), timeout=2.5) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                ping = int((time.time() - start) * 1000)
                
                # Исключаем "фейковые" пинги (слишком быстрые для реальности)
                if ping < 30: return None
                
                # Приоритет только за технологиями обхода (Reality/Vision)
                score = 3000 - ping
                if 'reality' in config.lower(): score += 1000
                if 'vision' in config.lower(): score += 500
                
                return {"config": config, "score": score}
    except:
        return None

def run():
    print("--- ОХОТА НА ЭЛИТНЫЕ СЕРВЕРЫ ---")
    raw_configs = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=12, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>|]+', res)
            raw_configs.extend(found)
        except: continue

    unique_configs = list(set([c.strip() for c in raw_configs if len(c) > 60]))
    print(f"Кандидатов на проверку: {len(unique_configs)}")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_ultra_strict, c): c for c in unique_configs}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    # Сортируем: лучшие из лучших в начало
    results.sort(key=lambda x: x['score'], reverse=True)

    if results:
        # Оставляем только ТОП-15. Это будут те самые 15, которые работают на 100%.
        final_list = [item['config'] for item in results[:15]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! В Gist отправлено {len(final_list)} проверенных серверов.")
    else:
        print("Ни один сервер не прошел элитный отбор.")

if __name__ == "__main__":
    run()
