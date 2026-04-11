import requests, os, re, subprocess, urllib.parse, socket, concurrent.futures, time

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
        "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', 'node', '4jadi']
WHITE_DOMAINS = []

def is_garbage(config):
    try:
        name_raw = config.split('#')[-1] if '#' in config else ""
        name = urllib.parse.unquote(name_raw).strip().lower()
        if not name or len(name) < 4: return True
        # Исправленная проверка регистра
        if any(bad.lower() in name for bad in BLACK_LIST): return True
        if re.sub(r'[-\s]', '', name).isdigit(): return True
        if len(re.findall(r'\d', name)) > 6: return True
        return False
    except:
        return True

def get_tech_score(config):
    score = 0
    c_low = config.lower()
    if 'xtls-rprx-vision' in c_low: score += 2000
    if any(domain in c_low for domain in WHITE_DOMAINS): score += 5000
    if 'security=reality' in c_low: score += 1000
    return score

def check_ping_fast(config_item):
    try:
        config = config_item["config"]
        parsed = urllib.parse.urlparse(config)
        host, port = parsed.hostname, int(parsed.port or 443)
        start = time.time()
        with socket.create_connection((host, port), timeout=2.0):
            ms = int((time.time() - start) * 1000)
            config_item["ping"] = ms
            return config_item
    except:
        return None

def run():
    print("--- ЗАПУСК ОЧИЩЕННОГО СКАНЕРА ---")
    all_raw = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            all_raw.extend(re.findall(r'vless://[^\s\'"<>]+', res))
        except: continue

    unique = list(set(all_raw))
    candidates = []
    for cfg in unique:
        if not is_garbage(cfg):
            score = get_tech_score(cfg)
            if score > 0:
                candidates.append({"config": cfg, "tech_score": score, "ping": 9999})

    real_alive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
        futures = [executor.submit(check_ping_fast, item) for item in candidates]
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res: real_alive.append(res)

    real_alive.sort(key=lambda x: (-x['tech_score'], x['ping']))

    if real_alive:
        to_save = [x['config'] for x in real_alive[:30]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(to_save))
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! Отправлено {len(to_save)} серверов.")
    else:
        print("Ничего не найдено.")

if __name__ == "__main__":
    run()
