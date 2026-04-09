import requests, os, socket, re, time

# --- НАСТРОЙКИ ---
GID = "635b44b708e61127ccb3c672316590e5" # Твой ID Gist вписан прямо сюда
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
            with socket.create_connection((host, port), timeout=1.2):
                latency = int((time.time() - start) * 1000)
                # Очистка названия от рекламы
                clean_conf = re.sub(r'#.*', '', config)
                return {"conf": clean_conf, "ping": latency, "host": host}
    except: pass
    return None

def run():
    print("--- ЗАПУСК УЛЬТРА-ОЧИСТКИ ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=20).text
            found = re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res)
            all_configs.extend(found)
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Всего ключей: {len(unique)}")

    results = []
    # Проверяем до 2000 серверов
    for c in unique[:2000]:
        res = check_server(c)
        if res: results.append(res)
    
    # Сортировка по пингу (от быстрых к медленным)
    results.sort(key=lambda x: x['ping'])
    print(f"Рабочих найдено: {len(results)}")

    if results:
        # Формируем итоговый список с красивыми именами
        final_list = []
        for i, item in enumerate(results):
            # Упрощенное имя: Номер - Пинг - Хост
            name = f"#{i+1} | Ping:{item['ping']}ms | Server"
            final_list.append(f"{item['conf']}#{name}")

        final_url = f"https://github.com{GID}"
        headers = {"Authorization": f"token {GTK}", "Accept": "application/vnd.github.v3+json"}
        payload = {"files": {FILE_NAME: {"content": "\n".join(final_list)}}}
        
        r = requests.patch(final_url, headers=headers, json=payload)
        if r.status_code == 200:
            print("УСПЕХ! Gist обновлен и отсортирован.")
        else:
            print(f"Ошибка API: {r.status_code} - {r.text}")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
