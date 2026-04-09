import requests, os, socket, re, time, subprocess, json

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def get_flag(host):
    # Простейший определитель флага по домену. 
    # Для IP-адресов по умолчанию поставим 🌐, так как полная база весит много
    flags = {"de": "🇩🇪", "us": "🇺🇸", "ru": "🇷🇺", "nl": "🇳🇱", "gb": "🇬🇧", "fi": "🇫🇮", "fr": "🇫🇷", "jp": "🇯🇵", "sg": "🇸🇬", "tr": "🇹🇷"}
    ext = host.split('.')[-1].lower()
    return flags.get(ext, "🌐")

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
                return {"conf": clean_conf, "ping": ping, "host": host}
    except: pass
    return None

def run():
    print(f"--- ОБНОВЛЕНИЕ СПИСКА С ФЛАГАМИ ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            all_configs.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    
    results = []
    # Давай проверять 150 штук, чтобы список был посолиднее, но всё еще быстрым
    for c in unique[:150]:
        res = check_server(c)
        if res: results.append(res)
    
    results.sort(key=lambda x: x['ping'])

    if results:
        final_list = []
        for i, item in enumerate(results):
            flag = get_flag(item['host'])
            # Формат: 🇩🇪 [45ms] Server #1
            name = f"{flag} [{item['ping']}ms] VPN-{i+1}"
            final_list.append(f"{item['conf']}#{name}")
        
        final_text = "\n".join(final_list)
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write(final_text)
            
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"ГОТОВО! Найдено {len(results)} рабочих серверов с флагами.")
    else:
        print("Рабочих серверов не нашли.")

if __name__ == "__main__":
    run()
