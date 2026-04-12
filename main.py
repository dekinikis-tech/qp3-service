import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray" # После инсталлера он будет в PATH

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
    """Установка xray через официальный скрипт (самый надежный метод)"""
    print("Устанавливаю Xray-core...")
    # Скачиваем и запускаем официальный инсталлер
    subprocess.run("curl -L https://github.com | sudo bash -s -- install", shell=True)

def test_via_xray(vless_url, port_offset):
    socks_port = 25000 + port_offset
    cfg_file = f"cfg_{socks_port}.json"
    try:
        parsed = urllib.parse.urlparse(vless_url)
        params = urllib.parse.parse_qs(parsed.query)
        
        # Исправлено: теперь возвращает СТРОКУ, а не список
        def get_p(key, default=""):
            return params.get(key, [default])[0]

        config_json = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": socks_port, "protocol": "socks", "settings": {"udp": True}}],
            "outbounds": [{
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": parsed.hostname,
                        "port": int(parsed.port or 443),
                        "users": [{
                            "id": parsed.username,
                            "encryption": "none",
                            "flow": get_p("flow")
                        }]
                    }]
                },
                "streamSettings": {
                    "network": get_p("type", "tcp"),
                    "security": get_p("security", "none")
                }
            }]
        }

        ss = config_json["outbounds"][0]["streamSettings"]
        if ss["security"] == "reality":
            ss["realitySettings"] = {
                "publicKey": get_p("pbk"),
                "fingerprint": get_p("fp", "chrome"),
                "serverName": get_p("sni"),
                "shortId": get_p("sid")
            }
        elif ss["security"] == "tls":
            ss["tlsSettings"] = {"serverName": get_p("sni", parsed.hostname)}

        with open(cfg_file, "w") as f:
            json.dump(config_json, f)
        
        # Запуск
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.0)

        is_ok = False
        try:
            proxies = {"http": f"socks5h://127.0.0.1:{socks_port}", "https": f"socks5h://127.0.0.1:{socks_port}"}
            # Делаем реальный запрос к Google
            r = requests.get("http://google.com", proxies=proxies, timeout=5)
            if r.status_code == 204:
                is_ok = True
        except:
            pass

        proc.terminate()
        if os.path.exists(cfg_file): os.remove(cfg_file)
        return vless_url if is_ok else None
    except:
        if os.path.exists(cfg_file): os.remove(cfg_file)
        return None

def run():
    setup_xray()
    print("--- СБОР И ТЕСТ ЧЕРЕЗ XRAY ---")
    raw_data = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10, headers=headers).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = []
    for c in list(set(raw_data)):
        if '#' in c:
            name = urllib.parse.unquote(c.split('#')[-1]).lower()
            if not any(bad in name for bad in BLACK_LIST) and not re.search(r'\d{3,}', name):
                unique.append(c)

    print(f"Кандидатов: {len(unique)}. Начинаю проверку...")
    
    results = []
    # 15 потоков для стабильности в GitHub Actions
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = [executor.submit(test_via_xray, url, i) for i, url in enumerate(unique[:100])]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    if results:
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(results[:40]))
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Реально рабочих: {len(results)}")
    else:
        print("Ни один сервер не прошел проверку через Xray.")

if __name__ == "__main__":
    run()
