import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray"

SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt",
    "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']

# Регулярное выражение для точного парсинга VLESS
VLESS_REGEX = re.compile(
    r"vless://(?P<uuid>[^@]+)@(?P<host>[^:?#]+):(?P<port>\d+)\??(?P<query>[^#]+)?#?(?P<name>.*)?"
)

def test_via_xray(vless_url, port_offset):
    socks_port = 26000 + port_offset
    cfg_file = f"cfg_{socks_port}.json"
    proc = None
    
    try:
        match = VLESS_REGEX.match(vless_url)
        if not match: return None
        
        data = match.groupdict()
        query_params = urllib.parse.parse_qs(data.get('query') or '')
        
        def get_p(key, default=""): 
            return query_params.get(key, [default])[0]

        address = data['host']
        sni_host = get_p('sni', get_p('host', address))
        network_type = get_p('type', 'tcp')
        stream_settings = {"network": network_type, "security": get_p('security', 'none')}

        if network_type == "ws":
            ws_host = get_p('host', address)
            stream_settings["wsSettings"] = {"path": get_p("path", "/"), "headers": {"Host": ws_host}}
        elif network_type == "grpc":
            stream_settings["grpcSettings"] = {"serviceName": get_p("serviceName", "")}

        if stream_settings["security"] == "reality":
            stream_settings["realitySettings"] = {
                "serverName": sni_host, 
                "fingerprint": get_p("fp", "chrome"), 
                "publicKey": get_p("pbk"), 
                "shortId": get_p("sid", "")
            }
        elif stream_settings["security"] == "tls":
            stream_settings["tlsSettings"] = {
                "serverName": sni_host, 
                "fingerprint": get_p("fp", "chrome"), 
                "alpn": ["h2", "http/1.1"]
            }

        config = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": socks_port, "protocol": "socks", "settings": {"udp": True}}],
            "outbounds": [{
                "protocol": "vless", 
                "settings": {"vnext": [{"address": address, "port": int(data['port']), "users": [{"id": data['uuid'], "encryption": "none", "flow": get_p("flow", "")}]}]}, 
                "streamSettings": stream_settings
            }]
        }

        with open(cfg_file, "w") as f: json.dump(config, f)
        
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2) # Даем время на запуск
        
        if proc.poll() is not None: return None # Если Xray упал сразу
        
        try:
            proxies = {"http": f"socks5h://127.0.0.1:{socks_port}", "https": f"socks5h://127.0.0.1:{socks_port}"}
            r = requests.get("http://google.com/generate_204", proxies=proxies, timeout=5)
            if r.status_code == 204:
                return vless_url
        except:
            return None
            
    except: return None
    finally:
        if proc:
            proc.terminate()
            proc.wait()
        if os.path.exists(cfg_file): os.remove(cfg_file)

def run():
    print("--- ЗАПУСК ПРОВЕРКИ (v7 - Финальная версия) ---")
    all_raw = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            # Ищем ссылки в открытом тексте
            found = re.findall(r'vless://[^\s\'"<>]+', res)
            print(f"Источник: {url[:40]}... | Найдено: {len(found)}")
            all_raw.extend(found)
        except: continue
            
    unique = list(set(all_raw))
    candidates = []
    
    for cfg in unique:
        if '#' in cfg:
            name = urllib.parse.unquote(cfg.split('#')[-1]).lower()
            if not any(bad in name for bad in BLACK_LIST): candidates.append(cfg)
        else: candidates.append(cfg)

    print(f"\nВсего уникальных: {len(unique)}. Кандидатов после фильтрации: {len(candidates)}. Проверяем топ-100...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_via_xray, url, i): url for i, url in enumerate(candidates[:100])}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                match = VLESS_REGEX.match(res)
                name = match.groupdict().get('name', 'Unnamed') if match else 'Unnamed'
                try: name = urllib.parse.unquote(name)
                except: pass
                print(f"  [+] РАБОТАЕТ: {name}")
                results.append(res)

    if results:
        print(f"\nУСПЕХ! Найдено рабочих серверов: {len(results)}. Сохраняем топ-40.")
        with open(FILE_NAME, "w", encoding="utf-8") as f: f.write("\n".join(results[:40]))
        if GID:
            print("Обновляем Gist...")
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("Gist успешно обновлен.")
    else:
        print("\nНи один сервер не прошел проверку. Возможно, первые 100 серверов нерабочие.")

if __name__ == "__main__":
    run()
