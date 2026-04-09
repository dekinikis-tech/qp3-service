import requests, os, socket, re, time, json, subprocess

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
            with socket.create_connection((host, port), timeout=0.8):
                return {"conf": re.sub(r'#.*', '', config), "ping": int((time.time() - start) * 1000)}
    except: pass
    return None

def run():
    print("--- СУПЕР-МЕТОД CURL ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            all_configs.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Ключей: {len(unique)}")

    results = []
    for c in unique[:100]: # Увеличил до 100 для теста, это быстро
        res = check_server(c)
        if res: results.append(res)
    
    results.sort(key=lambda x: x['ping'])
    print(f"Рабочих: {len(results)}")

    if results:
        final_text = "\n".join([f"{item['conf']}##{i+1}_[Ping:{item['ping']}ms]" for i, item in enumerate(results)])
        
        # Подготовка данных для CURL
        payload = json.dumps({"files": {FILE_NAME: {"content": final_text}}})
        
        # СИСТЕМНЫЙ ВЫЗОВ (Обходит все ошибки библиотек Python)
        print("Отправка через системный CURL...")
        cmd = [
            "curl", "-X", "PATCH",
            "-H", f"Authorization: token {GTK}",
            "-H", "Accept: application/vnd.github.v3+json",
            "-H", "Content-Type: application/json",
            "-d", payload,
            f"https://github.com{GID}"
        ]
        
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0:
            print("ПОБЕДА! Проверяй Gist.")
        else:
            print(f"Ошибка CURL: {process.stderr}")
    else:
        print("Рабочих нет.")

if __name__ == "__main__":
    run()
