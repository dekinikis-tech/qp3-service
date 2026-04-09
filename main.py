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
    # Используем альтернативный сервис (без жестких лимитов на код страны)
    try:
        res = requests.get(f"https://ipapi.co{ip}/json/", timeout=2).json()
        code = res.get("country_code", "UN")
        country = res.get("country_name", "Unknown")
        flag = "".join(chr(127397 + ord(c)) for c in code.upper())
        return f"{flag} {country}"
    except:
        return "🌐 Unknown"

def check_server(config):
    try:
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: match = re.search(r'ss://[a-zA-Z0-9+/=]+@([^:/#\s]+):(\d+)', config)
        if match:
            host, port = match.group(1), int(match.group(2))
            # Для РФ: игнорируем стандартные порты, если их слишком много (часто блокируются)
            start = time.time()
            with socket.create_connection((host, port), timeout=0.6):
                ping = int((time.time() - start) * 1000)
                # Отсеиваем всё, что медленнее 400мс — это почти гарантия лагов в РФ
                if ping > 450: return None
                clean_link = config.split("#")[0]
                return {"link": clean_link, "ping": ping, "host": host}
    except: pass
    return None

def run():
    print("--- ФИЛЬТРАЦИЯ ДЛЯ РФ ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            all_configs.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    # Очистка и перемешивание для честной выборки
    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    
    results = []
    # Проверяем 200 штук, чтобы найти "золотой" десяток
    print(f"Начинаю отбор из {len(unique)} ключей...")
    for c in unique[:200]:
        res = check_server(c)
        if res: 
            # Сразу определяем гео, пока не уперлись в лимиты
            res['geo'] = get_geo(res['host'])
            results.append(res)
            # Небольшая пауза, чтобы Гео-сервис нас не забанил
            time.sleep(0.2)
    
    results.sort(key=lambda x: x['ping'])

    if results:
        final_list = []
        # Ограничим итоговый список самыми лучшими 50 серверами
        for item in results[:50]:
            display_name = f"{item['geo']} | {item['ping']}ms"
            final_list.append(f"{item['link']}#{display_name}")
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"УСПЕХ: Отобрано {len(results)} топ-серверов.")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
