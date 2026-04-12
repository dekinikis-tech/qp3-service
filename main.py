import requests, os, re, subprocess, json, time, concurrent.futures, stat

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "./xray"
XRAY_URL = "https://github.com"

SOURCES = [
    "https://github.com/igareck/vpn-configs-for-russia/blob/main/WHITE-SNI-RU-all.txt",
"https://github.com/igareck/vpn-configs-for-russia/blob/main/WHITE-CIDR-RU-checked.txt",
"https://github.com/igareck/vpn-configs-for-russia/blob/main/WHITE-CIDR-RU-all.txt",
"https://github.com/igareck/vpn-configs-for-russia/blob/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
"https://github.com/igareck/vpn-configs-for-russia/blob/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
"https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt",
"https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']

def setup_xray():
    """Скачивание и подготовка xray-core"""
    if not os.path.exists(XRAY_BIN):
        print("Скачиваю Xray...")
        r = requests.get(XRAY_URL)
        with open("xray.zip", "wb") as f: f.write(r.content)
        subprocess.run("unzip -o xray.zip xray", shell=True)
        os.chmod(XRAY_BIN, stat.S_IRWXU)

def test_via_xray(vless_url, port_offset):
    """Реальная проверка через xray-core"""
    socks_port = 20000 + port_offset
    config_json = {
        "log": {"loglevel": "none"},
        "inbounds": [{"port": socks_port, "protocol": "socks", "settings": {"udp": True}}],
        "outbounds": [{
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": "", # Будет заполнено парсером
                    "port": 443,
                    "users": [{"id": "", "encryption": "none", "flow": ""}]
                }]
            },
            "streamSettings": {"network": "tcp", "security": "none"}
        }]
    }

    try:
        # Упрощенный парсинг для теста
        import urllib.parse
        parsed = urllib.parse.urlparse(vless_url)
        params = urllib.parse.parse_qs(parsed.query)
        
        # Настройка аутбаунда под конкретный конфиг
        out = config_json["outbounds"][0]
        out["settings"]["vnext"][0]["address"] = parsed.hostname
        out["settings"]["vnext"][0]["port"] = int(parsed.port or 443)
        out["settings"]["vnext"][0]["users"][0]["id"] = parsed.username
        out["settings"]["vnext"][0]["users"][0]["flow"] = params.get('flow', [''])[0]
        
        out["streamSettings"]["security"] = params.get('security', ['none'])[0]
        out["streamSettings"]["network"] = params.get('type', ['tcp'])[0]
        
        reality_settings = {
            "publicKey": params.get('pbk', [''])[0],
            "fingerprint": params.get('fp', ['chrome'])[0],
            "serverName": params.get('sni', [''])[0],
            "shortId": params.get('sid', [''])[0],
            "spiderX": params.get('spx', [''])[0]
        }
        if out["streamSettings"]["security"] == "reality":
            out["streamSettings"]["realitySettings"] = reality_settings
        elif out["streamSettings"]["security"] == "tls":
            out["streamSettings"]["tlsSettings"] = {"serverName": reality_settings["serverName"]}

        # Запуск Xray
        cfg_file = f"cfg_{socks_port}.json"
        with open(cfg_file, "w") as f: json.dump(config_json, f)
        
        proc = subprocess.Popen([XRAY_BIN, "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1.5) # Даем время на запуск

        # Тест пропускной способности (generate_204)
        try:
            proxies = {"http": f"socks5://127.0.0.1:{socks_port}", "https": f"socks5://127.0.0.1:{socks_port}"}
            r = requests.get("http://google.com", proxies=proxies, timeout=3)
            is_ok = (r.status_code == 204)
        except:
            is_ok = False

        proc.terminate()
        os.remove(cfg_file)
        return vless_url if is_ok else None
    except:
        return None

def run():
    setup_xray()
    print("--- СБОР И ТЕСТ ЧЕРЕЗ XRAY-CORE ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    # Фильтр мусора по именам
    unique = []
    for c in list(set(raw_data)):
        name = c.split('#')[-1].lower()
        if not any(bad in name for bad in BLACK_LIST) and not re.search(r'\d{3,}', name):
            unique.append(c)

    print(f"Кандидатов: {len(unique)}. Начинаю проверку...")
    
    results = []
    # Используем 20 потоков, так как запуск xray ресурсозатратен
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = [executor.submit(test_via_xray, url, i) for i, url in enumerate(unique[:100])]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    if results:
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(results[:30]))
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Найдено реально рабочих: {len(results)}")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
