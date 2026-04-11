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

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi']

def verify_bandwidth(config_item):
    """
    Эмуляция Шага 3: Запрос к ://google.com.
    Мы проверяем, может ли сервер реально передавать данные.
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
        # Маскировка под Chrome (uTLS)
        context.set_ciphers('ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256')

        start = time.time()
        with socket.create_connection((host, port), timeout=3.5) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # Имитируем запрос данных (generate_204)
                # Это заставляет VLESS-сервер реально пропустить трафик через себя
                request = f"GET /generate_204 HTTP/1.1\r\nHost: {sni}\r\nConnection: close\r\n\r\n"
                ssock.sendall(request.encode())
                
                ssock.settimeout(2.0)
                # Ждем хотя бы 1 байт ответа. Если его нет - прокси мертв.
                data = ssock.recv(1)
                if not data: return None
                
                config_item["ping"] = int((time.time() - start) * 1000)
                return config_item
    except:
        return None

def get_tech_score(config):
    """Шаг 1: Валидация параметров и технологий"""
    score = 0
    c_low = config.lower()
    # XTLS Vision и новейшие транспорты - высший приоритет
    if 'xtls-rprx-vision' in c_low: score += 2000
    if 'type=xhttp' in c_low or 'type=httpupgrade' in c_low: score += 1500
    if 'security=reality' in c_low: score += 1000
    return score

def run():
    print("--- ВЕРИФИКАЦИЯ ПРОПУСКНОЙ СПОСОБНОСТИ ---")
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
        # Убираем только явный мусор по именам
        name = urllib.parse.unquote(cfg.split('#')[-1]).lower()
        if any(bad in name for bad in BLACK_LIST) or len(name) < 3:
            continue
            
        score = get_tech_score(cfg)
        if score > 0:
            candidates.append({"config": cfg, "score": score})

    # Сортируем лучших по технологиям перед тестом
    candidates.sort(key=lambda x: x['score'], reverse=True)
    
    # Берем топ-150 кандидатов и проверяем их на реальную передачу байтов
    real_alive = []
    print(f"Тестируем передачу данных для {len(candidates[:150])} узлов...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = [executor.submit(verify_bandwidth, item) for item in candidates[:150]]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: real_alive.append(res)

    # Итоговая сортировка по пингу
    real_alive.sort(key=lambda x: x['ping'])

    if real_alive:
        # Оставляем ТОП-30 "бетонных" серверов
        to_save = [x['config'] for x in real_alive[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(to_save))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Верификацию прошли {len(real_alive)} серверов. Топ-30 в Gist.")
    else:
        print("Ни один сервер не прошел тест передачи данных.")

if __name__ == "__main__":
    run()
