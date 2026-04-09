import requests, os, socket, re, time, subprocess

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
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if match:
            host, port = match.group(1), int(match.group(2))
            start = time.time()
            with socket.create_connection((host, port), timeout=1.0):
                ping = int((time.time() - start) * 1000)
                clean_conf = re.sub(r'#.*', '', config).strip()
                return {"conf": clean_conf, "ping": ping}
    except: pass
    return None

def run():
    print(f"--- БЫСТРЫЙ ТЕСТ: 50 СЕРВЕРОВ ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            all_configs.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Найдено в базе: {len(unique)}")

    results = []
    for c in unique[:50]:
        res = check_server(c)
        if res: results.append(res)
    
    results.sort(key=lambda x: x['ping'])
    print(f"Рабочих из 50: {len(results)}")

    if results:
        final_text = "\n".join([f"{item['conf']}#⭐_{i+1}_[Ping:{item['ping']}ms]" for i, item in enumerate(results)])
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write(final_text)
            
        # ИСПРАВЛЕННАЯ КОМАНДА
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        process = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if process.returncode == 0:
            print("ПОБЕДА! Gist обновлен.")
        else:
            print(f"Ошибка GH: {process.stderr}")
    else:
        print("Рабочих серверов не нашли.")

if __name__ == "__main__":
    run()
