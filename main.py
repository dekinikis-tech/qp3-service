import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse, zipfile, stat

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "./xray" 

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

def setup_xray():
    """Скачивание Xray через системный wget (самый надежный способ в Ubuntu)"""
    if not os.path.exists(XRAY_BIN):
        print("Загрузка Xray-core...")
        # Используем зеркало GitHub или прямую ссылку через wget с флагами
        url = "https://github.com"
        try:
            subprocess.run(f"wget -q -O xray.zip {url}", shell=True)
            with zipfile.ZipFile("xray.zip", "r") as zip_ref:
                zip_ref.extract("xray", ".")
            os.chmod(XRAY_BIN, stat.S_IRWXU)
            print("Xray успешно подготовлен.")
        except Exception as e:
            print(f"Ошибка установки Xray: {e}")

def test_via_xray(vless_url, port_offset):
    socks_port = 30000 + port_offset
    cfg_file = f"cfg_{socks_port}.json"
    try:
        parsed = urllib.parse.urlparse(vless_url)
        params = urllib.parse.parse_qs(parsed.query)
        
        # Получаем строку из параметров
        def get_p(key, default=""):
            val = params.get(key, [default])
            return val[0] if isinstance(val, list) else val

        # КОРРЕКТНЫЙ КОНФИГ XRAY
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

        # Тонкая настройка Reality/TLS
        ss = config_json["outbounds"][0]["streamSettings"] # Добавлен индекс [0]
        if ss["security"] == "reality":
            ss["realitySettings"] = {
                "publicKey": get_p("pbk"),
                "fingerprint": get_p("fp", "chrome"),
                "serverName": get_p("sni"),
                "shortId": get_p("sid"),
                "spiderX": get_p("spx")
            }
        elif ss["security"] == "tls":
            ss["tlsSettings"] = {"serverName": get_p("sni", parsed.hostname)}

        with open(cfg_file, "w") as f:
            json.dump(config_json, f)
        
        # Запуск xray
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(2.0)

        is_ok = False
        try:
            proxies = {"http": f"socks5h://127.0.0.1:{socks_port}", "https": f"socks5h://127.0.0.1:{socks_port}"}
            r = requests.get("http://google.com", proxies=proxies, timeout=5)
            if r.status_code == 204:
                is_ok = True
        except:
            pass

        proc.terminate()
        if os.path.exists(cfg_file): os.remove(cfg_file)
        return vless_url if is_ok else None
    except Exception:
        if os.path.exists(cfg_file): os.remove(cfg_file)
        return None

def run():
    setup_xray()
    if not os.path.exists(XRAY_BIN):
        print("Критическая ошибка: Xray не найден.")
        return

    print("--- СТАРТ ПРОВЕРКИ ---")
    all_raw = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
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
            if not any(bad in name for bad in BLACK_LIST) and not re.search(r'\d{3,}', name):
                candidates.append(cfg)

    print(f"Кандидатов: {len(candidates)}. Тестируем топ-150...")
    
    results = []
    # 10 потоков для максимальной стабильности
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(test_via_xray, url, i) for i, url in enumerate(candidates[:150])]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    if results:
        # Сохраняем ТОП-40
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(results[:40]))
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Найдено рабочих: {len(results)}")
    else:
        print("Рабочих серверов не найдено. Возможно, GitHub заблокирован провайдерами.")

if __name__ == "__main__":
    run()
