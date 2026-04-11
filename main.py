import requests, os, re, subprocess, urllib.parse

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

SOURCES = [
        "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
        "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt"
]

# Черный список (теперь мы точно знаем, кого обходить)
BLACK_LIST = ['meshky', '4mohsen', 'white', '708087']

def get_config_quality(config):
    """Оценка по твоим эталонам: Vision + Reality + SNI"""
    score = 0
    c_low = config.lower()
    
    # Главный критерий - наличие Vision (как в твоих примерах)
    if 'xtls-rprx-vision' in c_low: score += 1000
    # Второй критерий - Reality
    if 'security=reality' in c_low: score += 500
    # Третий - правильные браузерные отпечатки
    if 'fp=chrome' in c_low or 'fp=firefox' in c_low: score += 200
    
    # Бонус за надежные SNI из твоего списка
    good_sni = ['microsoft', 'samsung', 'google', 'deepseek', 'union.monster', 'cdnjs']
    if any(s in c_low for s in good_sni): score += 300
    
    return score

def run():
    print("--- СБОР ПО ЭТАЛОННЫМ ПАРАМЕТРАМ ---")
    all_raw = []
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=12, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>|]+', res)
            all_raw.extend(found)
        except: continue

    unique = list(set(all_raw))
    print(f"Всего найдено: {len(unique)}")

    final_selection = []
    for cfg in unique:
        # Убираем мусор и короткие ссылки
        name = urllib.parse.unquote(cfg.split('#')[-1]).lower() if '#' in cfg else ""
        if any(bad in name for bad in BLACK_LIST) or len(name) < 4:
            continue
        
        quality = get_config_quality(cfg)
        # Нам нужны только те, что имеют Vision или Reality
        if quality > 1000: # Оставляем только "элиту" с Vision
            final_selection.append({"config": cfg, "score": quality})

    # Сортируем: самые "жирные" по параметрам - вверх
    final_selection.sort(key=lambda x: x['score'], reverse=True)

    if final_selection:
        # Берем ТОП-20 самых качественных
        to_save = [x['config'] for x in final_selection[:20]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(to_save))
            
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
            print(f"УСПЕХ! В Gist улетели {len(to_save)} 'Vision' серверов.")
    else:
        # Если Vision нет, берем просто лучшие Reality
        print("Vision не найден, ищем Reality...")
        backup = [x['config'] for x in sorted([{"c": c, "s": get_config_quality(c)} for c in unique], key=lambda x: x['s'], reverse=True)[:20]]
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(backup))
        if GID:
            subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)

if __name__ == "__main__":
    run()
