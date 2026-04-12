import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse, queue

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray"

# 💎 "БЕЛЫЙ СПИСОК" SNI: Ищем сервера, которые маскируются только под эти домены.
# Это CDN-домены, которые провайдеры боятся блокировать.
ALLOWED_SNI_PATTERNS = [
    'gcdn.prod.globacdn.com',
    'www.speedtest.net',
    'www.visa.com',
    'www.apple.com',
    'www.microsoft.com',
    'cdn.discordapp.com'
]

SOURCES = [
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt"
]

VLESS_REGEX = re.compile(r"vless://(?P<uuid>[^@]+)@(?P<host>[^:?#]+):(?P<port>\d+)\??(?P<query>[^#]+)?#?(?P<name>.*)?")

MAX_WORKERS = 30
port_queue = queue.Queue()
for p in range(35000, 35000 + MAX_WORKERS):
    port_queue.put(p)

def test_via_xray(vless_url):
    port = port_queue.get()
    cfg_file = f"cfg_{port}.json"
    proc = None
    try:
        match = VLESS_REGEX.match(vless_url)
        if not match: return None
        data = match.groupdict()
        address, server_port = data['host'], int(data['port'])
        
        # --- ФИЛЬТР #1: Жесткие правила для обхода блокировок ---
        if ':' in address or address.startswith('['): return None # Только IPv4
        if server_port != 443: return None # Только стандартный HTTPS порт
            
        query = urllib.parse.parse_qs(data.get('query') or '')
        def get_p(k, d=""): return query.get(k, [d])[0]
        
        if get_p('security') != "reality": return None # Только Reality
        
        # --- ФИЛЬТР #2: ГЛАВНЫЙ. Проверяем, маскируется ли сервер под "белый" домен. ---
        sni = get_p('sni', get_p('host', address)).lower()
        if not any(pattern in sni for pattern in ALLOWED_SNI_PATTERNS):
            return None

        # --- Если все фильтры пройдены, начинаем тест ---
        config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": port, "protocol": "http"}],
            "outbounds": [{
                "protocol": "vless", 
                "settings": {"vnext": [{"address": address, "port": server_port, "users": [{"id": data['uuid'], "encryption": "none", "flow": get_p("flow")}]}]}, 
                "streamSettings": {"network": get_p('type', 'tcp'), "security": "reality", "realitySettings": {
                    "serverName": sni, "fingerprint": get_p("fp", "chrome"),
                    "publicKey": get_p("pbk"), "shortId": get_p("sid"), "spiderX": get_p("spx", "/")
                }}
            }]
        }
        
        with open(cfg_file, "w") as f: json.dump(config, f)
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Ожидаем старт порта (максимум 1.5 сек)
        ready, start_w = False, time.time()
        while time.time() - start_w < 1.5:
            if proc.poll() is not None: break
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    ready = True; break
            time.sleep(0.1)
        if not ready: return None
        
        proxies = {"http": f"http://127.0.0.1:{port}", "https": f"http://127.0.0.1:{port}"}
        session = requests.Session()
        session.trust_env = False 
        
        t1 = time.perf_counter()
        r1 = session.get("http://www.gstatic.com/generate_204", proxies=proxies, timeout=1.5)
        if r1.status_code == 204:
            ping = int((time.perf_counter() - t1) * 1000)
            return (vless_url, ping)
            
    except: return None
    finally:
        if proc:
            try: proc.kill(); proc.wait(timeout=0.5)
            except: pass
        if os.path.exists(cfg_file): os.remove(cfg_file)
        port_queue.put(port)

def run():
    print("--- ЗАПУСК ПРОВЕРКИ (v16: White List Only) ---")
    all_raw, headers = [], {'User-Agent': 'Mozilla/5.0'}
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10, headers=headers).text
            all_raw.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: pass
            
    unique_candidates = list(set(all_raw))
    print(f"Собрано из баз: {len(unique_candidates)}. Начинаем жесткую фильтрацию...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_via_xray, url): url for url in unique_candidates}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                results.append(res) # res = (url, ping)

    if results:
        results.sort(key=lambda x: x[1]) # Сортируем по пингу
        final_urls = [r[0] for r in results]
        
        print(f"\nНАЙДЕНО ЖЕЛЕЗОБЕТОННЫХ СЕРВЕРОВ: {len(final_urls)}.")
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_urls[:40]))
            
        if GID:
            print("Обновляем Gist...")
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("Gist успешно обновлен.")
    else:
        print("\nСегодня в базах не нашлось серверов, проходящих через Анти-РКН фильтр.")

if __name__ == "__main__":
    run()
