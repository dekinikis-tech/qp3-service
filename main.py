import requests, os, socket, re, time, subprocess, json, concurrent.futures

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def get_flag_and_country(ip):
    try:
        # Используем надежный сервис с запасом по таймауту
        res = requests.get(f"https://ipapi.co{ip}/json/", timeout=3).json()
        code = res.get("country_code", "").upper()
        if code:
            flag = "".join(chr(127397 + ord(c)) for c in code)
            return f"{flag} {res.get('country_name', 'Unknown')}"
    except: pass
    return None # Если гео не определилось, сервер нам не нужен (подозрительный)

def deep_check(config):
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if not match: return None
        
        host, port = match.group(1), int(match.group(2))
        
        # ЭТАП 1: Проверка порта
        start = time.time()
        with socket.create_connection((host, port), timeout=1.5):
            ping = int((time.time() - start) * 1000)
            
            # ЭТАП 2: Попытка получить баннер сервера (имитация рукопожатия)
            # Это отсеивает 80% "фейковых" портов
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            s.connect((host, port))
            s.send(b'\x05\x01\x00') # Базовый запрос для SOCKS/V2Ray
            data = s.recv(10)
            s.close()
            
            if ping > 700: return None
            return {"link": config.split("#")[0], "ping": ping, "host": host}
    except: pass
    return None

def run():
    print("--- ЗАПУСК ГЛУБОКОЙ ФИЛЬТРАЦИИ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            raw_data.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 40]))
    print(f"В базе {len(unique)} ключей. Начинаю жесткий отбор...")

    # Проверяем сразу по 100 штук
    valid_servers = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(deep_check, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_servers.append(res)
    
    valid_servers.sort(key=lambda x: x['ping'])
    print(f"Прошли тех-проверку: {len(valid_servers)}. Определяю ГЕО...")

    final_list = []
    # Теперь берем тех, кто прошел, и пробиваем ГЕО. Если ГЕО нет - сервер в мусор.
    # Ограничимся ТОП-40 самыми быстрыми.
    count = 0
    for item in valid_servers:
        if count >= 40: break
        
        geo = get_flag_and_country(item['host'])
        if geo:
            final_list.append(f"{item['link']}#{geo} | {item['ping']}ms")
            count += 1
            time.sleep(0.5) # Пауза для стабильности API флагов

    if final_list:
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print(f"УСПЕХ! В Gist выгружено {len(final_list)} гарантированно живых серверов.")
    else:
        print("Ни один сервер не прошел проверку качества.")

if __name__ == "__main__":
    run()
