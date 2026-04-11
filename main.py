import requests, os, socket, re, time, concurrent.futures, ssl, urllib.parse, json

# Берем данные из переменных окружения GitHub
TOKEN = os.environ.get('GIST_TOKEN')
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

def check_real_handshake(config):
    """Глубокая проверка: имитируем запрос данных"""
    try:
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        params = urllib.parse.parse_qs(parsed.query)
        sni = params.get('sni', [host])[0]

        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        
        start = time.time()
        with socket.create_connection((host, port), timeout=3.0) as sock:
            with context.wrap_socket(sock, server_hostname=sni) as ssock:
                # Посылаем запрос, чтобы сервер начал обрабатывать прокси-трафик
                ssock.sendall(b"GET / HTTP/1.1\r\nHost: " + sni.encode() + b"\r\n\r\n")
                ssock.settimeout(1.5)
                # Если пришел хоть какой-то ответ - сервер "живой" для v2rayNG
                ssock.recv(1) 
                ping = int((time.time() - start) * 1000)
                return {"config": config, "ping": ping}
    except:
        return None

def update_gist(content):
    """Обновление Gist через API напрямую"""
    url = f"https://github.com{GID}"
    headers = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}
    data = {"files": {FILE_NAME: {"content": content}}}
    res = requests.patch(url, headers=headers, json=data)
    return res.status_code == 200

def run():
    print("--- СБОР КОНФИГОВ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 60]))
    results = []

    print(f"Проверяем {len(unique)} серверов...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
        futures = {executor.submit(check_real_handshake, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)

    results.sort(key=lambda x: x['ping'])

    if results:
        final_text = "\n".join([item['config'] for item in results[:100]])
        if TOKEN and GID:
            if update_gist(final_text):
                print(f"УСПЕХ! Gist обновлен. Найдено рабочих: {len(results)}")
            else:
                print("Ошибка: Не удалось обновить Gist. Проверьте GIST_TOKEN.")
    else:
        print("Ни одного рабочего сервера не найдено.")

if __name__ == "__main__":
    run()
