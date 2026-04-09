import requests, os, re, subprocess

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Твои источники
SOURCES = [
   "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt"
]

def run():
    print("--- ГЛУБОКИЙ ПОИСК ПО ВСЕМ RU-МАСКИРОВКАМ ---")
    
    # Расширенный список признаков (RU-SNI, маскировка и воркеры)
    patterns = [
        # Твои домены
        r'sni=ads\.x5\.ru',
        r'sni=cdnv-img\.perekrestok\.ru',
        r'sni=m\.vk\.ru',
        r'sni=goya\.rutube\.ru',
        r'serviceName=UpdateService',
        # Дополнительные рабочие SNI для РФ
        r'sni=vk\.com',
        r'sni=m\.vk\.com',
        r'sni=elvis\.v2ray',
        r'sni=yandex\.ru',
        r'sni=yastatic\.net',
        r'sni=ozon\.ru',
        r'sni=avito\.ru',
        r'sni=gosuslugi\.ru',
        r'sni=sberbank\.ru',
        r'sni=tinkoff\.ru',
        r'sni=magnit\.ru',
        r'sni=ok\.ru',
        r'sni=wildberries\.ru',
        # Технологические признаки (Vision и Workers)
        r'flow=xtls-rprx-vision',
        r'workers\.dev',
        r'eu\.org',
        r'pages\.dev',
        r'security=reality'
    ]

    raw_data = []
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            links = re.findall(r'vless://[^\s\'"<>]+', res)
            
            for link in links:
                # Если в ссылке есть ХОТЯ БЫ ОДИН признак из списка
                if any(re.search(p, link, re.IGNORECASE) for p in patterns):
                    # Проверяем, чтобы ссылка была полной (длинной)
                    if len(link) > 120 or 'workers.dev' in link:
                        raw_data.append(link.strip())
        except: continue

    # Убираем дубликаты
    final_list = list(dict.fromkeys(raw_data))

    if final_list:
        print(f"Найдено {len(final_list)} потенциально рабочих серверов.")
        # Берем последние 100, чтобы не перегружать список (самые свежие)
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list[-100:]))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print("УСПЕХ! Gist обновлен.")
    else:
        print("Подходящих серверов не найдено.")

if __name__ == "__main__":
    run()
