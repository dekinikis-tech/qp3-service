import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse, queue, socket, statistics

# ============================================================
# НАСТРОЙКИ
# ============================================================
GID        = os.environ.get('MY_GIST_ID')
FILE_NAME  = "vps.txt"
XRAY_BIN   = "xray"
TOP_N      = 50

# Количество воркеров (параллельных проверок)
MAX_WORKERS = 10

# Количество тестовых запросов на сервер (чем больше — тем точнее, но дольше)
PING_ROUNDS = 3

# Максимально допустимый средний пинг (мс). Сервера выше — отбрасываем.
MAX_PING_MS = 2000

# Максимально допустимый процент потерь пакетов (0.0 – 1.0)
MAX_LOSS_RATE = 0.34   # допускаем не более 1 потери из 3

# Таймаут одного HTTP-запроса через прокси (сек)
REQUEST_TIMEOUT = 5.0

# Максимальное время ожидания старта xray (сек)
XRAY_START_TIMEOUT = 2.0

SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt"
]

# Стоп-слова в URL/имени сервера
BLACK_LIST = [
    'meshky', '4mohsen', 'white', '708087', 'anycast',
    'oneclick', 'ipv6', '4jadi', '4kian', 'yandex.net', 'vk-apps.com',
]

# Заблокированные IP-префиксы (Cloudflare, Яндекс и др.)
BLOCKED_IPS = (
    '104.', '172.64.', '172.65.', '172.66.', '172.67.',
    '188.114.', '162.159.', '108.162.', '158.160.',
    '51.250.', '84.201.',
)

VLESS_REGEX = re.compile(
    r"vless://(?P<uuid>[^@]+)@(?P<host>[^:?#]+):(?P<port>\d+)\??(?P<query>[^#]+)?#?(?P<name>.*)?"
)

# Очередь портов для параллельных xray-процессов
port_queue: queue.Queue = queue.Queue()
for _p in range(25000, 25000 + MAX_WORKERS):
    port_queue.put(_p)


# ============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================================

def _wait_for_port(host: str, port: int, timeout: float) -> bool:
    """Ждёт, пока TCP-порт станет доступен. Возвращает True при успехе."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.15):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _build_xray_config(data: dict, port: int) -> dict:
    """Собирает конфиг xray из разобранного VLESS URL."""
    address     = data['host']
    server_port = int(data['port'])
    query       = urllib.parse.parse_qs(data.get('query') or '')

    def q(k, d=""):
        return query.get(k, [d])[0]

    sni = q('sni', q('host', address))
    net = q('type', 'tcp')
    sec = q('security', 'none')

    stream: dict = {"network": net, "security": sec}

    if net == "ws":
        stream["wsSettings"] = {
            "path": q("path", "/"),
            "headers": {"Host": q('host', address)},
        }
    elif net == "grpc":
        stream["grpcSettings"] = {"serviceName": q("serviceName", "")}
    elif net == "h2":
        stream["httpSettings"] = {
            "host": [q('host', address)],
            "path": q("path", "/"),
        }

    if sec == "reality":
        stream["realitySettings"] = {
            "serverName":  sni,
            "fingerprint": q("fp", "chrome"),
            "publicKey":   q("pbk"),
            "shortId":     q("sid"),
            "spiderX":     q("spx", "/"),
        }
    elif sec == "tls":
        stream["tlsSettings"] = {
            "serverName":  sni,
            "fingerprint": q("fp", "chrome"),
            "alpn":        ["h2", "http/1.1"],
        }

    return {
        "log": {"loglevel": "none"},
        "inbounds": [{
            "listen":   "127.0.0.1",
            "port":     port,
            "protocol": "http",
        }],
        "outbounds": [{
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": address,
                    "port":    server_port,
                    "users":   [{
                        "id":         data['uuid'],
                        "encryption": "none",
                        "flow":       q("flow"),
                    }],
                }]
            },
            "streamSettings": stream,
        }],
    }


# ============================================================
# ОСНОВНАЯ ФУНКЦИЯ ТЕСТИРОВАНИЯ
# ============================================================

def test_via_xray(vless_url: str):
    """
    Запускает xray с конфигом сервера и выполняет PING_ROUNDS запросов.
    Возвращает (vless_url, средний_пинг, потери) или None если сервер не прошёл.
    """
    port     = port_queue.get()
    cfg_file = f"cfg_{port}.json"
    proc     = None

    try:
        # --- 1. Разбираем URL ---
        match = VLESS_REGEX.match(vless_url)
        if not match:
            return None

        data    = match.groupdict()
        address = data['host']

        if address.startswith(BLOCKED_IPS):
            return None
        if ':' in address:   # IPv6 — пропускаем
            return None

        # --- 2. Пишем конфиг xray ---
        config = _build_xray_config(data, port)
        with open(cfg_file, "w") as f:
            json.dump(config, f)

        # --- 3. Запускаем xray ---
        proc = subprocess.Popen(
            [XRAY_BIN, "run", "-c", cfg_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if not _wait_for_port("127.0.0.1", port, XRAY_START_TIMEOUT):
            return None

        # --- 4. Многократное тестирование ---
        proxies = {
            "http":  f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}",
        }
        session             = requests.Session()
        session.trust_env   = False
        # Явно не используем системные прокси
        session.proxies     = proxies

        pings   = []
        losses  = 0

        for _ in range(PING_ROUNDS):
            try:
                t0 = time.perf_counter()
                r  = session.get(
                    "http://www.gstatic.com/generate_204",
                    timeout=REQUEST_TIMEOUT,
                )
                elapsed = int((time.perf_counter() - t0) * 1000)

                if r.status_code == 204:
                    pings.append(elapsed)
                else:
                    losses += 1
            except Exception:
                losses += 1

        # --- 5. Оцениваем результаты ---
        total        = PING_ROUNDS
        loss_rate    = losses / total

        # Если слишком много потерь — сервер ненадёжный
        if loss_rate > MAX_LOSS_RATE:
            return None

        # Если ни один запрос не прошёл — отбрасываем
        if not pings:
            return None

        avg_ping = int(statistics.mean(pings))

        # Если средний пинг слишком высокий — отбрасываем
        if avg_ping > MAX_PING_MS:
            return None

        # Jitter (разброс пинга) — штрафуем нестабильные сервера
        jitter = int(statistics.stdev(pings)) if len(pings) > 1 else 0

        # Итоговый "счёт" сервера: средний пинг + штраф за нестабильность
        # Чем меньше — тем лучше
        score = avg_ping + jitter // 2

        return (vless_url, score, avg_ping, jitter, losses)

    except Exception:
        return None

    finally:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=1.0)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if os.path.exists(cfg_file):
            os.remove(cfg_file)
        port_queue.put(port)


# ============================================================
# СБОР И ФИЛЬТРАЦИЯ КОНФИГОВ
# ============================================================

def fetch_configs() -> list[str]:
    """Скачивает конфиги со всех источников и возвращает уникальные кандидаты."""
    all_raw: list[str] = []
    headers = {'User-Agent': 'Mozilla/5.0'}

    for url in SOURCES:
        try:
            res = requests.get(url, timeout=10, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>]+', res)
            all_raw.extend(found)
            print(f"  [OK] {url}  →  найдено: {len(found)}")
        except Exception as e:
            print(f"  [WARN] Не удалось загрузить {url}: {e}")

    unique = list(set(all_raw))

    candidates = [
        cfg for cfg in unique
        if not any(bad in urllib.parse.unquote(cfg).lower() for bad in BLACK_LIST)
    ]

    return candidates


# ============================================================
# ГЛАВНЫЙ ЗАПУСК
# ============================================================

def run():
    print("=" * 60)
    print("  ЗАПУСК ПРОВЕРКИ VPN-СЕРВЕРОВ")
    print(f"  Раундов на сервер : {PING_ROUNDS}")
    print(f"  Макс. пинг        : {MAX_PING_MS} мс")
    print(f"  Макс. потери      : {int(MAX_LOSS_RATE * 100)}%")
    print("=" * 60)

    # --- Сбор ---
    print("\n[1/3] Сбор конфигов...")
    candidates = fetch_configs()
    print(f"\nВсего уникальных кандидатов после фильтрации: {len(candidates)}\n")

    if not candidates:
        print("Нет кандидатов для проверки.")
        return

    # --- Тестирование ---
    print("[2/3] Тестирование серверов...")
    results     = []
    tested      = 0
    total       = len(candidates)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_via_xray, url): url for url in candidates}

        for future in concurrent.futures.as_completed(futures):
            tested += 1
            if tested % 50 == 0 or tested == total:
                passed = len(results)
                print(f"  Прогресс: {tested}/{total}  |  Прошли: {passed}")

            res = future.result()
            if res:
                results.append(res)

    # --- Сортировка и сохранение ---
    print(f"\n[3/3] Сохранение результатов...")

    if not results:
        print("\n❌ Нет рабочих серверов.")
        return

    # Сортируем по score (пинг + штраф за jitter)
    results.sort(key=lambda x: x[1])
    top = results[:TOP_N]

    print(f"\n{'─'*60}")
    print(f"  ИТОГ: проверено {total}, прошли {len(results)}, сохраняем топ {len(top)}")
    print(f"{'─'*60}")
    print(f"  {'#':<4} {'Пинг':>6} {'Jitter':>8} {'Потери':>8}   Сервер")
    print(f"  {'─'*4} {'─'*6} {'─'*8} {'─'*8}   {'─'*30}")

    for i, (url, score, avg, jitter, losses) in enumerate(top[:10], 1):
        name = urllib.parse.unquote(url.split('#')[-1])[:35] if '#' in url else url[8:45]
        print(f"  {i:<4} {avg:>5}мс  {jitter:>6}мс  {losses}/{PING_ROUNDS}      {name}")

    if len(top) > 10:
        print(f"  ... и ещё {len(top) - 10} серверов")

    # Сохраняем только URL
    final_urls = [r[0] for r in top]
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        f.write("\n".join(final_urls))

    print(f"\n✅ Сохранено в {FILE_NAME}")

    # --- Обновляем Gist ---
    if GID:
        print("Обновляем Gist...")
        result = subprocess.run(
            ["gh", "gist", "edit", GID, "-f", FILE_NAME, FILE_NAME],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("✅ Gist обновлён.")
        else:
            print(f"❌ Ошибка обновления Gist: {result.stderr.strip()}")


if __name__ == "__main__":
    run()
