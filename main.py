import requests, os, re, subprocess, json, time, concurrent.futures, urllib.parse, queue, socket, statistics

# ============================================================
# НАСТРОЙКИ
# ============================================================
GID        = os.environ.get('MY_GIST_ID')
FILE_NAME  = "vps.txt"
XRAY_BIN   = "xray"
TOP_N      = 50

MAX_WORKERS = 10
PING_ROUNDS = 3

# Максимально допустимый средний пинг (мс)
MAX_PING_MS = 3000

# При PING_ROUNDS=3: 0.5 = хватит 2 успешных из 3
MAX_LOSS_RATE = 0.5

# Таймаут одного HTTP-запроса через прокси (сек)
REQUEST_TIMEOUT = 8.0

# Максимальное время ожидания старта xray (сек)
XRAY_START_TIMEOUT = 4.0

# URL-цели для проверки (пробуем по очереди)
TEST_URLS = [
    "http://www.gstatic.com/generate_204",
    "http://cp.cloudflare.com/",
    "http://connectivitycheck.gstatic.com/generate_204",
]

SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt"
]

BLACK_LIST = [
    'meshky', '4mohsen', 'white', '708087', 'anycast',
    'oneclick', 'ipv6', '4jadi', '4kian', 'yandex.net', 'vk-apps.com',
]

BLOCKED_IPS = (
    '104.', '172.64.', '172.65.', '172.66.', '172.67.',
    '188.114.', '162.159.', '108.162.', '158.160.',
    '51.250.', '84.201.',
)

VLESS_REGEX = re.compile(
    r"vless://(?P<uuid>[^@]+)@(?P<host>[^:?#]+):(?P<port>\d+)\??(?P<query>[^#]+)?#?(?P<n>.*)?"
)

port_queue: queue.Queue = queue.Queue()
for _p in range(25000, 25000 + MAX_WORKERS):
    port_queue.put(_p)


def _wait_for_port(host: str, port: int, timeout: float) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return True
        except OSError:
            time.sleep(0.05)
    return False


def _build_xray_config(data: dict, port: int) -> dict:
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


def test_via_xray(vless_url: str):
    """
    Сервер считается РАБОЧИМ только если:
    - xray успешно запустился
    - хотя бы 1 запрос вернул HTTP-ответ
    - процент потерь <= MAX_LOSS_RATE
    - средний пинг <= MAX_PING_MS
    """
    port     = port_queue.get()
    cfg_file = f"cfg_{port}.json"
    proc     = None

    try:
        match = VLESS_REGEX.match(vless_url)
        if not match:
            return None

        data    = match.groupdict()
        address = data['host']

        if address.startswith(BLOCKED_IPS):
            return None
        if ':' in address:
            return None

        config = _build_xray_config(data, port)
        with open(cfg_file, "w") as f:
            json.dump(config, f)

        proc = subprocess.Popen(
            [XRAY_BIN, "run", "-c", cfg_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        if not _wait_for_port("127.0.0.1", port, XRAY_START_TIMEOUT):
            return None

        proxies = {
            "http":  f"http://127.0.0.1:{port}",
            "https": f"http://127.0.0.1:{port}",
        }
        session           = requests.Session()
        session.trust_env = False
        session.proxies   = proxies

        pings  = []
        losses = 0

        for _ in range(PING_ROUNDS):
            success = False
            # Пробуем несколько тестовых URL — берём первый успешный
            for test_url in TEST_URLS:
                try:
                    t0 = time.perf_counter()
                    r  = session.get(
                        test_url,
                        timeout=REQUEST_TIMEOUT,
                        allow_redirects=True,
                    )
                    elapsed = int((time.perf_counter() - t0) * 1000)
                    # Любой HTTP-ответ — значит сервер работает
                    if r.status_code in (200, 204, 301, 302):
                        pings.append(elapsed)
                        success = True
                        break
                except Exception:
                    continue

            if not success:
                losses += 1

        # Должен быть хотя бы 1 успешный запрос
        if not pings:
            return None

        loss_rate = losses / PING_ROUNDS
        if loss_rate > MAX_LOSS_RATE:
            return None

        avg_ping = int(statistics.mean(pings))
        if avg_ping > MAX_PING_MS:
            return None

        jitter = int(statistics.stdev(pings)) if len(pings) > 1 else 0
        score  = avg_ping + jitter // 2

        return (vless_url, score, avg_ping, jitter, losses)

    except Exception:
        return None

    finally:
        if proc:
            try:
                proc.terminate()
                proc.wait(timeout=1.5)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        if os.path.exists(cfg_file):
            os.remove(cfg_file)
        port_queue.put(port)


def fetch_configs() -> list[str]:
    all_raw: list[str] = []
    headers = {'User-Agent': 'Mozilla/5.0'}

    for url in SOURCES:
        try:
            res = requests.get(url, timeout=15, headers=headers).text
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


def run():
    print("=" * 60)
    print("  ЗАПУСК ПРОВЕРКИ VPN-СЕРВЕРОВ")
    print(f"  Раундов на сервер : {PING_ROUNDS}")
    print(f"  Макс. пинг        : {MAX_PING_MS} мс")
    print(f"  Макс. потери      : {int(MAX_LOSS_RATE * 100)}%")
    print(f"  Таймаут запроса   : {REQUEST_TIMEOUT} сек")
    print(f"  Таймаут xray      : {XRAY_START_TIMEOUT} сек")
    print("=" * 60)

    print("\n[1/3] Сбор конфигов...")
    candidates = fetch_configs()
    print(f"\nВсего уникальных кандидатов после фильтрации: {len(candidates)}\n")

    if not candidates:
        print("Нет кандидатов для проверки.")
        return

    print("[2/3] Тестирование серверов...")
    results = []
    tested  = 0
    total   = len(candidates)

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(test_via_xray, url): url for url in candidates}

        for future in concurrent.futures.as_completed(futures):
            tested += 1
            if tested % 25 == 0 or tested == total:
                passed = len(results)
                print(f"  Прогресс: {tested}/{total}  |  Прошли: {passed}")

            res = future.result()
            if res:
                results.append(res)

    print(f"\n[3/3] Сохранение результатов...")

    if not results:
        print("\n❌ Нет рабочих серверов. В Gist ничего не записываем.")
        return

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

    final_urls = [r[0] for r in top]
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        f.write("\n".join(final_urls))

    print(f"\n✅ Сохранено {len(final_urls)} рабочих серверов в {FILE_NAME}")

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
    else:
        print("⚠️  MY_GIST_ID не задан — Gist не обновляется.")


if __name__ == "__main__":
    run()
