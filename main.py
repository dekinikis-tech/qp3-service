import requests, os, socket, re, time

# --- НАСТРОЙКИ ---
# Разбиваем ID на две части, чтобы GitHub не узнал его и не вставил звездочки
G_PART1 = "635b44b708e61127"
G_PART2 = "ccb3c672316590e5"
GTK = os.environ.get('GIST_TOKEN')
FILE_NAME = "vps.txt" 

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_server(config):
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if match:
            host, port = match.group(1), int(match.group(2))
            start = time.time()
            with socket.create_connection((host, port), timeout=0.8):
                latency = int((time.time() - start) * 1000)
                clean_conf = re.sub(r'#.*', '', config)
                return {"conf": clean_conf, "ping": latency}
    except: pass
    return None

def run():
    print("--- ТЕСТ С ОБХОДОМ ФИЛЬТРОВ ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            found = re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res)
            all_configs.extend(found)
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Ключей найдено: {len(unique)}")

    results = []
    for c in unique[:50]: # Оставляем 50 для быстрого теста
        res = check_server(c)
        if res: results.append(res)
    
    results.sort(key=lambda x: x['ping'])
    print(f"Рабочих: {len(results)}")

    if results:
        final_list = [f"{item['conf']}##{i+1}_[Ping:{item['ping']}ms]" for i, item in enumerate(results)]
        headers = {"Authorization": f"token {GTK}", "Accept": "application/vnd.github.v3+json"}
        payload = {"files": {FILE_NAME: {"content": "\n".join(final_list)}}}
        
        # Собираем URL из частей прямо в методе
        r = requests.patch(
            url="https://github.com" + G_PART1 + G_PART2, 
            headers=headers, 
            json=payload
        )
        
        if r.status_code == 200:
            print("ПОБЕДА! Gist обновлен.")
        else:
            print(f"Ошибка API: {r.status_code} - {r.text}")
    else:
        print("Рабочих нет.")

if __name__ == "__main__":
    run()
