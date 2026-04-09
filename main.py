import requests, os, socket, re, time, json, subprocess

# --- НАСТРОЙКИ (ВСЁ ИЗ СЕКРЕТОВ) ---
GID = os.environ.get('MY_GIST_ID')
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
            with socket.create_connection((host, port), timeout=1.0):
                return {"conf": re.sub(r'#.*', '', config), "ping": int((time.time() - start) * 1000)}
    except: pass
    return None

def run():
    print("--- ЗАПУСК ФИНАЛЬНОЙ ВЕРСИИ ---")
    all_configs = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            all_configs.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in all_configs if c.strip()]))
    print(f"Всего ключей в базе: {len(unique)}")

    results = []
    # Проверяем 1500 штук
    for c in unique[:1500]:
        res = check_server(c)
        if res: results.append(res)
    
    results.sort(key=lambda x: x['ping'])
    print(f"Рабочих найдено: {len(results)}")

    if results:
        final_text = "\n".join([f"{item['conf']}##{i+1}_[Ping:{item['ping']}ms]" for i, item in enumerate(results)])
        payload = json.dumps({"files": {FILE_NAME: {"content": final_text}}})
        
        with open("payload.json", "w") as f:
            f.write(payload)
            
        # Формируем URL
        api_url = f"https://github.com{GID}"
        
        # Запуск CURL
        cmd = ["curl", "-L", "-X", "PATCH", 
               "-H", f"Authorization: token {GTK}", 
               "-H", "Content-Type: application/json", 
               "-d", "@payload.json", api_url]
        
        print("Отправка данных в Gist...")
        process = subprocess.run(cmd, capture_output=True, text=True)
        
        if process.returncode == 0 and "id" in process.stdout.lower():
            print("УСПЕХ! Список обновлен, отсортирован и очищен от рекламы.")
        else:
            print(f"Что-то пошло не так. Статус: {process.returncode}")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
