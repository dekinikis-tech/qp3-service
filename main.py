import requests, os, socket, re, time

# --- НАСТРОЙКИ ---
GID = "635b44b708e61127ccb3c672316590e5" 
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
            with socket.create_connection((host, port), timeout=0.8): # Быстрый таймаут
                latency = int((time.time() - start) * 1000)
                clean_conf = re.sub(r'#.*', '', config)
                return {"conf": clean_conf, "ping": latency}
    except: pass
    return None

def run():
    print("--- МОЛНИЕНОСНЫЙ СТАРТ (50 шт) ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            found = re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res)
            all_configs.extend(found)
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Найдено ключей: {len(unique)}")

    results = []
    # ВСЕГО 50 ШТУК ДЛЯ ТЕСТА
    for c in unique[:50]:
        res = check_server(c)
        if res: results.append(res)
    
    results.sort(key=lambda x: x['ping'])
    print(f"Рабочих найдено: {len(results)}")

    if results:
        final_list = [f"{item['conf']}##{i+1}_[Ping:{item['ping']}ms]" for i, item in enumerate(results)]
        
        headers = {"Authorization": f"token {GTK}", "Accept": "application/vnd.github.v3+json"}
        payload = {"files": {FILE_NAME: {"content": "\n".join(final_list)}}}
        
        # Прямая ссылка на API
        url = "https://github.com" + GID
        
        r = requests.patch(url, headers=headers, json=payload)
        if r.status_code == 200:
            print("ПОБЕДА! Проверь свой Gist.")
        else:
            print(f"Ошибка API: {r.status_code}")
    else:
        print("Рабочих нет.")

if __name__ == "__main__":
    run()
