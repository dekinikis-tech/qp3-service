import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse, random, socket

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray"

# 🌟 ТОЛЬКО ПРОВЕРЕННЫЕ ИСТОЧНИКИ (мертвые удалены)
SOURCES = [
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']

# 🛡️ СТРОГИЙ АНТИ-CLOUDFLARE
BLOCKED_IPS = ('104.', '172.64.', '172.65.', '172.66.', '172.67.', '188.114.', '162.159.', '108.162.')

VLESS_REGEX = re.compile(
    r"vless://(?P<uuid>[^@]+)@(?P<host>[^:?#]+):(?P<port>\d+)\??(?P<query>[^#]+)?#?(?P<name>.*)?"
)

def wait_for_port(port, timeout=3.0):
    """Умное ожидание: проверяем, поднялся ли локальный SOCKS-порт"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                return True
        time.sleep(0.1)
    return False

def test_via_xray(vless_url, port_offset):
    socks_port = 26000 + port_offset
    cfg_file = f"cfg_{socks_port}.json"
    proc = None

    try:
        match = VLESS_REGEX.match(vless_url)
        if not match: return None
        data = match.groupdict()
        address = data['host']
        
        # Фильтр Cloudflare
        if address.startswith(BLOCKED_IPS): return None
            
        query_params = urllib.parse.parse_qs(data.get('query') or '')
        def get_p(key, default=""): return query_params.get(key, [default])[0]
        
        sni_host = get_p('sni', get_p('host', address))
        network_type = get_p('type', 'tcp')
        stream_settings = {"network": network_type, "security": get_p('security', 'none')}
        
        if network_type == "ws":
            ws_host = get_p('host', address)
            stream_settings["wsSettings"] = {"path": get_p("path", "/"), "headers": {"Host": ws_host}}
        elif network_type == "grpc":
            stream_settings["grpcSettings"] = {"serviceName": get_p("serviceName", "")}
            
        if stream_settings["security"] == "reality":
            stream_settings["realitySettings"] = {"serverName": sni_host, "fingerprint": get_p("fp", "chrome"), "publicKey": get_p("pbk"), "shortId": get_p("sid", "")}
        elif stream_settings["security"] == "tls":
            stream_settings["tlsSettings"] = {"serverName": sni_host, "fingerprint": get_p("fp", "chrome"), "alpn": ["h2", "http/1.1"]}
            
        config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": socks_port, "protocol": "socks", "settings": {"udp": True}}],
            "outbounds": [{"protocol": "vless", "settings": {"vnext": [{"address": address, "port": int(data['port']), "users": [{"id": data['uuid'], "encryption": "none", "flow": get_p("flow", "")}]}]}, "streamSettings": stream_settings}]
        }
        
        with open(cfg_file, "w") as f: json.dump(config, f)
        
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        # Ждем, пока порт откроется (максимум 3 секунды), вместо глупого сна
        if not wait_for_port(socks_port, timeout=3.0):
            return None
        
        if proc.poll() is not None: return None 
        
        try:
            proxies = {"http": f"socks5h://127.0.0.1:{socks_port}", "https": f"socks5h://127.0.0.1:{socks_port}"}
            # ЖЕЛЕЗОБЕТОННАЯ ПРОВЕРКА: строгий таймаут 5 сек + проверка HTTPS (а не HTTP)
            r = requests.get("https://cp.cloudflare.com/generate_204", proxies=proxies, timeout=5)
            if r.status_code == 204: 
                return vless_url
        except Exception: 
            return None
            
    except Exception: 
        return None
    finally:
        if proc:
            proc.terminate()
            proc.wait()
        if os.path.exists(cfg_file): os.remove(cfg_file)

def run():
    print("--- ЗАПУСК ПРОВЕРКИ (ЖЕЛЕЗОБЕТОННАЯ ВЕРСИЯ v12) ---")
    all_raw, headers = [], {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>]+', res)
            
            # Красивый вывод названия источника
            source_name = url.split('/')[-1] if '/' in url else url
            print(f"Источник: {source_name[:30]}... | Найдено: {len(found)}")
            
            all_raw.extend(found)
        except Exception as e: 
            print(f"Ошибка при загрузке {url[:30]}... : {e}")
            continue
            
    unique = list(set(all_raw))
    candidates = []
    for cfg in unique:
        if '#' in cfg:
            name = urllib.parse.unquote(cfg.split('#')[-1]).lower()
            if not any(bad in name for bad in BLACK_LIST): candidates.append(cfg)
        else: candidates.append(cfg)
        
    print(f"\nУникальных: {len(unique)}. После фильтров: {len(candidates)}.")
    
    # 🔥 ГЛАВНОЕ: Рандомизируем список, чтобы каждый раз проверять разные сервера!
    random.shuffle(candidates)
    pool_to_test = candidates[:300]
    print(f"Выбрано случайных серверов для проверки: {len(pool_to_test)}...\n")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(test_via_xray, url, i): url for i, url in enumerate(pool_to_test)}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                match = VLESS_REGEX.match(res)
                name = match.groupdict().get('name', 'Unnamed') if match else 'Unnamed'
                try: name = urllib.parse.unquote(name)
                except Exception: pass
                print(f"  [+] ЖЕЛЕЗОБЕТОННО: {name}")
                results.append(res)
                
    if results:
        print(f"\nУСПЕХ! Прошли строгую проверку: {len(results)}.")
        with open(FILE_NAME, "w", encoding="utf-8") as f: f.write("\n".join(results[:50]))
        if GID:
            print("Обновляем Gist...")
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("Gist успешно обновлен.")
    else:
        print("\nНи один сервер не прошел жесткую проверку качества.")

if __name__ == "__main__":
    run()
