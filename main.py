import requests, os, socket, re, time, subprocess, json

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
        # Получаем код страны и полное название
        res = requests.get(f"http://ip-api.com{ip}?fields=status,country,countryCode", timeout=1.5).json()
        if res.get("status") == "success":
            code = res.get("countryCode").upper()
            country_name = res.get("country")
            flag = "".join(chr(127397 + ord(c)) for c in code)
            return f"{flag} {country_name}"
    except: pass
    return "🌐 Unknown"

def check_server(config):
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        
        if match:
            host, port = match.group(1), int(match.group(2))
            start = time.time()
            # Жесткая проверка: 0.7 сек на отклик
            with socket.create_connection((host, port), timeout=0.7):
                ping = int((time.time() - start) * 1000)
                # Вырезаем конфиг без старого названия (всё до знака #)
                clean_link = config.split("#")[0]
                return {"link": clean_link, "ping": ping, "host": host}
    except: pass
    return None

def run():
    print("--- СБОРКА ЧИСТОГО СПИСКА ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            all_configs.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    results = []
    
    # Проверяем 150 штук для качества
    for c in unique[:150]:
        res = check_server(c)
        if res: results.append(res)
    
    # Сортировка по скорости
    results.sort(key=lambda x: x['ping'])

    if results:
        final_list = []
        for item in results:
            geo = get_geo(item['host'])
            # Формат: 🇩🇪 Germany | 120ms
            display_name = f"{geo} | {item['ping']}ms"
            final_list.append(f"{item['link']}#{display_name}")
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        # Обновляем Gist
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"ГОТОВО! В списке {len(results)} чистых серверов.")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
