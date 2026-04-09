import requests, os, socket, re, time, subprocess, json

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

# Кэш для флагов, чтобы не стучаться в API слишком часто
geo_cache = {}

def get_geo_info(ip):
    if ip in geo_cache: return geo_cache[ip]
    try:
        # Используем бесплатное API для определения страны
        res = requests.get(f"http://ip-api.com{ip}?fields=status,countryCode", timeout=2).json()
        if res.get("status") == "success":
            code = res.get("countryCode").upper()
            # Превращаем код страны в эмодзи флага
            flag = "".join(chr(127397 + ord(c)) for c in code)
            geo_cache[ip] = flag
            return flag
    except: pass
    return "🌐"

def check_server(config):
    try:
        # Парсим хост, порт и оригинальное имя
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        
        if match:
            host, port = match.group(1), int(match.group(2))
            
            # Извлекаем оригинальное имя сервера (после #)
            original_name = ""
            if "#" in config:
                original_name = config.split("#")[-1]
                # Чистим рекламу (ТГ каналы, ссылки)
                original_name = re.sub(r'(@\w+|http\S+|www\S+)', '', original_name).strip()
            
            start = time.time()
            # Проверка порта
            with socket.create_connection((host, port), timeout=1.5):
                ping = int((time.time() - start) * 1000)
                # Если пинг слишком большой, сервер скорее всего будет тормозить
                if ping > 1000: return None
                
                flag = get_geo_info(host)
                clean_conf = config.split("#")[0]
                return {"conf": clean_conf, "ping": ping, "name": original_name, "flag": flag}
    except: pass
    return None

def run():
    print("--- ГЛУБОКАЯ ПРОВЕРКА И ГЕОЛОКАЦИЯ ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            all_configs.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    results = []
    
    # Проверяем 100 штук для качества (с гео-проверкой это дольше)
    for c in unique[:100]:
        res = check_server(c)
        if res: results.append(res)
    
    results.sort(key=lambda x: x['ping'])

    if results:
        final_list = []
        for item in results:
            # Формат: Флаг [Пинг] ОригинальноеИмя (без рекламы)
            display_name = f"{item['flag']} [{item['ping']}ms] {item['name']}".strip()
            final_list.append(f"{item['conf']}#{display_name}")
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"УСПЕХ: Обновлено {len(results)} серверов с реальными флагами.")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
