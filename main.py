import requests, os, socket, re, time, subprocess, concurrent.futures

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt"
]

def check_is_proxy_alive(config):
    """
    Глубокая проверка: TCP коннект + попытка получить ответ протокола
    """
    try:
        is_modern = any(x in config.lower() for x in ['reality', 'tls', 'security=vless', 'flow=xtls'])
        match = re.search(r'@([^:/#\s]+):(\d+)', config)
        if not match: return None
        
        host, port = match.group(1), int(match.group(2))
        
        start = time.time()
        # 1. Базовый коннект
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect((host, port))
        
        # 2. Пытаемся отправить "мусорный" HTTP запрос. 
        # Рабочие Xray/V2ray сервера часто настроены отвечать на некорректные данные мгновенно (fallback),
        # а заблокированные или мертвые порты просто "проглотят" байты или будут висеть.
        s.send(b"GET / HTTP/1.1\r\n\r\n")
        
        # Пытаемся считать хоть 1 байт ответа
        response = s.recv(1)
        s.close()
        
        ping = int((time.time() - start) * 1000)
        
        # Очень жесткие критерии для РФ:
        if not is_modern and ping > 300: return None # Простые vless выше 300мс - мусор
        if is_modern and ping > 800: return None
        
        return {"config": config, "ping": ping, "modern": is_modern}
    except:
        return None

def run():
    print("--- ГЛУБОКАЯ ПРОВЕРКА ДАННЫХ ---")
    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10).text
            raw_data.extend(re.findall(r'(?:vless|vmess|ss)://[^\s\'"<>]+', res))
        except: continue

    unique = list(set([c.strip() for c in raw_data if len(c) > 50]))
    print(f"Всего ключей: {len(unique)}")

    results = []
    # Проверяем всю базу в 100 потоков
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = {executor.submit(check_is_proxy_alive, c): c for c in unique}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: results.append(res)
    
    # Сортировка: Modern (Reality/TLS) всегда в топе, затем по пингу
    results.sort(key=lambda x: (not x['modern'], x['ping']))

    if results:
        # Выгружаем ТОП-30. Если их мало - значит это реально работающие.
        final_list = [item['config'] for item in results[:30]]
        
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        cmd = f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}'
        subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"УСПЕХ! Найдено {len(results)} потенциально рабочих. В Gist ушло ТОП-30.")
    else:
        print("Рабочих серверов не найдено.")

if __name__ == "__main__":
    run()
