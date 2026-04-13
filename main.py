import requests, os, re, subprocess, json, time, concurrent.futures
import urllib.parse, queue, socket, statistics

# ============================================================
# НАСТРОЙКИ
# ============================================================
GID        = os.environ.get('MY_GIST_ID')
FILE_NAME  = "vps.txt"
XRAY_BIN   = "xray"
TOP_N      = 50

# Этап 1 — быстрый TCP-пинг (много воркеров, без xray)
TCP_WORKERS     = 100
TCP_TIMEOUT     = 1.5   # сек

# Этап 2 — глубокая проверка через xray (только выжившие)
XRAY_WORKERS        = 15
PING_ROUNDS         = 2
MAX_PING_MS         = 4000
MAX_LOSS_RATE       = 0.5
REQUEST_TIMEOUT     = 7.0
XRAY_START_TIMEOUT  = 3.5

TEST_URLS = [
    "http://www.gstatic.com/generate_204",
    "http://cp.cloudflare.com/",
    "http://connectivitycheck.gstatic.com/generate_204",
]

SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile-2.txt",
    "https://raw.githubusercontent.com/AvenCores/goida-vpn-configs/refs/heads/main/githubmirror/26.txt",
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
for _p in range(25000, 25000 + XRAY_WORKERS):
    port_queue.put(_p)


# ============================================================
# ЭТАП 1: БЫСТРАЯ TCP-ПРОВЕРКА
# ============================================================

def tcp_alive(vless_url: str) -> str | None:
    """
    Просто проверяем, открыт ли TCP-порт сервера.
    Не запускаем xray, не шифруем — просто connect().
    Быстро: ~0.1-1.5 сек на сервер.
    """
    match = VLESS_REGEX.match(vless_url)
    if not match:
        return None

    data    = match.groupdict()
    address = data['host']
    port    = int(data['port'])

    # Фильтры
    if address.startswith(BLOCKED_IPS):
        return None
    if ':' in address:  # IPv6
        return None
    if any(bad in urllib.parse.unquote(vless_url).lower() for bad in BLACK_LIST):
        return None

    try:
        with socket.create_connection((address, port), timeout=TCP_TIMEOUT):
            return vless_url
    except OSError:
        return None


# ============================================================
# ЭТАП 2: ГЛУБОКАЯ ПРОВЕРКА ЧЕРЕЗ XRAY
# ============================================================

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
        "inbounds": [{"listen": "127.0.0.1", "port": port, "protocol": "http"}],
        "outbounds": [{
            "protocol": "vless",
            "settings": {
                "vnext": [{
                    "address": address,
                    "port":    server_port,
                    "users":   [{"id": data['uuid'], "encryption": "none", "flow": q("flow")}],
                }]
            },
            "streamSettings": stream,
        }],
    }


def test_via_xray(vless_url: str):
    """Полная проверка через xray — только для серверов прошедших TCP-тест."""
    port     = port_queue.get()
    cfg_file = f"cfg_{port}.json"
    proc     = None

    try:
        match = VLESS_REGEX.match(vless_url)
        if not match:
            return None

        data   = match.groupdict()
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
            for test_url in TEST_URLS:
                try:
                    t0 = time.perf_counter()
                    r  = session.get(test_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
                    elapsed = int((time.perf_counter() - t0) * 1000)
                    if r.status_code in (200, 204, 301, 302):
                        pings.append(elapsed)
                        success = True
                        break
                except Exception:
                    continue
            if not success:
                losses += 1

        if not pings:
            return None
        if losses / PING_ROUNDS > MAX_LOSS_RATE:
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
                try: proc.kill()
                except Exception: pass
        if os.path.exists(cfg_file):
            os.remove(cfg_file)
        port_queue.put(port)


# ============================================================
# СБОР КОНФИГОВ
# ============================================================

def fetch_configs() -> list[str]:
    all_raw: list[str] = []
    headers = {'User-Agent': 'Mozilla/5.0'}

    for url in SOURCES:
        try:
            res   = requests.get(url, timeout=15, headers=headers).text
            found = re.findall(r'vless://[^\s\'"<>]+', res)
            all_raw.extend(found)
            print(f"  [OK] {url}  →  {len(found)} конфигов")
        except Exception as e:
            print(f"  [WARN] Не удалось загрузить {url}: {e}")

    return list(set(all_raw))


# ============================================================
# ГЛАВНЫЙ ЗАПУСК
# ============================================================

def run():
    t_start = time.time()
    print("=" * 60)
    print("  ЗАПУСК ПРОВЕРКИ VPN-СЕРВЕРОВ  (2-этапный)")
    print(f"  TCP-воркеры   : {TCP_WORKERS}  (таймаут {TCP_TIMEOUT}с)")
    print(f"  Xray-воркеры  : {XRAY_WORKERS}  (таймаут {XRAY_START_TIMEOUT}с)")
    print(f"  Раундов       : {PING_ROUNDS},  макс. пинг: {MAX_PING_MS}мс")
    print("=" * 60)

    # --- Сбор ---
    print("\n[1/4] Сбор конфигов...")
    all_configs = fetch_configs()
    print(f"      Итого уникальных: {len(all_configs)}")

    if not all_configs:
        print("Нет кандидатов.")
        return

    # --- Этап 1: TCP ---
    print(f"\n[2/4] Быстрая TCP-проверка ({TCP_WORKERS} воркеров)...")
    alive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=TCP_WORKERS) as ex:
        for url in concurrent.futures.as_completed(
            {ex.submit(tcp_alive, u): u for u in all_configs}
        ):
            result = url.result()
            if result:
                alive.append(result)

    elapsed_tcp = int(time.time() - t_start)
    print(f"      TCP живых: {len(alive)} / {len(all_configs)}  ({elapsed_tcp}с)")

    if not alive:
        print("Нет живых серверов после TCP-проверки.")
        return

    # --- Этап 2: Xray ---
    print(f"\n[3/4] Глубокая xray-проверка {len(alive)} серверов ({XRAY_WORKERS} воркеров)...")
    results  = []
    tested   = 0
    total    = len(alive)

    with concurrent.futures.ThreadPoolExecutor(max_workers=XRAY_WORKERS) as ex:
        futures = {ex.submit(test_via_xray, u): u for u in alive}
        for future in concurrent.futures.as_completed(futures):
            tested += 1
            if tested % 10 == 0 or tested == total:
                print(f"  Прогресс: {tested}/{total}  |  Прошли xray: {len(results)}")
            res = future.result()
            if res:
                results.append(res)

    elapsed_total = int(time.time() - t_start)

    # --- Сохранение ---
    print(f"\n[4/4] Сохранение...")

    if not results:
        print("❌ Нет рабочих серверов.")
        return

    results.sort(key=lambda x: x[1])
    top = results[:TOP_N]

    print(f"\n{'─'*60}")
    print(f"  Всего: {len(all_configs)} → TCP: {len(alive)} → xray: {len(results)} → топ: {len(top)}")
    print(f"  Время: {elapsed_total}с")
    print(f"{'─'*60}")

    for i, (url, score, avg, jitter, losses) in enumerate(top[:10], 1):
        name = urllib.parse.unquote(url.split('#')[-1])[:40] if '#' in url else url[8:48]
        print(f"  {i:<3} {avg:>5}мс  jitter:{jitter:>4}мс  loss:{losses}/{PING_ROUNDS}  {name}")

    if len(top) > 10:
        print(f"  ... ещё {len(top)-10}")

    final_urls = [r[0] for r in top]
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        f.write("\n".join(final_urls))

    print(f"\n✅ Сохранено {len(final_urls)} серверов в {FILE_NAME}")

    if GID:
        print("Обновляем Gist...")
        res = subprocess.run(
            ["gh", "gist", "edit", GID, "-f", FILE_NAME, FILE_NAME],
            capture_output=True, text=True
        )
        if res.returncode == 0:
            print("✅ Gist обновлён.")
        else:
            print(f"❌ Gist ошибка: {res.stderr.strip()}")
    else:
        print("⚠️  MY_GIST_ID не задан.")


if __name__ == "__main__":
    run()
