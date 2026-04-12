import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse, queue

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Бинарник будет доступен глобально благодаря твоему YAML
XRAY_BIN = "xray"

SOURCES = [
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']
BLOCKED_IPS = ('104.', '172.64.', '172.65.', '172.66.', '172.67.', '188.114.', '162.159.', '108.162.')
ALLOWED_PORTS = (443, 80, 8443, 2053, 2083, 2087, 2096) # Только стандартные порты (защита от РКН)

VLESS_REGEX = re.compile(
    r"vless://(?P<uuid>[^@]+)@(?P<host>[^:?#]+):(?P<port>\d+)\??(?P<query>[^#]+)?#?(?P<name>.*)?"
)

# Очередь портов для 40 потоков
MAX_WORKERS = 40
port_queue = queue.Queue()
for p in range(30000, 30000 + MAX_WORKERS):
    port_queue.put(p)

def test_via_xray(vless_url):
    port = port_queue.get()
    cfg_file = f"cfg_{port}.json"
    proc = None

    try:
        match = VLESS_REGEX.match(vless_url)
        if not match: return None
        data = match.groupdict()
        address = data['host']
        server_port = int(data['port'])
        
        # 🛡️ АНТИ-РКН ФИЛЬТРЫ:
        if ':' in address or address.startswith('['): return None # Убиваем IPv6
        if address.startswith(BLOCKED_IPS): return None           # Убиваем Cloudflare IP
        if server_port not in ALLOWED_PORTS: return None          # Убиваем странные порты
            
        query = urllib.parse.parse_qs(data.get('query') or '')
        def get_p(k, d=""): return query.get(k, [d])[0]
        
        sec = get_p('security', 'none')
        if sec != "reality": return None                          # ТОЛЬКО REALITY!
        
        sni = get_p('sni', get_p('host', address))
        net = get_p('type', 'tcp')
        
        stream_settings = {"network": net, "security": sec}
        
        if net == "ws":
            stream_settings["wsSettings"] = {"path": get_p("path", "/"), "headers": {"Host": get_p('host', address)}}
        elif net == "grpc":
            stream_settings["grpcSettings"] = {"serviceName": get_p("serviceName", "")}
            
        stream_settings["realitySettings"] = {
            "serverName": sni, 
            "fingerprint": get_p("fp", "chrome"), 
            "publicKey": get_p("pbk"), 
            "shortId": get_p("sid", ""),
            "spiderX": get_p("spx", "/")
        }
            
        config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": port, "protocol": "http", "settings": {"allowTransparent": False}}],
            "outbounds": [{
                "protocol": "vless", 
                "settings": {"vnext": [{"address": address, "port": server_port, "users": [{"id": data['uuid'], "encryption": "none", "flow": get_p("flow", "")}]}]}, 
                "streamSettings": stream_settings
            }]
        }
        
        with open(cfg_file, "w") as f: json.dump(config, f)
        
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        start_wait = time.time()
        port_ready = False
        while time.time() - start_wait < 1.5:
            if proc.poll() is not None: break
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                if s.connect_ex(('127.0.0.1', port)) == 0:
                    port_ready = True
                    break
            time.sleep(0.1)
            
        if not port_ready: return None
        
        proxies = {"http": f"http://127.0.0.1:{port}", "https": f"http://127.0.0.1:{port}"}
        
        session = requests.Session()
        session.trust_env = False 
        
        req_start = time.perf_counter()
        # Жесткий таймаут 2.0 секунды. Медленные отсеиваются.
        r = session.get("http://www.gstatic.com/generate_204", proxies=proxies, timeout=2.0)
        
        if r.status_code == 204: 
            ping = int((time.perf_counter() - req_start) * 1000)
            return (vless_url, ping)
            
    except Exception: 
        return None
    finally:
        if proc:
            try: 
                proc.kill()
                proc.wait(timeout=1)
            except Exception: pass
        if os.path.exists(cfg_file): 
            try: os.remove(cfg_file)
            except Exception: pass
        port_queue.put(port)

def run():
    print("--- ЗАПУСК ПРОВЕРКИ (Анти-РКН GitHub Actions Edition) ---")
    all_raw, headers = [], {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>]+', res)
            source_name = url.split('/')[-1] if '/' in url else url
            print(f"Источник: {source_name[:30]}... | Найдено: {len(found)}")
            all_raw.extend(found)
        except Exception: pass
            
    unique = list(set(all_raw))
    candidates = []
    for cfg in unique:
        if '#' in cfg:
            name = urllib.parse.unquote(cfg.split('#')[-1]).lower()
            if not any(bad in name for bad in BLACK_LIST): candidates.append(cfg)
        else: candidates.append(cfg)
        
    print(f"\nСобрано уникальных серверов: {len(candidates)}. Начинаем полную проверку...")
    
    results = []
    tested_count = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_via_xray, url): url for url in candidates}
        for future in concurrent.futures.as_completed(futures):
            tested_count += 1
            res = future.result()
            
            if tested_count % 200 == 0:
                print(f"  [Прогресс: {tested_count} / {len(candidates)}]")
                
            if res:
                url, ping = res
                results.append((ping, url))
                
    if results:
        # Сортировка от самых быстрых к медленным
        results.sort(key=lambda x: x[0])
        best_urls = [r[1] for r in results]
        
        print(f"\nИТОГ: Из {len(candidates)} серверов реально работают: {len(results)}.")
        
        with open(FILE_NAME, "w", encoding="utf-8") as f: 
            f.write("\n".join(best_urls[:40])) # Сохраняем ТОП-40
            
        if GID:
            print("Обновляем Gist...")
            # GitHub CLI подхватит GH_TOKEN из переменных окружения
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("Gist успешно обновлен.")
    else:
        print("\nК сожалению, ни один сервер не прошел проверку.")

if __name__ == "__main__":
    run()
