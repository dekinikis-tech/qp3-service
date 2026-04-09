import requests, os, re, subprocess

GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"

# Источники, которые специализируются на обходе блокировок в РФ
SOURCES = [
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/26.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/1.txt",
    "https://github.com/AvenCores/goida-vpn-configs/raw/refs/heads/main/githubmirror/6.txt" # Специальный RU-источник
]

def run():
    print("--- ФОРМИРОВАНИЕ ПРЯМОГО СПИСКА (RU-STABLE) ---")
    raw_data = []
    
    # Ключевые слова из твоих рабочих ссылок
    target_marks = ['reality', 'xtls-rprx-vision', 'grpc', 'workers.dev']
    ru_sni = ['vk.com', 'rutube', 'perekrestok', 'x5.ru', 'yandex', 'ozon']

    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15).text
            # Вытаскиваем все VLESS
            links = re.findall(r'vless://[^\s\'"<>]+', res)
            
            for link in links:
                link_low = link.lower()
                # ФИЛЬТР: Берем только то, что реально имеет шансы в РФ
                # Должен быть современный протокол И (RU-маскировка ИЛИ Cloudflare)
                is_modern = any(m in link_low for m in target_marks)
                is_adapted = any(s in link_low for s in ru_sni) or 'workers.dev' in link_low
                
                if is_modern and is_adapted and len(link) > 150:
                    raw_data.append(link.strip())
        except: continue

    # Убираем дубликаты и берем последние 50 (самые свежие из файлов)
    unique_links = list(dict.fromkeys(raw_data)) # Сохраняем порядок
    final_list = unique_links[-50:] 

    if final_list:
        print(f"Найдено {len(final_list)} потенциально 'бетонных' серверов.")
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\n".join(final_list))
            
        subprocess.run(f'gh gist edit {GID} -f "{FILE_NAME}" {FILE_NAME}', shell=True)
        print("УСПЕХ! Gist обновлен свежими RU-адаптированными ссылками.")
    else:
        print("Подходящих ссылок не найдено.")

if __name__ == "__main__":
    run()
