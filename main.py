import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse

# --- НАСТРОЙКИ ---
GID = os.environ.get('MY_GIST_ID')
FILE_NAME = "vps.txt"
XRAY_BIN = "xray"
SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/V2RayRoot/V2RayConfig/refs/heads/main/Config/vless.txt",
    "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt"
]
BLACK_LIST = ['meshky', '4mohsen', 'white', '708087', 'anycast', 'oneclick', 'ipv6', '4jadi', '4kian']

# --- ДИАГНОСТИЧЕСКАЯ ФУНКЦИЯ ---
def test_via_xray(vless_url, port_offset):
    """
    Функция с расширенным логированием для диагностики.
    """
    socks_port = 26000 + port_offset
    cfg_file = f"cfg_{socks_port}.json"
    proc = None
    
    # Выводим имя для отладки
    try:
        name = urllib.parse.unquote(vless_url.split('#')[-1])
    except:
        name = "NoName"
    
    try:
        parsed = urllib.parse.urlparse(vless_url)
        params = urllib.parse.parse_qs(parsed.query)
        
        def get_p(key, default=""):
            val = params.get(key, [default])
            return val[0]

        config_json = {
            "log": {"loglevel": "warning"}, # Включаем логи Xray
            "inbounds": [{"port": socks_port, "protocol": "socks", "settings": {"udp": True}}],
            "outbounds": [{
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": parsed.hostname,
                        "port": int(parsed.port or 443),
                        "users": [{"id": parsed.username, "encryption": "none", "flow": get_p("flow")}]
                    }]
                },
                "streamSettings": {
                    "network": get_p("type", "tcp"),
                    "security": get_p("security", "none")
                }
            }]
        }
        
        ss = config_json["outbounds"][0]["streamSettings"]
        if ss["security"] == "reality":
            ss["realitySettings"] = {"publicKey": get_p("pbk"), "fingerprint": get_p("fp", "chrome"), "serverName": get_p("sni"), "shortId": get_p("sid")}
        elif ss["security"] == "tls":
            ss["tlsSettings"] = {"serverName": get_p("sni", parsed.hostname)}

        with open(cfg_file, "w") as f:
            json.dump(config_json, f, indent=2) # Сохраняем с форматированием для легкой отладки
        
        # Запускаем Xray, но теперь захватываем его вывод ошибок (stderr)
        proc = subprocess.Popen([XRAY_BIN, "run", "-c", cfg_file], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        time.sleep(2)

        # Проверяем, не завершился ли Xray с ошибкой сразу
        if proc.poll() is not None:
            stdout, stderr = proc.communicate()
            print(f"  [-] ПРОВАЛ ({name}): Xray не запустился. Ошибка:\n{stderr}")
            return None
        
        is_ok = False
        try:
            proxies = {"http": f"socks5h://127.0.0.1:{socks_port}", "https": f"socks5h://127.0.0.1:{socks_port}"}
            r = requests.get("http://google.com/generate_204", proxies=proxies, timeout=5)
            if r.status_code == 204:
                is_ok = True
        except Exception as e:
            # ВОТ КЛЮЧЕВОЙ МОМЕНТ: мы выводим точную ошибку
            print(f"  [-] ПРОВАЛ ({name}): Ошибка сети -> {type(e).__name__}: {e}")
            pass
        
        return vless_url if is_ok else None
        
    except Exception as e:
        print(f"  [-] КРИТИЧЕСКАЯ ОШИБКА ({name}): Не удалось создать конфиг или запустить Xray -> {e}")
        return None
    finally:
        if proc:
            proc.terminate()
            stdout, stderr = proc.communicate(timeout=2) # Ждем и читаем остатки логов
            if stderr and "failed to find an available port" in stderr:
                 print(f"  [!] ОШИБКА ПОРТА: {stderr.strip()}")
            proc.wait()
        if os.path.exists(cfg_file):
            os.remove(cfg_file)

def run():
    print("--- ЗАПУСК ГЛУБОКОЙ ДИАГНОСТИКИ ---")
    
    # 1. САНИТАРНАЯ ПРОВЕРКА СЕТИ
    print("\n1. Проверка прямого доступа к сети...")
    try:
        r = requests.get("http://google.com/generate_204", timeout=5)
        if r.status_code == 204:
            print("   [OK] Прямой доступ к сети есть.")
        else:
            print(f"   [ПРЕДУПРЕЖДЕНИЕ] Сеть доступна, но вернула статус {r.status_code}.")
    except Exception as e:
        print(f"   [КРИТИЧЕСКАЯ ОШИБКА] Нет прямого доступа к сети: {e}")
        return # Выход, если даже прямой доступ не работает

    # 2. СБОР КОНФИГУРАЦИЙ
    print("\n2. Сбор конфигураций...")
    all_raw, headers = [], {'User-Agent': 'Mozilla/5.0'}
    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
            found = re.findall(r'vless://[^\\s\'"<>]+', res)
            print(f"   Источник: {url[:40]}... | Найдено: {len(found)}")
            all_raw.extend(found)
        except Exception as e:
            print(f"   Не удалось скачать {url[:40]}: {e}")
    
    # 3. ФИЛЬТРАЦИЯ И ПРОВЕРКА
    unique = list(set(all_raw))
    candidates = []
    for cfg in unique:
        if '#' in cfg:
            name = urllib.parse.unquote(cfg.split('#')[-1]).lower()
            if not any(bad in name for bad in BLACK_LIST): candidates.append(cfg)
        else:
            candidates.append(cfg)

    print(f"\n3. Фильтрация и проверка...")
    print(f"   Всего уникальных: {len(unique)}. Кандидатов после фильтрации: {len(candidates)}.")
    # Увеличим количество для повышения шансов
    print(f"   Проверяем топ-200...")
    
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
        futures = {executor.submit(test_via_xray, url, i): url for i, url in enumerate(candidates[:200])}
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            if res:
                name = urllib.parse.unquote(res.split('#')[-1])
                print(f"  [+] РАБОТАЕТ: {name}")
                results.append(res)

    # 4. РЕЗУЛЬТАТ
    print("\n4. Результат")
    if results:
        print(f"   УСПЕХ! Найдено рабочих серверов: {len(results)}. Сохраняем топ-40.")
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            f.write("\\n".join(results[:40]))
        if GID:
            print("   Обновляем Gist...")
            subprocess.run(f'gh gist edit {GID} "{FILE_NAME}"', shell=True, check=True)
            print("   Gist успешно обновлен.")
    else:
        print("   Ни один сервер не прошел проверку Xray. Проанализируйте диагностические логи выше.")

if __name__ == "__main__":
    run()
