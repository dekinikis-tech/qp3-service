import requests, os, socket, re, time, subprocess, concurrent.futures

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_server(config):
    try:
        # Парсим хост и порт
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if not match: return None
        
        host, port = match.group(1), int(match.group(2))
        
        start = time.time()
        # Жесткий таймаут 0.7 сек — если не ответил, значит в РФ будет лагать
        with socket.create_connection((host, port), timeout=0.7):
            ping = int((time.time() - start) * 1000)
            
            # Полностью вычищаем старое название (рекламу и т.д.)
            clean_link = config.split("#")[0]
            return {"link": clean_link, "ping": ping}
    except: pass
    return None

def run():
    print("--- ЗАПУСК БЕЗ ФЛАГОВ (МАКСИМАЛЬНАЯ СКОРОСТЬ) ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 40]))
    print(f"Загружено ключей: {len(unique)}")

    valid_servers = []
    # 100 потоков — пролетаем всю базу за один миг
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_server, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: valid_servers.append(res)
    
    # Сортировка: самые шустрые в начало
    valid_servers.sort(key=lambda x: x['ping'])
    print(f"Рабочих найдено: {len(valid_servers)}")

    if valid_servers:
        # Формируем список: Номер и Пинг
        # Берем ТОП-100, чтобы не забивать память телефона лишним мусором
        final_list = [f"{item['link']}#Server_{i+1}_[{item['ping']}ms]" for i, item in enumerate(valid_servers[:100])]
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        # Обновление через GH CLI
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"УСПЕХ! В Gist выгружено {len(final_list)} рабочих серверов.")
    else:
        print("Живых серверов не найдено.")

if __name__ == "__main__":
    run()
