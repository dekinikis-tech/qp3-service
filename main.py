import requests, os, re, subprocess, json, time, concurrent.futures
import urllib.parse, queue, socket, statistics, base64, urllib.request as url_req

# ============================================================
# НАСТРОЙКИ
# ============================================================
GID         = os.environ.get('MY_GIST_ID')
FILE_NAME   = "vps.txt"
SUB_FILE    = "sub.txt"    # Base64-подписка для V2RayNG / Nekobox / Streisand
VIEWER_FILE = "index.html"
XRAY_BIN    = "xray"
TOP_N_EACH  = 150   # топ отдельно для зарубежных И для российских

# Этап 1 — быстрый TCP-пинг
TCP_WORKERS    = 100
TCP_TIMEOUT    = 1.5

# Этап 2 — глубокая проверка через xray
# Динамические таймауты: если MY_SLOW_NET=1 — увеличиваем пороги для медленных соединений
_slow = os.environ.get('MY_SLOW_NET') == '1'
XRAY_WORKERS       = 15
PING_ROUNDS        = 3
MAX_PING_MS        = 6000  if _slow else 4000
MAX_LOSS_RATE      = 0.67  if _slow else 0.5
REQUEST_TIMEOUT    = 12.0  if _slow else 7.0
XRAY_START_TIMEOUT = 5.0   if _slow else 3.5

TEST_URLS = [
    "http://www.instagram.com/",
    "http://www.facebook.com/",
    "http://www.gstatic.com/generate_204",
    "http://cp.cloudflare.com/",
]

SOURCES = [
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_VLESS_RUS_mobile.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/BLACK_SS+All_RUS.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-CIDR-RU-checked.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/WHITE-SNI-RU-all.txt",
    "https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/refs/heads/main/Vless-Reality-White-Lists-Rus-Mobile.txt",
]
BLACK_LIST = [
    'meshky', '4mohsen', 'white', '708087',
    'oneclick', '4jadi', '4kian', 'yandex.net', 'vk-apps.com',
]

BLOCKED_IPS = (
    '104.', '172.64.', '172.65.', '172.66.', '172.67.',
    '188.114.', '162.159.', '108.162.', '158.160.',
    '51.250.', '84.201.',
)

RU_IP_PREFIXES = (
    '46.8.', '46.17.', '46.29.', '46.36.', '46.39.', '46.40.', '46.41.',
    '46.101.', '46.102.', '46.148.', '77.37.', '77.91.', '79.133.', '79.174.',
    '80.64.', '80.87.', '80.240.', '80.250.', '82.146.', '82.148.', '83.166.',
    '83.220.', '83.222.', '85.10.', '85.119.', '85.142.', '85.143.', '85.209.',
    '86.62.', '87.117.', '87.249.', '88.218.', '89.108.', '89.110.', '89.111.',
    '89.249.', '90.150.', '90.156.', '91.90.', '91.108.', '91.185.', '91.193.',
    '91.194.', '91.213.', '91.215.', '91.217.', '91.219.', '91.220.', '91.221.',
    '91.222.', '91.223.', '92.63.', '92.119.', '92.222.', '93.95.', '93.153.',
    '93.157.', '93.158.', '94.26.', '94.130.', '94.140.', '94.142.', '94.143.',
    '94.154.', '94.247.', '95.46.', '95.47.', '95.165.', '95.213.', '95.215.',
    '95.216.', '95.217.', '95.241.', '95.247.', '101.42.', '103.21.', '109.71.',
    '109.172.', '109.195.', '109.234.', '178.18.', '178.21.', '178.124.', '178.137.',
    '178.154.', '178.155.', '185.4.', '185.6.', '185.7.', '185.12.', '185.16.',
    '185.22.', '185.36.', '185.55.', '185.67.', '185.68.', '185.71.', '185.80.',
    '185.83.', '185.87.', '185.100.', '185.103.', '185.105.', '185.112.', '185.123.',
    '185.126.', '185.130.', '185.133.', '185.146.', '185.151.', '185.161.', '185.163.',
    '185.164.', '185.170.', '185.173.', '185.177.', '185.178.', '185.180.', '185.184.',
    '185.185.', '185.188.', '185.189.', '185.190.', '185.191.', '185.192.', '185.195.',
    '185.196.', '185.197.', '185.198.', '185.199.', '185.200.', '185.201.', '185.204.',
    '185.209.', '185.210.', '185.211.', '185.212.', '185.215.', '185.216.', '185.220.',
    '185.225.', '185.226.', '185.229.', '185.230.', '185.231.', '185.234.', '185.238.',
    '185.246.', '185.247.', '195.2.', '195.3.', '195.10.', '195.12.', '195.14.',
    '195.16.', '195.19.', '195.22.', '195.24.', '195.25.', '195.34.', '195.42.',
    '195.43.', '195.47.', '195.49.', '195.58.', '195.62.', '195.64.', '195.65.',
    '195.80.', '195.82.', '195.88.', '195.90.', '195.91.', '195.93.', '195.94.',
    '195.96.', '195.128.', '195.133.', '195.144.', '195.149.', '195.151.', '195.154.',
    '195.160.', '195.161.', '195.162.', '195.163.', '195.165.', '195.166.', '195.168.',
    '195.170.', '195.174.', '195.175.', '195.182.', '195.184.', '195.185.', '195.189.',
    '195.190.', '195.191.', '195.194.', '195.196.', '195.197.', '195.198.', '195.199.',
    '195.200.', '195.201.', '195.203.', '195.204.', '195.206.', '195.208.', '195.209.',
    '195.210.', '195.211.', '195.214.', '195.215.', '195.218.', '195.219.', '195.220.',
    '195.222.', '195.225.', '195.226.', '195.227.', '195.230.', '195.232.', '195.233.',
    '195.234.', '195.238.', '195.239.', '195.240.', '195.242.', '195.244.', '195.245.',
    '195.246.', '195.248.', '195.249.', '195.250.', '195.251.', '195.253.', '195.254.',
    '212.33.', '212.47.', '212.109.', '213.24.', '213.33.', '213.87.', '213.145.',
    '213.148.', '213.167.', '213.183.', '213.184.', '213.188.', '213.189.', '213.194.',
    '213.195.', '213.202.', '213.203.', '213.206.', '213.207.', '213.208.', '213.219.',
    '213.220.', '213.222.', '213.226.', '213.227.', '213.228.', '213.230.', '213.232.',
    '213.234.', '213.243.', '213.248.', '216.24.',
    '158.160.',  # Yandex Cloud
    '51.250.',   # Yandex Cloud
    '84.201.',   # Yandex Cloud
    '130.193.',  # Yandex Cloud
    '62.84.',    # Mail.ru Cloud
    '94.250.',   # VK Cloud
)

RU_DOMAIN_KEYWORDS = (
    '.ru', '.su', 'yandex', 'vk.com', 'vk-apps', 'mail.ru',
    'selectel', 'beget', 'reg.ru', 'timeweb', 'hetzner.ru',
    'serverius', 'aeza.net', 'aeza.ru',
)

VLESS_REGEX = re.compile(
    r"vless://(?P<uuid>[^@]+)@(?P<host>[^:?#]+):(?P<port>\d+)\??(?P<query>[^#]+)?#?(?P<n>.*)?"
)

PROTO_REGEX = re.compile(
    r'(?:vless|trojan|hysteria2|ss)://[^\s\'"<>]+'
)

port_queue: queue.Queue = queue.Queue()
for _p in range(25000, 25000 + XRAY_WORKERS):
    port_queue.put(_p)


# ============================================================
# ГЕОЛОКАЦИЯ
# ============================================================

def _is_russian_server(address: str) -> bool:
    addr_lower = address.lower()
    if any(kw in addr_lower for kw in RU_DOMAIN_KEYWORDS):
        return True
    if address and address[0].isdigit():
        if address.startswith(RU_IP_PREFIXES):
            return True
    return False


# ============================================================
# БЕЗОПАСНОСТЬ СЕРВЕРА
# ============================================================

def _get_proto(url: str) -> str:
    for p in ('vless', 'trojan', 'hysteria2', 'ss'):
        if url.startswith(p + '://'):
            return p.upper()
    return 'UNKNOWN'


def _get_security(url: str) -> str:
    m = re.search(r'[?&]security=([^&#+]+)', url)
    if m:
        return m.group(1)
    if 'trojan://' in url:
        return 'tls'
    return 'none'


def _get_network(url: str) -> str:
    m = re.search(r'[?&]type=([^&#+]+)', url)
    return m.group(1) if m else 'tcp'


def _get_security_level(url: str) -> tuple:
    """
    Возвращает (уровень, иконка, описание):
      'reality'  -> 🔑  Reality/XTLS — максимальная защита
      'secure'   -> 🔒  TLS без allowInsecure
      'insecure' -> ⚠️   allowInsecure=1 или security=none
    """
    sec = _get_security(url)
    allow_insecure = bool(re.search(r'[?&]allowInsecure=1', url))

    if sec == 'reality':
        return 'reality', '\U0001f511', 'Reality/XTLS — максимальная защита'
    if sec == 'tls' and not allow_insecure:
        return 'secure', '\U0001f512', 'TLS — соединение защищено'
    return 'insecure', '\u26a0\ufe0f', 'Небезопасно: нет TLS или allowInsecure=1'


# ============================================================
# ЭТАП 1: БЫСТРАЯ TCP-ПРОВЕРКА
# ============================================================

def _is_ipv6_address(host: str) -> bool:
    return ':' in host or (host.startswith('[') and host.endswith(']'))


def _extract_host_port(url: str):
    for pattern in (
        r'(?:vless|trojan)://[^@]+@([^:/?#\[\]]+|\[[^\]]+\]):(\d+)',
        r'hysteria2://[^@]+@([^:/?#\[\]]+|\[[^\]]+\]):(\d+)',
        r'ss://[^@]+@([^:/?#\[\]]+|\[[^\]]+\]):(\d+)',
    ):
        m = re.match(pattern, url)
        if m:
            return m.group(1).strip('[]'), int(m.group(2))
    return None, None


def tcp_alive(url: str):
    address, port = _extract_host_port(url)
    if address is None:
        return None

    # Отсекаем мусорные данные, чтобы избежать UnicodeError(label too long)
    if len(address) > 253:
        return None

    if _is_ipv6_address(address):
        return None
    if address.startswith(BLOCKED_IPS):
        return None
    addr_lower = address.lower()
    if any(bad in addr_lower for bad in BLACK_LIST):
        return None
    try:
        with socket.create_connection((address, port), timeout=TCP_TIMEOUT):
            return url
    # Ловим UnicodeError и ValueError, чтобы скрипт не падал из-за битых доменов
    except (OSError, UnicodeError, ValueError):
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

    sni    = q('sni', q('host', address))
    net    = q('type', 'tcp')
    sec    = q('security', 'none')
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
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "vless",
                "settings": {
                    "vnext": [{
                        "address": address,
                        "port":    server_port,
                        "users":   [{"id": data['uuid'], "encryption": "none", "flow": q("flow")}],
                    }]
                },
                "streamSettings": stream,
            },
            {"tag": "block", "protocol": "blackhole"}
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [{"type": "field", "outboundTag": "proxy", "network": "tcp,udp"}]
        }
    }


def _build_xray_config_trojan(url: str, port: int):
    m = re.match(
        r'trojan://([^@]+)@([^:/?#\[\]]+|\[[^\]]+\]):(\d+)\??([^#]*)?#?(.*)?', url
    )
    if not m:
        return None

    password    = m.group(1)
    address     = m.group(2).strip('[]')
    server_port = int(m.group(3))
    query       = urllib.parse.parse_qs(m.group(4) or '')

    def q(k, d=""):
        return query.get(k, [d])[0]

    sni    = q('sni', address)
    net    = q('type', 'tcp')
    sec    = q('security', 'tls')
    stream: dict = {"network": net, "security": sec}

    if net == "ws":
        stream["wsSettings"] = {
            "path": urllib.parse.unquote(q("path", "/")),
            "headers": {"Host": q('host', address)},
        }
    elif net == "grpc":
        stream["grpcSettings"] = {"serviceName": q("serviceName", "")}

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
            "allowInsecure": q("allowInsecure", "0") == "1",
            "alpn":        ["h2", "http/1.1"],
        }

    return {
        "log": {"loglevel": "none"},
        "inbounds": [{"listen": "127.0.0.1", "port": port, "protocol": "http"}],
        "outbounds": [
            {
                "tag": "proxy",
                "protocol": "trojan",
                "settings": {
                    "servers": [{"address": address, "port": server_port, "password": password}]
                },
                "streamSettings": stream,
            },
            {"tag": "block", "protocol": "blackhole"}
        ],
        "routing": {
            "domainStrategy": "AsIs",
            "rules": [{"type": "field", "outboundTag": "proxy", "network": "tcp,udp"}]
        }
    }


def _check_google_ban(session: requests.Session) -> bool:
    """
    Проверяет, не забанен ли прокси Google-ом.
    generate_204 должен вернуть 204. Редирект на sorry.google.com = капча/бан.
    Возвращает True если всё нормально (не забанен).
    """
    try:
        r = session.get(
            "http://www.google.com/generate_204",
            timeout=5.0,
            allow_redirects=False,
        )
        if r.status_code == 204:
            return True
        if r.status_code in (301, 302):
            location = r.headers.get('Location', '')
            if 'sorry' in location or 'captcha' in location:
                return False
        return True
    except Exception:
        return True  # не смогли проверить — не штрафуем


def test_via_xray(url: str):
    port     = port_queue.get()
    cfg_file = f"cfg_{port}.json"
    proc     = None
    try:
        if url.startswith('vless://'):
            match = VLESS_REGEX.match(url)
            if not match:
                return None
            config = _build_xray_config(match.groupdict(), port)
        elif url.startswith('trojan://'):
            config = _build_xray_config_trojan(url, port)
            if config is None:
                return None
        else:
            # hysteria2 и ss — TCP прошли, даём условный пинг
            return (url, 9999, 9999, 0, 0)

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

        # --- Проверка на Google-бан ---
        if not _check_google_ban(session):
            return None

        pings  = []
        losses = 0

        for _ in range(PING_ROUNDS):
            success = False
            for test_url in TEST_URLS:
                try:
                    t0      = time.perf_counter()
                    r       = session.get(test_url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
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

        return (url, score, avg_ping, jitter, losses)

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

def _decode_subscription(text: str) -> str:
    stripped = text.strip()
    if re.search(r'(?:vless|trojan|hysteria2|ss)://', stripped):
        return stripped
    for variant in (stripped, stripped.replace('-', '+').replace('_', '/')):
        padded = variant + '=' * ((-len(variant)) % 4)
        try:
            decoded = base64.b64decode(padded).decode('utf-8', errors='ignore')
            if re.search(r'(?:vless|trojan|hysteria2|ss)://', decoded):
                return decoded
        except Exception:
            continue
    lines_decoded = []
    for line in stripped.splitlines():
        line = line.strip()
        if not line:
            continue
        if re.search(r'(?:vless|trojan|hysteria2|ss)://', line):
            lines_decoded.append(line)
            continue
        try:
            padded       = line + '=' * ((-len(line)) % 4)
            decoded_line = base64.b64decode(padded).decode('utf-8', errors='ignore')
            if re.search(r'(?:vless|trojan|hysteria2|ss)://', decoded_line):
                lines_decoded.append(decoded_line)
        except Exception:
            continue
    return '\n'.join(lines_decoded) if lines_decoded else stripped


def _fetch_with_retry(url: str, retries: int = 3, delay: float = 2.0):
    headers = {'User-Agent': 'Mozilla/5.0'}
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, timeout=15, headers=headers)
            r.raise_for_status()
            return r.text
        except Exception as e:
            if attempt < retries:
                print(f"  [RETRY {attempt}/{retries}] {url}: {e}")
                time.sleep(delay)
            else:
                print(f"  [WARN] Не удалось загрузить после {retries} попыток: {url}: {e}")
    return None


def fetch_configs():
    """Возвращает (список уникальных конфигов, множество host:port российских серверов)."""
    all_raw = []
    ru_keys = set()

    for source_url in SOURCES:
        raw_text = _fetch_with_retry(source_url)
        if raw_text is None:
            continue
        text  = _decode_subscription(raw_text)
        found = PROTO_REGEX.findall(text)
        fmt   = "plain" if text is raw_text else "base64"
        print(f"  [OK] {source_url}  ->  {len(found)} конфигов  [{fmt}]")
        all_raw.extend(found)

    # Дедупликация по хосту:порту
    seen_endpoints = set()
    unique = []
    for cfg in all_raw:
        host, port = _extract_host_port(cfg)
        if host and port:
            key = f"{host}:{port}"
            if key not in seen_endpoints:
                seen_endpoints.add(key)
                unique.append(cfg)
                if _is_russian_server(host):
                    ru_keys.add(key)
        else:
            unique.append(cfg)

    return unique, ru_keys


# ============================================================
# ГЕНЕРАЦИЯ HTML
# ============================================================

def generate_html_viewer(intl_results: list, ru_results: list, elapsed: int) -> str:

    def ping_color(avg):
        if avg < 300:   return '#06d6a0'
        if avg < 1000:  return '#ffd166'
        return '#ef476f'

    def make_rows(results):
        rows = []
        for i, (url, score, avg, jitter, losses) in enumerate(results, 1):
            proto    = _get_proto(url)
            security = _get_security(url)
            network  = _get_network(url)
            host, _  = _extract_host_port(url)
            tag      = urllib.parse.unquote(url.split('#')[-1])[:40] if '#' in url else (host or '')[:40]
            is_ru    = _is_russian_server(host or '')
            flag     = '\U0001f1f7\U0001f1fa' if is_ru else '\U0001f30d'
            loss_pct = int(losses / PING_ROUNDS * 100)
            pc       = ping_color(avg)
            safe_url = url.replace('&', '&amp;').replace('"', '&quot;').replace('<', '&lt;').replace("'", '&#39;')
            safe_tag = tag.replace('<', '&lt;').replace('>', '&gt;')

            # Определяем уровень безопасности
            sec_level, sec_icon, sec_tooltip = _get_security_level(url)
            if sec_level == 'reality':
                sec_color = '#a78bfa'
            elif sec_level == 'secure':
                sec_color = '#06d6a0'
            else:
                sec_color = '#ef476f'

            rows.append(
                f'<tr style="border-bottom:1px solid #1e2230">'
                f'<td style="padding:9px 10px;color:#4a5568;width:36px">{i}</td>'
                f'<td style="padding:9px 10px;max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{flag} {safe_tag}</td>'
                f'<td style="padding:9px 10px"><span style="background:#0d2b33;color:#00e5ff;border:1px solid #005f6b;border-radius:4px;padding:2px 7px;font-size:11px;font-weight:700">{proto}</span></td>'
                f'<td style="padding:9px 10px"><span style="background:#1a1f2e;color:#9aa0b4;border:1px solid #2a3040;border-radius:4px;padding:2px 7px;font-size:11px">{network}</span></td>'
                f'<td style="padding:9px 10px"><span style="background:#1a1f2e;color:#9aa0b4;border:1px solid #2a3040;border-radius:4px;padding:2px 7px;font-size:11px">{security}</span></td>'
                f'<td style="padding:9px 10px;text-align:center">'
                f'<span title="{sec_tooltip}" style="font-size:15px;cursor:help;color:{sec_color}">{sec_icon}</span>'
                f'</td>'
                f'<td style="padding:9px 10px;color:{pc};font-weight:700">{avg}ms</td>'
                f'<td style="padding:9px 10px;color:#718096">{jitter}ms</td>'
                f'<td style="padding:9px 10px;color:{"#06d6a0" if loss_pct==0 else "#ef476f"}">{loss_pct}%</td>'
                f'<td style="padding:9px 10px"><button onclick="copyVpn(this)" data-url="{safe_url}" style="background:#0d2b33;border:1px solid #005f6b;color:#00e5ff;border-radius:5px;padding:4px 10px;cursor:pointer;font-size:13px">Copy</button></td>'
                f'</tr>'
            )
        return '\n'.join(rows)

    intl_rows = make_rows(intl_results)
    ru_rows   = make_rows(ru_results)
    total     = len(intl_results) + len(ru_results)
    updated   = time.strftime('%d.%m.%Y %H:%M UTC', time.gmtime())
    best_ping = min((r[2] for r in intl_results), default=0)

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VPN Scout</title>
<style>
body {{ margin:0; padding:0; background:#0a0c10; color:#e2e8f0; font-family:Arial,sans-serif; font-size:13px; }}
h1 {{ margin:0; padding:20px 20px 0; font-size:24px; color:#fff; }}
.info {{ padding:8px 20px 16px; color:#718096; font-size:12px; }}
.info b {{ color:#00e5ff; }}
.legend {{ padding:0 20px 10px; font-size:11px; color:#718096; display:flex; gap:16px; flex-wrap:wrap; }}
.legend span {{ display:flex; align-items:center; gap:4px; }}
.stats-row {{ display:table; width:100%; border-collapse:separate; border-spacing:10px; padding:0 10px 10px; box-sizing:border-box; }}
.stat {{ display:table-cell; background:#111318; border:1px solid #1e2230; border-radius:8px; padding:14px 18px; text-align:center; }}
.stat-num {{ font-size:26px; font-weight:700; color:#fff; }}
.stat-lbl {{ font-size:11px; color:#718096; margin-top:4px; }}
.tab-bar {{ padding:10px 20px; }}
.tab-btn {{
  display:inline-block;
  padding:10px 30px;
  margin-right:8px;
  border-radius:8px;
  border:2px solid #1e2230;
  background:#111318;
  color:#e2e8f0;
  font-size:14px;
  font-weight:700;
  cursor:pointer;
  text-decoration:none;
}}
.tab-btn.active-intl {{ background:#00e5ff; color:#000; border-color:#00e5ff; }}
.tab-btn.active-ru  {{ background:#ff6b35; color:#fff; border-color:#ff6b35; }}
.tab-btn:hover {{ border-color:#718096; }}
.section {{ display:none; padding:0 20px 40px; }}
.section.visible {{ display:block; }}
.tbl-wrap {{ overflow-x:auto; border:1px solid #1e2230; border-radius:8px; }}
table {{ width:100%; border-collapse:collapse; background:#111318; }}
thead th {{ background:#0d1017; color:#718096; font-size:10px; text-transform:uppercase; padding:11px 12px; text-align:left; border-bottom:1px solid #1e2230; white-space:nowrap; }}
tbody tr:hover {{ background:#161b26; }}
#toast {{ position:fixed; bottom:24px; right:24px; background:#06d6a0; color:#000; font-weight:700; font-size:13px; padding:10px 20px; border-radius:8px; opacity:0; transition:opacity .3s; pointer-events:none; z-index:999; }}
#toast.show {{ opacity:1; }}
</style>
</head>
<body>

<h1>VPN Scout</h1>
<div class="info">Обновлено: <b>{updated}</b> &nbsp;|&nbsp; Время проверки: <b>{elapsed}с</b></div>

<div class="legend">
  <span><span style="color:#a78bfa;font-size:14px">🔑</span> Reality/XTLS — максимальная защита</span>
  <span><span style="color:#06d6a0;font-size:14px">🔒</span> TLS — соединение защищено</span>
  <span><span style="color:#ef476f;font-size:14px">⚠️</span> Небезопасно (нет TLS или allowInsecure=1)</span>
</div>

<div class="stats-row">
  <div class="stat"><div class="stat-num" style="color:#00e5ff">{len(intl_results)}</div><div class="stat-lbl">🌍 Зарубежных</div></div>
  <div class="stat"><div class="stat-num" style="color:#ff6b35">{len(ru_results)}</div><div class="stat-lbl">🇷🇺 Российских</div></div>
  <div class="stat"><div class="stat-num">{total}</div><div class="stat-lbl">Всего живых</div></div>
  <div class="stat"><div class="stat-num" style="color:#06d6a0">{best_ping}ms</div><div class="stat-lbl">Лучший пинг</div></div>
</div>

<div class="tab-bar">
  <button class="tab-btn active-intl" id="btn-intl" onclick="showTab('intl')">🌍 Зарубежные ({len(intl_results)})</button>
  <button class="tab-btn" id="btn-ru" onclick="showTab('ru')">🇷🇺 Российские ({len(ru_results)})</button>
</div>

<div class="section visible" id="sec-intl">
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>#</th><th>Сервер</th><th>Протокол</th><th>Транспорт</th><th>Безопасность</th><th>🔒</th><th>Пинг</th><th>Jitter</th><th>Loss</th><th></th></tr></thead>
      <tbody>
        {intl_rows if intl_rows else '<tr><td colspan="10" style="text-align:center;padding:30px;color:#718096">Нет серверов</td></tr>'}
      </tbody>
    </table>
  </div>
</div>

<div class="section" id="sec-ru">
  <div class="tbl-wrap">
    <table>
      <thead><tr><th>#</th><th>Сервер</th><th>Протокол</th><th>Транспорт</th><th>Безопасность</th><th>🔒</th><th>Пинг</th><th>Jitter</th><th>Loss</th><th></th></tr></thead>
      <tbody>
        {ru_rows if ru_rows else '<tr><td colspan="10" style="text-align:center;padding:30px;color:#718096">Нет серверов</td></tr>'}
      </tbody>
    </table>
  </div>
</div>

<div id="toast">Скопировано!</div>

<script>
function showTab(name) {{
  document.getElementById('sec-intl').className = 'section' + (name === 'intl' ? ' visible' : '');
  document.getElementById('sec-ru').className   = 'section' + (name === 'ru'   ? ' visible' : '');
  document.getElementById('btn-intl').className = 'tab-btn' + (name === 'intl' ? ' active-intl' : '');
  document.getElementById('btn-ru').className   = 'tab-btn' + (name === 'ru'   ? ' active-ru'   : '');
}}
function copyVpn(btn) {{
  var url = btn.getAttribute('data-url');
  var ta = document.createElement('textarea');
  ta.value = url;
  ta.style.position = 'fixed';
  ta.style.left = '-9999px';
  document.body.appendChild(ta);
  ta.select();
  try {{
    document.execCommand('copy');
    btn.textContent = 'OK!';
    btn.style.color = '#06d6a0';
    btn.style.borderColor = '#06d6a0';
    var t = document.getElementById('toast');
    t.className = 'show';
    setTimeout(function() {{
      btn.textContent = 'Copy';
      btn.style.color = '#00e5ff';
      btn.style.borderColor = '#005f6b';
      t.className = '';
    }}, 1500);
  }} catch(e) {{ alert('Не удалось скопировать'); }}
  document.body.removeChild(ta);
}}
</script>
</body>
</html>"""


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
    print(f"  Топ каждой гео: {TOP_N_EACH}")
    print(f"  Динамический таймаут (MY_SLOW_NET): {'ВКЛ' if _slow else 'ВЫКЛ'}")
    print(f"  Google-бан фильтр: ВКЛ")
    print(f"  Base64-подписка: {SUB_FILE}")
    print("=" * 60)

    # --- [1/4] Сбор ---
    print("\n[1/4] Сбор конфигов...")
    all_configs, ru_source_keys = fetch_configs()
    print(f"      Итого уникальных (по хосту:порту): {len(all_configs)}")
    if not all_configs:
        print("Нет кандидатов.")
        return

    # --- [2/4] TCP ---
    print(f"\n[2/4] Быстрая TCP-проверка ({TCP_WORKERS} воркеров)...")
    alive = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=TCP_WORKERS) as ex:
        for future in concurrent.futures.as_completed(
            {ex.submit(tcp_alive, u): u for u in all_configs}
        ):
            result = future.result()
            if result:
                alive.append(result)

    elapsed_tcp = int(time.time() - t_start)
    print(f"      TCP живых: {len(alive)} / {len(all_configs)}  ({elapsed_tcp}с)")
    if not alive:
        print("Нет живых серверов после TCP-проверки.")
        return

    # --- [3/4] Xray ---
    print(f"\n[3/4] Глубокая xray-проверка {len(alive)} серверов ({XRAY_WORKERS} воркеров)...")
    results = []
    tested  = 0
    total   = len(alive)

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

    # --- [4/4] Сохранение ---
    print(f"\n[4/4] Сохранение...")
    if not results:
        print("Нет рабочих серверов. Старый файл сохранён.")
        return

    # Сортируем все результаты по score (avg + jitter/2)
    results.sort(key=lambda x: x[1])

    # Делим по адресу сервера
    intl_all = []
    ru_all   = []
    for entry in results:
        host, port = _extract_host_port(entry[0])
        key = f"{host}:{port}" if host and port else ""
        if key in ru_source_keys:
            ru_all.append(entry)
        else:
            intl_all.append(entry)

    intl_results = intl_all[:TOP_N_EACH]
    ru_results   = ru_all[:TOP_N_EACH]

    print(f"\n{'─'*60}")
    print(f"  Всего: {len(all_configs)} -> TCP: {len(alive)} -> xray: {len(results)}")
    print(f"  Зарубежных: найдено {len(intl_all)}, в топе: {len(intl_results)}")
    print(f"  Российских: найдено {len(ru_all)}, в топе: {len(ru_results)}")
    print(f"  Время: {elapsed_total}с")
    print(f"{'─'*60}")

    print("\n  Топ-10 зарубежных:")
    for i, (url, score, avg, jitter, losses) in enumerate(intl_results[:10], 1):
        _, sec_icon, _ = _get_security_level(url)
        name = urllib.parse.unquote(url.split('#')[-1])[:40] if '#' in url else url[8:48]
        print(f"  {i:<3} {avg:>5}мс  jitter:{jitter:>4}мс  loss:{losses}/{PING_ROUNDS}  {sec_icon} {name}")

    if ru_results:
        print("\n  Топ-10 российских:")
        for i, (url, score, avg, jitter, losses) in enumerate(ru_results[:10], 1):
            _, sec_icon, _ = _get_security_level(url)
            name = urllib.parse.unquote(url.split('#')[-1])[:40] if '#' in url else url[8:48]
            print(f"  {i:<3} {avg:>5}мс  jitter:{jitter:>4}мс  loss:{losses}/{PING_ROUNDS}  {sec_icon} {name}")

    # Формируем URL-ы с иконкой безопасности в теге (#...)
    tagged_urls = []
    for r in intl_results + ru_results:
        url = r[0]
        _, sec_icon, _ = _get_security_level(url)
        if '#' in url:
            base, tag = url.rsplit('#', 1)
            clean_tag = urllib.parse.unquote(tag)[:38]
            tagged_urls.append(f"{base}#{sec_icon} {clean_tag}")
        else:
            host, port = _extract_host_port(url)
            tagged_urls.append(f"{url}#{sec_icon} {host}:{port}")

    with open(FILE_NAME, "w", encoding="utf-8") as f:
        f.write("\n".join(tagged_urls))
    print(f"\n Сохранено {len(tagged_urls)} серверов в {FILE_NAME}")

    # Генерируем Base64-подписку (для V2RayNG / Nekobox / Streisand)
    b64_content = base64.b64encode("\n".join(tagged_urls).encode("utf-8")).decode("utf-8")
    with open(SUB_FILE, "w", encoding="utf-8") as f:
        f.write(b64_content)
    print(f" Base64-подписка сохранена в {SUB_FILE}")

    # Генерируем HTML
    html = generate_html_viewer(intl_results, ru_results, elapsed_total)
    with open(VIEWER_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f" HTML-viewer сохранён в {VIEWER_FILE}")

    # Обновляем Gist через GitHub REST API
    if GID:
        print("Обновляем Gist (три файла: vps.txt + sub.txt + index.html)...")

        with open(FILE_NAME, "r", encoding="utf-8") as f:
            vps_content = f.read()
        with open(SUB_FILE, "r", encoding="utf-8") as f:
            sub_content = f.read()
        with open(VIEWER_FILE, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Читаем токен из окружения
        token = os.environ.get('GH_TOKEN')
        if not token:
            try:
                token_res = subprocess.run(
                    ["gh", "auth", "token"], capture_output=True, text=True
                )
                token = token_res.stdout.strip()
            except Exception:
                token = None

        if token:
            payload = json.dumps({
                "files": {
                    FILE_NAME:   {"content": vps_content},
                    SUB_FILE:    {"content": sub_content},
                    VIEWER_FILE: {"content": html_content},
                }
            }).encode("utf-8")

            req = url_req.Request(
                f"https://api.github.com/gists/{GID}",
                data=payload,
                method="PATCH",
                headers={
                    "Authorization":        f"Bearer {token}",
                    "Content-Type":         "application/json",
                    "Accept":               "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                }
            )
            try:
                with url_req.urlopen(req) as resp:
                    if resp.status == 200:
                        print(" Gist обновлён.")
                    else:
                        print(f" Gist ошибка: статус {resp.status}")
            except Exception as e:
                print(f" Gist ошибка: {e}")
        else:
            print(" Не удалось получить токен GitHub (GH_TOKEN)!")
    else:
        print("  MY_GIST_ID не задан.")


if __name__ == "__main__":
    run()
