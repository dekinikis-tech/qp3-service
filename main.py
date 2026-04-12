import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray"
SOURCES = [
    "https://raw.githubusercontent.com/garead/vless/main/sub/mix_reality",
]
BLACK_LIST = ['dummy', 'example'] # Упростим для теста

# --- РЕГУЛЯРНОЕ ВЫРАЖЕНИЕ ДЛЯ VLESS ---
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
        
        def get_p(key, default=""): return query_params.get(key, [default])[0]

        # --- КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: ПРИОРИТЕТНЫЙ ПАРСИНГ ---
        # 1. Определяем реальный адрес и SNI
        address = data['host']
        # Приоритет для SNI - параметр 'sni', затем 'host', затем основной хост
        sni_host = get_p('sni', get_p('host', address))

        # 2. Собираем streamSettings с учетом всех параметров
        network_type = get_p('type', 'tcp')
        stream_settings = {"network": network_type, "security": get_p('security', 'tls')}

        if network_type == "ws":
            # Для WebSocket header 'Host' берется из параметра 'host', а не 'sni'
            ws_host = get_p('host', address)
            stream_settings["wsSettings"] = {"path": get_p("path", "/"), "headers": {"Host": ws_host}}
        elif network_type == "grpc":
            stream_settings["grpcSettings"] = {"serviceName": get_p("serviceName", "")}

        # 3. Собираем настройки TLS/REALITY
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

        # 4. Финальная сборка конфига
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
        
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
        time.sleep(2)
        
        if proc.poll() is not None:
            _, stderr = proc.communicate()
            print(f"  [-] ПРОВАЛ ({data['name']}): Xray не запустился. Ошибка: {stderr.strip()}")
            return None
        
        try:
            proxies = {"http": f"socks5h://127.0.0.1:{socks_port}", "https": f"socks5h://127.0.0.1:{socks_port}"}
            requests.get("http://google.com/generate_204", proxies=proxies, timeout=5)
            return vless_url
        except Exception as e:
            print(f"  [-] ПРОВАЛ ({data['name']}): Ошибка сети -> {type(e).__name__}")
            return None
            
    except Exception:
        return None
    finally:
        if proc:
            proc.terminate()
            proc.wait()
        if os.path.exists(cfg_file): os.remove(cfg_file)

def run():
    print("--- ЗАПУСК ПРОВЕРКИ (v5 - Приоритетный парсер) ---")
    all_raw, headers = [], {'User-Agent': 'Mozilla/5.0'}
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            all_raw.extend(res.splitlines())
        except Exception as e:
            print(f"Не удалось скачать {url}: {e}")
            continue
            
    unique = list(set(filter(None, all_raw)))
    print(f"\nНайдено уникальных конфигураций: {len(unique)}. Проверяем...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(test_via_xray, url, i): url for i, url in enumerate(unique)}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                name = VLESS_REGEX.match(res).groupdict().get('name', 'Unnamed')
                print(f"  [+] РАБОТАЕТ: {name}")
                results.append(res)

    if results:
        print(f"\nУСПЕХ! Найдено рабочих серверов: {len(results)}. Сохраняем.")
        with open(FILE_NAME, "w", encoding="utf-8") as f: f.write("\\n".join(results))
        if GID:
            print("Обновляем Gist...")
            subprocess.run(f'gh gist edit {GID} "{FILE_NAME}"', shell=True, check=True)
            print("Gist успешно обновлен.")
    else:
        print("\nНи один сервер не прошел проверку. Анализируйте логи провалов выше.")

if __name__ == "__main__":
    run()
