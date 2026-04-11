import requests, os, re, subprocess, urllib.parse, socket, concurrent.futures, time, ssl

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/igareck/vpn-configs-for-russia/blob/main/WHITE-SNI-RU-all.txt",
"https://github.com/igareck/vpn-configs-for-russia/blob/main/WHITE-CIDR-RU-checked.txt",
"https://github.com/igareck/vpn-configs-for-russia/blob/main/WHITE-CIDR-RU-all.txt",
"https://github.com/igareck/vpn-configs-for-russia/blob/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
"https://github.com/igareck/vpn-configs-for-russia/blob/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
"https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt",
"https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt"
]

# Черный список (дополнен по твоему последнему скрину)
BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']

def is_garbage(config):
    """Ультимативный фильтр мусора"""
    try:
        name_raw = config.split('#')[-1] if '#' in config else ""
        name = urllib.parse.unquote(name_raw).strip().lower()
        
        if not name or len(name) < 4: return True
        # 1. Если в имени 3 и более цифр (типа 0578) - ЭТО БАН
        if re.search(r'\d{3,}', name): return True
        # 2. Если имя содержит слова из черного списка
        if any(bad in name for bad in BLACK_LIST): return True
        # 3. Если имя чисто цифровое с дефисами (типа 12-345)
        if re.sub(r'[-\s]', '', name).isdigit(): return True
        
        return False
    except:
        return True

def verify_real_data(config_item):
    """Методология Шаг 3: Проверка реальной передачи данных"""
    try:
        config = config_item["config"]
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [host])

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')

        start = time.time()
        with socket.create_connection((host, port), timeout=3.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # Пытаемся получить хоть какой-то ответ от сервера
                request = f"GET /generate_204 HTTP/1.1\r\nHost: {sni}\r\nConnection: close\r\n\r\n"
                ssock.sendall(request.encode())
                ssock.settimeout(2.0)
                if not ssock.recv(1): return None
                
                config_item["ping"] = int((time.time() - start) * 1000)
                return config_item
    except:
        return None

def run():
    print("--- ОЧИСТКА СПИСКА ОТ 'КРАСНЫХ' СЕРВЕРОВ ---")
    all_raw = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=12, headers=headers).text
            all_raw.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set(all_raw))
    candidates = []
    for cfg in unique:
        if not is_garbage(cfg):
            # Отбираем только Reality и Vision (как самые рабочие)
            if 'xtls-rprx-vision' in cfg.lower() or 'reality' in cfg.lower():
                candidates.append({"config": cfg, "ping": 9999})

    # Проверяем на реальную передачу данных
    real_alive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(verify_real_data, item) for item in candidates[:150]]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: real_alive.append(res)

    # Сортировка по реальному пингу
    real_alive.sort(key=lambda x: x['ping'])

    if real_alive:
        # Оставляем ТОП-20 самых быстрых и живых
        to_save = [x['config'] for x in real_alive[:20]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(to_save))
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! В Gist отправлено {len(to_save)} 'бетонных' серверов.")
    else:
        print("Живых серверов не найдено.")

if __name__ == "__main__":
    run()
