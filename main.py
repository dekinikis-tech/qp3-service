import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse, queue

# --- НАСТРОЙКИ (Как в твоей оригинальной версии) ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray"

SOURCES = [
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']
BLOCKED_IPS = ('104.', '172.64.', '172.65.', '172.66.', '172.67.', '188.114.', '162.159.', '108.162.')

VLESS_REGEX = re.compile(r"vless://(?P<uuid>[^@]+)@(?P<host>[^:?#]+):(?P<port>\d+)\??(?P<query>[^#]+)?#?(?P<name>.*)?")

# 🛠️ ГЛАВНОЕ ИСПРАВЛЕНИЕ: Жесткая очередь портов для идеальной изоляции потоков
MAX_WORKERS = 50
port_queue = queue.Queue()
for p in range(25000, 25000 + MAX_WORKERS):
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
        
        # Только базовые фильтры из твоего оригинального кода
        if address.startswith(BLOCKED_IPS): return None
        if ':' in address: return None # Простой, но эффективный фильтр IPv6
            
        query = urllib.parse.parse_qs(data.get('query') or '')
        def get_p(k, d=""): return query.get(k, [d])[0]
        
        sni = get_p('sni', get_p('host', address))
        net = get_p('type', 'tcp')
        sec = get_p('security', 'none')
        
        stream_settings = {"network": net, "security": sec}
        if net == "ws":
            stream_settings["wsSettings"] = {"path": get_p("path", "/"), "headers": {"Host": get_p('host', address)}}
        elif net == "grpc":
            stream_settings["grpcSettings"] = {"serviceName": get_p("serviceName", "")}
        if sec == "reality":
            stream_settings["realitySettings"] = {"serverName": sni, "fingerprint": get_p("fp", "chrome"), "publicKey": get_p("pbk"), "shortId": get_p("sid"), "spiderX": get_p("spx", "/")}
        elif sec == "tls":
            stream_settings["tlsSettings"] = {"serverName": sni, "fingerprint": get_p("fp", "chrome"), "alpn": ["h2", "http/1.1"]}

        config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": port, "protocol": "http"}],
            "outbounds": [{"protocol": "vless", "settings": {"vnext": [{"address": address, "port": server_port, "users": [{"id": data['uuid'], "encryption": "none", "flow": get_p("flow")}]}]}, "streamSettings": stream_settings}]
        }
        
        with open(cfg_file, "w") as f: json.dump(config, f)
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Умное ожидание порта
        ready, start_w = False, time.time()
        while time.time() - start_w < 1.5:
            if proc.poll() is not None: break
            import socket
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.1)
                if s.connect_ex(('127.0.0.1', port)) == 0: ready = True; break
            time.sleep(0.1)
        if not ready: return None
        
        proxies = {"http": f"http://127.0.0.1:{port}", "https": f"http://127.0.0.1:{port}"}
        session = requests.Session()
        session.trust_env = False
        
        t1 = time.perf_counter()
        # Стандартная проверка с жестким таймаутом
        r1 = session.get("http://www.gstatic.com/generate_204", proxies=proxies, timeout=2.0)
        if r1.status_code == 204:
            ping = int((time.perf_counter() - t1) * 1000)
            return (vless_url, ping)
            
    except: return None
    finally:
        if proc:
            try: proc.kill(); proc.wait(timeout=0.5)
            except: pass
        if os.path.exists(cfg_file): os.remove(cfg_file)
        port_queue.put(port) # Возвращаем порт в очередь

def run():
    print("--- ЗАПУСК ПРОВЕРКИ (v17: Восстановленная логика + Рейтинг) ---")
    all_raw, headers = [], {'User-Agent': 'Mozilla/5.0'}
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10, headers=headers).text
            all_raw.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: pass
            
    # Фильтруем по BLACK_LIST, как в твоем оригинальном коде
    unique = list(set(all_raw))
    candidates = []
    for cfg in unique:
        if '#' in cfg:
            name = urllib.parse.unquote(cfg.split('#')[-1]).lower()
            if not any(bad in name for bad in BLACK_LIST): candidates.append(cfg)
        else: candidates.append(cfg)
        
    print(f"\nСобрано уникальных серверов: {len(candidates)}. Начинаем ПОЛНУЮ проверку...")
    print("Это займет время, но результат будет честным.\n")
    
    results = []
    tested_count = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # 🔥 ПРОВЕРЯЕМ ВСЕХ КАНДИДАТОВ, БЕЗ РАНДОМА
        futures = {executor.submit(test_via_xray, url): url for url in candidates}
        for future in concurrent.futures.as_completed(futures):
            tested_count += 1
            if tested_count % 200 == 0:
                print(f"  [Прогресс: {tested_count} / {len(candidates)}]")
            res = future.result()
            if res:
                results.append(res) # res = (url, ping)

    if results:
        # 🔥 СОРТИРУЕМ ПО ПИНГУ И ВЫДАЕМ ЛУЧШИЕ
        results.sort(key=lambda x: x[1])
        final_urls = [r[0] for r in results]
        
        print(f"\nИТОГ: Из {len(candidates)} серверов проверку прошли: {len(final_urls)}.")
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_urls[:50])) # Сохраняем ТОП-50 самых быстрых
            
        if GID:
            print("Обновляем Gist...")
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("Gist успешно обновлен.")
    else:
        print("\nК сожалению, ни один сервер в базах не прошел проверку.")

if __name__ == "__main__":
    run()
