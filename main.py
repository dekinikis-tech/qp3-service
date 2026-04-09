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
    try:
        res = requests.get(f"http://ip-api.com{ip}?fields=status,country,countryCode", timeout=1.5).json()
        if res.get("status") == "success":
            code = res.get("countryCode").upper()
            flag = "".join(chr(127397 + ord(c)) for c in code)
            return f"{flag} {res.get('country')}"
    except: pass
    return "🌐 Unknown"

def check_server(config):
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if match:
            host, port = match.group(1), int(match.group(2))
            start = time.time()
            # Увеличили таймаут до 1.0 сек, чтобы ловить сервера до 700-800мс
            with socket.create_connection((host, port), timeout=1.0):
                ping = int((time.time() - start) * 1000)
                
                # НОВЫЙ ПОРОГ: Пропускаем всё, что быстрее 800мс
                if ping > 800: return None 
                
                # Полная очистка ссылки от старого мусора
                clean_link = config.split("#")[0]
                return {"link": clean_link, "ping": ping, "host": host}
    except: pass
    return None

def run():
    print("--- ЗАПУСК: БАЛАНС (ДО 800мс) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 30]))
    print(f"Всего ключей в базе: {len(unique)}")

    results = []
    # Проверяем ВСЮ базу в 150 потоков
    with concurrent.futures.ThreadPoolExecutor(max_workers=150) as executor:
        futures = {executor.submit(check_server, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Сортировка: быстрые сверху
    results.sort(key=lambda x: x['ping'])
    print(f"Найдено рабочих: {len(results)}")

    if results:
        final_list = []
        # Выгружаем ТОП-150 серверов (теперь список будет внушительным)
        for i, item in enumerate(results[:150]):
            # Гео делаем только для тех, кто попал в итоговый список
            geo = get_geo(item['host'])
            display_name = f"{geo} | {item['ping']}ms"
            final_list.append(f"{item['link']}#{display_name}")
            # Пауза, чтобы не забанили Гео-API
            if i % 15 == 0: time.sleep(0.5)
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print(f"УСПЕХ! В Gist отправлено {len(final_list)} серверов.")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
