import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray"
SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt", "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt", "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt", "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt",
    "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt"
]
BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']

def test_via_xray(vless_url, port_offset):
    socks_port = 26000 + port_offset
    cfg_file = f"cfg_{socks_port}.json"
    proc = None
    try:
        parsed = urllib.parse.urlparse(vless_url)
        if not parsed.hostname: return None # Пропускаем невалидные URL без хоста
        params = urllib.parse.parse_qs(parsed.query)
        def get_p(key, default=""):
            val = params.get(key, [default])
            return val[0]

        network_type = get_p("type", "tcp")
        # --- ИСПРАВЛЕННЫЙ БЛОК (Проблема №2) ---
        # Правильно обрабатываем разные типы сети
        stream_settings = {"network": network_type, "security": get_p("security", "none")}
        if network_type == "ws":
            stream_settings["wsSettings"] = {"path": get_p("path", "/"), "headers": {"Host": get_p("host", parsed.hostname)}}
        elif network_type == "grpc":
            stream_settings["grpcSettings"] = {"serviceName": get_p("serviceName", "")}
        
        # Собираем конфиг Xray
        config_json = {
            "log": {"loglevel": "none"},
            "inbounds": [{"port": socks_port, "protocol": "socks", "settings": {"udp": True}}],
            "outbounds": [{
                "protocol": "vless",
                "settings": {"vnext": [{"address": parsed.hostname, "port": int(parsed.port or 443), "users": [{"id": parsed.username, "encryption": "none", "flow": get_p("flow")}]}]},
                "streamSettings": stream_settings
            }]
        }
        
        ss = config_json["outbounds"][0]["streamSettings"]
        if ss["security"] == "reality":
            ss["realitySettings"] = {"publicKey": get_p("pbk"), "fingerprint": get_p("fp", "chrome"), "serverName": get_p("sni"), "shortId": get_p("sid")}
        elif ss["security"] == "tls":
            ss["tlsSettings"] = {"serverName": get_p("sni", parsed.hostname)}

        with open(cfg_file, "w") as f: json.dump(config_json, f)
        
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2)
        
        if proc.poll() is not None: return None # Xray не запустился, конфиг неверный
        
        is_ok = False
        try:
            proxies = {"http": f"socks5h://127.0.0.1:{socks_port}", "https": f"socks5h://127.0.0.1:{socks_port}"}
            r = requests.get("http://google.com/generate_204", proxies=proxies, timeout=5)
            if r.status_code == 204: is_ok = True
        except: pass
        
        return vless_url if is_ok else None
    except: return None
    finally:
        if proc:
            proc.terminate()
            proc.wait()
        if os.path.exists(cfg_file): os.remove(cfg_file)

def run():
    print("--- ЗАПУСК ПРОВЕРКИ ---")
    all_raw, headers = [], {'User-Agent': 'Mozilla/5.0'}
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            found = re.findall(r'vless://[^\\s\'"<>]+', res)
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

    print(f"\nВсего уникальных: {len(unique)}. Кандидатов после фильтрации: {len(candidates)}. Проверяем топ-200...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        futures = {executor.submit(test_via_xray, url, i): url for i, url in enumerate(candidates[:200])}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                try: name = urllib.parse.unquote(res.split('#')[-1])
                except: name = "NoName"
                print(f"  [+] РАБОТАЕТ: {name}")
                results.append(res)

    if results:
        print(f"\nУСПЕХ! Найдено рабочих серверов: {len(results)}. Сохраняем топ-40.")
        with open(FILE_NAME, "w", encoding="utf-8") as f: f.write("\\n".join(results[:40]))
        if GID:
            print("Обновляем Gist...")
            subprocess.run(f'gh gist edit {GID} "{FILE_NAME}"', shell=True, check=True)
            print("Gist успешно обновлен.")
    else:
        print("\nНи один сервер не прошел проверку. Попробуйте запустить воркфлоу еще раз, возможно, попались нерабочие серверы.")

if __name__ == "__main__":
    run()
