import requests, os, socket, re, time, subprocess, json, concurrent.futures

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def get_geo(ip):
    # Упрощенный Гео-чек для массовой проверки (только код страны)
    try:
        res = requests.get(f"https://ipapi.co{ip}/json/", timeout=1).json()
        code = res.get("country_code", "UN").upper()
        country = res.get("country", "Unknown")
        flag = "".join(chr(127397 + ord(c)) for c in code)
        return f"{flag} {country}"
    except: return "🌐 Unknown"

def check_server(config):
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if match:
            host, port = match.group(1), int(match.group(2))
            start = time.time()
            # Ультра-жесткий таймаут для отсева мусора
            with socket.create_connection((host, port), timeout=0.5):
                ping = int((time.time() - start) * 1000)
                if ping > 400: return None # РФ-фильтр
                clean_link = config.split("#")[0]
                return {"link": clean_link, "ping": ping, "host": host}
    except: pass
    return None

def run():
    print("--- ЗАПУСК ПОЛНОЙ ПРОВЕРКИ 4000+ СЕРВЕРОВ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            raw_data.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if c.strip()]))
    print(f"Загружено из источников: {len(unique)} ключей.")

    results = []
    # Многопоточный движок (100 потоков)
    print("Начинаю массовую фильтрацию (это будет быстро)...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        future_to_conf = {executor.submit(check_server, c): c for c in unique}
        for future in concurrent.futures.as_completed(future_to_conf):
            res = future.result()
            if res: results.append(res)
    
    print(f"Первичный отбор пройден: {len(results)} серверов.")
    
    # Сортировка по скорости
    results.sort(key=lambda x: x['ping'])

    if results:
        # Берем ТОП-100 лучших и узнаем их ГЕО (не больше 100, чтобы не забанили API)
        final_list = []
        print("Определяю страны для ТОП-серверов...")
        for i, item in enumerate(results[:100]):
            geo = get_geo(item['host'])
            display_name = f"{geo} | {item['ping']}ms"
            final_list.append(f"{item['link']}#{display_name}")
            if i % 10 == 0: time.sleep(0.5) # Пауза для стабильности API
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"ГОТОВО! В твоем Gist теперь только сливки: {len(final_list)} лучших серверов.")
    else:
        print("Даже после полной проверки ничего путного не найдено.")

if __name__ == "__main__":
    run()
