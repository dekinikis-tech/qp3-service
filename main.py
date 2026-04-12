import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray"

# 🌟 ТОЛЬКО ПРОВЕРЕННЫЕ "ЧИСТЫЕ" ИСТОЧНИКИ
SOURCES = [
    # Самые стабильные под РФ (маскировка под RU-сервисы)
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/ru-sni/vless_ru.txt",
    # Очищенные от мусора VLESS Reality
    "https://raw.githubusercontent.com/kort0881/vpn-vless-configs-russia/main/githubmirror/clean/vless.txt",
    # Ваши проверенные "Белые списки"
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    # Стабильный агрегатор
    "https://raw.githubusercontent.com/ebrasha/free-v2ray-public-list/main/vless.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']

# 🛡️ СТРОГИЙ АНТИ-CLOUDFLARE (Убираем всё, что дает -1 в v2rayN)
BLOCKED_IPS = ('104.', '172.64.', '172.65.', '172.66.', '172.67.', '188.114.', '162.159.', '108.162.')

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
        address = data['host']
        
        # Фильтр Cloudflare (Самый важный шаг для вас)
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
        time.sleep(2)
        
        if proc.poll() is not None: return None 
        
        try:
            proxies = {"http": f"socks5h://127.0.0.1:{socks_port}", "https": f"socks5h://127.0.0.1:{socks_port}"}
            # Увеличим таймаут до 7 секунд для надежности
            r = requests.get("http://google.com/generate_204", proxies=proxies, timeout=7)
            if r.status_code == 204: return vless_url
        except: return None
            
    except: return None
    finally:
        if proc:
            proc.terminate()
            proc.wait()
        if os.path.exists(cfg_file): os.remove(cfg_file)

def run():
    print("--- ЗАПУСК ПРОВЕРКИ (v11 - Качество > Количество) ---")
    all_raw, headers = [], {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
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

    # Проверяем больше кандидатов (300), чтобы найти лучшие из лучших
    print(f"\nВсего уникальных: {len(unique)}. Кандидатов: {len(candidates)}. Проверяем топ-300...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
        futures = {executor.submit(test_via_xray, url, i): url for i, url in enumerate(candidates[:300])}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                match = VLESS_REGEX.match(res)
                name = match.groupdict().get('name', 'Unnamed') if match else 'Unnamed'
                try: name = urllib.parse.unquote(name)
                except: pass
                print(f"  [+] РАБОТАЕТ (Качественный): {name}")
                results.append(res)

    if results:
        # Сохраняем ВСЁ, что нашли (но не более 50 для порядка)
        print(f"\nУСПЕХ! Найдено действительно рабочих серверов: {len(results)}.")
        with open(FILE_NAME, "w", encoding="utf-8") as f: f.write("\n".join(results[:50]))
        if GID:
            print("Обновляем Gist...")
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print("Gist успешно обновлен.")
    else:
        print("\nНи один сервер не прошел жесткую проверку качества.")

if __name__ == "__main__":
    run()
