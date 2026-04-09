import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_honest_proxy(config):
    try:
        # Приоритет Reality/TLS/Vision (самые живучие в РФ)
        is_modern = any(x in config.lower() for x in ['reality', 'tls', 'security=vless', 'flow=xtls'])
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        
        host, port = match.group(1), int(match.group(2))
        
        start = time.time()
        # ШАГ 1: Быстрый TCP коннект
        with socket.create_connection((host, port), timeout=1.2):
            ping = int((time.time() - start) * 1000)
            
            # ТВОЕ УСЛОВИЕ: От 50мс до 600мс
            if ping < 50 or ping > 600:
                return None
            
            # ШАГ 2: Глубокая проверка (ждем ответ от протокола)
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.2)
            s.connect((host, port))
            # Отправляем "приветственный" байт
            s.send(b"\x16\x03\x01\x00\x00") 
            response = s.recv(1)
            s.close()
            
            if not response: return None
            
            return {"config": config, "ping": ping, "modern": is_modern}
    except:
        return None

def run():
    print("--- ФИЛЬТРАЦИЯ: ЗОНА 50-600мс ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 50]))
    print(f"Всего ключей: {len(unique)}")

    results = []
    # 120 потоков для скорости
    with concurrent.futures.ThreadPoolExecutor(max_workers=120) as executor:
        futures = {executor.submit(check_honest_proxy, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Сортировка: сначала защищенные (Reality), потом самые быстрые из честных
    results.sort(key=lambda x: (not x['modern'], x['ping']))

    if results:
        # Выгружаем ТОП-40 самых качественных
        final_list = [item['config'] for item in results[:40]]
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"УСПЕХ! Найдено {len(results)} честных серверов. В Gist ушло ТОП-40.")
    else:
        print("Честных серверов в диапазоне 50-600мс не найдено.")

if __name__ == "__main__":
    run()
