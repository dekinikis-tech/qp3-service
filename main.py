import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse, random, socket

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray"

# 🌟 ТОЛЬКО ПРОВЕРЕННЫЕ ИСТОЧНИКИ
SOURCES = [
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']
BLOCKED_IPS = ('104.', '172.64.', '172.65.', '172.66.', '172.67.', '188.114.', '162.159.', '108.162.')

VLESS_REGEX = re.compile(
    r"vless://(?P<uuid>[^@]+)@(?P<host>[^:?#]+):(?P<port>\d+)\??(?P<query>[^#]+)?#?(?P<name>.*)?"
)

def get_free_port():
    """Получает 100% свободный случайный порт от операционной системы"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]

def wait_for_port(port, proc, timeout=3.0):
    """Ждет открытия порта, но сразу прерывается, если xray упал"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if proc.poll() is not None: 
            return False # Xray упал из-за кривого конфига
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.5)
            if sock.connect_ex(('127.0.0.1', port)) == 0:
                return True
        time.sleep(0.1)
    return False

def test_via_xray(vless_url):
    socks_port = get_free_port() # Уникальный порт для защиты от зомби-процессов
    cfg_file = f"cfg_{socks_port}.json"
    proc = None

    try:
        match = VLESS_REGEX.match(vless_url)
        if not match: return None
        data = match.groupdict()
        address = data['host']
        
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
        
        if not wait_for_port(socks_port, proc, timeout=3.0):
            return None
        
        proxies = {"http": f"socks5h://127.0.0.1:{socks_port}", "https": f"socks5h://127.0.0.1:{socks_port}"}
        
        # Эмулируем точный пинг, который делает v2rayN
        r = requests.get("http://www.gstatic.com/generate_204", proxies=proxies, timeout=5)
        if r.status_code == 204: 
            return vless_url
            
    except Exception: 
        return None
    finally:
        if proc:
            proc.kill() # Жестко убиваем процесс Xray
            proc.wait()
        if os.path.exists(cfg_file): 
            try: os.remove(cfg_file)
            except Exception: pass

def run():
    print("--- ЗАПУСК ПРОВЕРКИ (v13 - Без зомби-процессов) ---")
    all_raw, headers = [], {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>]+', res)
            source_name = url.split('/')[-1] if '/' in url else url
            print(f"Источник: {source_name[:30]}... | Найдено: {len(found)}")
            all_raw.extend(found)
        except Exception as e: 
            pass
            
    unique = list(set(all_raw))
    candidates = []
    for cfg in unique:
        if '#' in cfg:
            name = urllib.parse.unquote(cfg.split('#')[-1]).lower()
            if not any(bad in name for bad in BLACK_LIST): candidates.append(cfg)
        else: candidates.append(cfg)
        
    print(f"\nУникальных: {len(unique)}. После фильтров: {len(candidates)}.")
    
    random.shuffle(candidates)
    pool_to_test = candidates[:300]
    print(f"Выбрано случайных серверов для проверки: {len(pool_to_test)}...\n")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(test_via_xray, url): url for url in pool_to_test}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                match = VLESS_REGEX.match(res)
                name = match.groupdict().get('name', 'Unnamed') if match else 'Unnamed'
                try: name = urllib.parse.unquote(name)
                except Exception: pass
                print(f"  [+] РЕАЛЬНО РАБОТАЕТ: {name}")
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
