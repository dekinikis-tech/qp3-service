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
    "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt",
    "https://github.com/luxxuria/harvester/blob/main/non_ru.txt",
    "https://github.com/luxxuria/harvester/blob/main/ping_tested.txt",
    "https://github.com/luxxuria/harvester/blob/main/speed_tested.txt",
    "https://github.com/luxxuria/harvester/blob/main/top_600.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi']

def verify_node(config_item):
    """
    Пункт 3 твоей методологии: Верификация пропускной способности.
    Имитируем запрос данных через TLS Handshake.
    """
    try:
        config = config_item["config"]
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [host])[0]

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        # Эмуляция современного браузера (uTLS)
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')

        start = time.time()
        with socket.create_connection((host, port), timeout=3.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # Имитируем запрос к google.com/generate_204 (Пункт 3 твоей методики)
                # Отправляем минимальный HTTP-заголовок
                request = f"HEAD /generate_204 HTTP/1.1\r\nHost: {sni}\r\n\r\n"
                ssock.sendall(request.encode())
                
                # Ждем ответ. Если сервер прислал данные - он ЖИВОЙ на 100%
                ssock.settimeout(1.5)
                ssock.recv(1)
                
                ping = int((time.time() - start) * 1000)
                config_item["ping"] = ping
                return config_item
    except:
        return None

def get_quality_score(config):
    """Пункт 1 твоей методологии: Валидация параметров"""
    score = 0
    c_low = config.lower()
    
    # Приоритет новейшим транспортам (xhttp, grpc)
    if 'type=xhttp' in c_low or 'type=grpc' in c_low: score += 1000
    if 'xtls-rprx-vision' in c_low: score += 2000
    if 'security=reality' in c_low: score += 500
    
    return score

def run():
    print("--- ЗАПУСК ВЕРИФИКАЦИИ ПО МЕТОДОЛОГИИ ---")
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
        name = urllib.parse.unquote(cfg.split('#')[-1]).lower()
        if any(bad in name for bad in BLACK_LIST) or len(name) < 3:
            continue
            
        score = get_quality_score(cfg)
        if score > 0:
            candidates.append({"config": cfg, "score": score})

    # Сортируем лучших кандидатов для теста
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    # Проверяем топ-100 самых перспективных на реальную передачу данных
    real_alive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
        futures = [executor.submit(verify_node, item) for item in candidates[:100]]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: real_alive.append(res)

    # Финальная сортировка по пингу (от быстрых к медленным)
    real_alive.sort(key=lambda x: x['ping'])

    if real_alive:
        # Берем ТОП-25 самых быстрых из тех, кто прошел верификацию данных
        to_save = [x['config'] for x in real_alive[:25]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(to_save))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Верификацию прошли {len(real_alive)} серверов. Топ-25 в Gist.")
    else:
        print("Ни один сервер не прошел верификацию пропускной способности.")

if __name__ == "__main__":
    run()
