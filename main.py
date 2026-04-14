import requests, os, re, subprocess, json, time, concurrent.futures
import urllib.parse, queue, socket, statistics, base64

# ============================================================
# НАСТРОЙКИ
# ============================================================
GID        = os.environ.get('MY_GIST_ID')
FILE_NAME  = "vps.txt"
VIEWER_FILE = "index.html"
XRAY_BIN   = "xray"
TOP_N      = 50

# Этап 1 — быстрый TCP-пинг (много воркеров, без xray)
TCP_WORKERS     = 100
TCP_TIMEOUT     = 1.5   # сек

# Этап 2 — глубокая проверка через xray (только выжившие)
XRAY_WORKERS        = 15
PING_ROUNDS         = 3          # FIX: было 2, теперь 3 для адекватного jitter
MAX_PING_MS         = 4000
MAX_LOSS_RATE       = 0.5
REQUEST_TIMEOUT     = 7.0
XRAY_START_TIMEOUT  = 3.5

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

# IP-диапазоны и домены российских хостингов/провайдеров
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
    # Известные RU облака
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
# ОПРЕДЕЛЕНИЕ ГЕОЛОКАЦИИ СЕРВЕРА
# ============================================================

def _is_russian_server(address: str) -> bool:
    """Определяет, является ли сервер российским по IP или домену."""
    addr_lower = address.lower()
    if any(kw in addr_lower for kw in RU_DOMAIN_KEYWORDS):
        return True
    if address[0].isdigit():  # это IP, не домен
        if address.startswith(RU_IP_PREFIXES):
            return True
    return False


# ============================================================
# ЭТАП 1: БЫСТРАЯ TCP-ПРОВЕРКА
# ============================================================

def _is_ipv6_address(host: str) -> bool:
    return ':' in host or (host.startswith('[') and host.endswith(']'))


def _extract_host_port(url: str):
    m = re.match(r'(?:vless|trojan)://[^@]+@([^:/?#\[\]]+|\[[^\]]+\]):(\d+)', url)
    if m:
        return m.group(1).strip('[]'), int(m.group(2))
    m = re.match(r'hysteria2://[^@]+@([^:/?#\[\]]+|\[[^\]]+\]):(\d+)', url)
    if m:
        return m.group(1).strip('[]'), int(m.group(2))
    m = re.match(r'ss://[^@]+@([^:/?#\[\]]+|\[[^\]]+\]):(\d+)', url)
    if m:
        return m.group(1).strip('[]'), int(m.group(2))
    return None, None


def tcp_alive(url: str) -> str | None:
    address, port = _extract_host_port(url)
    if address is None:
        return None
    if _is_ipv6_address(address):
        return None
    if address.startswith(BLOCKED_IPS):
        return None

    # FIX: проверяем BLACK_LIST только по хосту, а не по всему URL
    addr_lower = address.lower()
    if any(bad in addr_lower for bad in BLACK_LIST):
        return None

    try:
        with socket.create_connection((address, port), timeout=TCP_TIMEOUT):
            return url
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


def _build_xray_config_trojan(url: str, port: int) -> dict | None:
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

    sni = q('sni', address)
    net = q('type', 'tcp')
    sec = q('security', 'tls')

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


def test_via_xray(url: str):
    """Полная проверка через xray — только для серверов прошедших TCP-тест."""
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
            padded = line + '=' * ((-len(line)) % 4)
            decoded_line = base64.b64decode(padded).decode('utf-8', errors='ignore')
            if re.search(r'(?:vless|trojan|hysteria2|ss)://', decoded_line):
                lines_decoded.append(decoded_line)
        except Exception:
            continue
    if lines_decoded:
        return '\n'.join(lines_decoded)
    return stripped


def _fetch_with_retry(url: str, retries: int = 3, delay: float = 2.0) -> str | None:
    """FIX: загрузка с retry вместо молчаливого пропуска."""
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


def fetch_configs() -> list[str]:
    all_raw: list[str] = []

    for url in SOURCES:
        raw_text = _fetch_with_retry(url)
        if raw_text is None:
            continue
        text  = _decode_subscription(raw_text)
        found = PROTO_REGEX.findall(text)
        all_raw.extend(found)
        fmt   = "plain" if text is raw_text else "base64"
        print(f"  [OK] {url}  →  {len(found)} конфигов  [{fmt}]")

    # FIX: дедупликация по хосту:порту, а не по точной строке
    seen_endpoints: set[str] = set()
    unique: list[str] = []
    for cfg in all_raw:
        host, port = _extract_host_port(cfg)
        if host and port:
            key = f"{host}:{port}"
            if key not in seen_endpoints:
                seen_endpoints.add(key)
                unique.append(cfg)
        else:
            unique.append(cfg)

    return unique


# ============================================================
# ГЕНЕРАЦИЯ HTML-VIEWER ДЛЯ GIST
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


def generate_html_viewer(intl_results: list, ru_results: list, elapsed: int) -> str:
    """Генерирует красивый HTML-файл для просмотра серверов."""

    def make_rows(results):
        rows = []
        for i, (url, score, avg, jitter, losses) in enumerate(results, 1):
            proto    = _get_proto(url)
            security = _get_security(url)
            network  = _get_network(url)
            host, port = _extract_host_port(url)
            tag      = urllib.parse.unquote(url.split('#')[-1])[:35] if '#' in url else ''
            is_ru    = _is_russian_server(host or '')
            flag     = '🇷🇺' if is_ru else '🌍'
            ping_cls = 'ping-good' if avg < 300 else ('ping-mid' if avg < 1000 else 'ping-bad')
            loss_pct = int(losses / PING_ROUNDS * 100)

            safe_url = url.replace('"', '&quot;').replace('<', '&lt;')
            rows.append(f"""
            <tr>
              <td class="num">{i}</td>
              <td>{flag} <span class="tag">{tag or (host or '')[:30]}</span></td>
              <td><span class="badge badge-{proto.lower()}">{proto}</span></td>
              <td><span class="badge badge-net">{network}</span></td>
              <td><span class="badge badge-sec">{security}</span></td>
              <td class="{ping_cls}">{avg}мс</td>
              <td class="jitter">{jitter}мс</td>
              <td class="{'loss-ok' if loss_pct == 0 else 'loss-bad'}">{loss_pct}%</td>
              <td><button class="copy-btn" onclick="copyUrl(this)" data-url="{safe_url}">⎘</button></td>
            </tr>""")
        return '\n'.join(rows)

    intl_rows = make_rows(intl_results)
    ru_rows   = make_rows(ru_results)

    total    = len(intl_results) + len(ru_results)
    updated  = time.strftime('%d.%m.%Y %H:%M UTC', time.gmtime())

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>VPN Servers</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Syne:wght@400;700;800&display=swap" rel="stylesheet">
<style>
:root {{
  --bg:       #0a0c10;
  --surface:  #111318;
  --border:   #1e2230;
  --accent:   #00e5ff;
  --accent2:  #ff6b35;
  --gold:     #ffd166;
  --green:    #06d6a0;
  --red:      #ef476f;
  --muted:    #4a5568;
  --text:     #e2e8f0;
  --subtext:  #718096;
  --radius:   10px;
  --mono:     'JetBrains Mono', monospace;
  --display:  'Syne', sans-serif;
}}

*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
  background: var(--bg);
  color: var(--text);
  font-family: var(--mono);
  font-size: 13px;
  min-height: 100vh;
  overflow-x: hidden;
}}

body::before {{
  content: '';
  position: fixed;
  inset: 0;
  background-image:
    linear-gradient(rgba(0,229,255,.03) 1px, transparent 1px),
    linear-gradient(90deg, rgba(0,229,255,.03) 1px, transparent 1px);
  background-size: 40px 40px;
  pointer-events: none;
  z-index: 0;
}}

.container {{
  position: relative;
  z-index: 1;
  max-width: 1300px;
  margin: 0 auto;
  padding: 40px 20px 80px;
}}

header {{
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 16px;
  margin-bottom: 40px;
  padding-bottom: 24px;
  border-bottom: 1px solid var(--border);
}}

.logo {{
  font-family: var(--display);
  font-weight: 800;
  font-size: 32px;
  letter-spacing: -1px;
  color: #fff;
  line-height: 1;
}}

.logo span {{ color: var(--accent); }}

.meta {{
  text-align: right;
  color: var(--subtext);
  font-size: 11px;
  line-height: 1.7;
}}

.meta strong {{ color: var(--accent); }}

.stats {{
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 12px;
  margin-bottom: 40px;
}}

.stat {{
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  position: relative;
  overflow: hidden;
  transition: border-color .2s;
}}

.stat::before {{
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: var(--accent);
}}

.stat:nth-child(2)::before {{ background: var(--accent2); }}
.stat:nth-child(3)::before {{ background: var(--green); }}
.stat:nth-child(4)::before {{ background: var(--gold); }}

.stat-val {{
  font-family: var(--display);
  font-size: 28px;
  font-weight: 800;
  color: #fff;
  line-height: 1;
  margin-bottom: 4px;
}}

.stat-label {{ color: var(--subtext); font-size: 11px; text-transform: uppercase; letter-spacing: .05em; }}

.tabs {{
  display: flex;
  gap: 4px;
  margin-bottom: 20px;
  background: var(--surface);
  padding: 4px;
  border-radius: var(--radius);
  border: 1px solid var(--border);
  width: fit-content;
}}

.tab {{
  padding: 10px 24px;
  border-radius: 7px;
  border: none;
  background: transparent;
  color: var(--subtext);
  font-family: var(--display);
  font-weight: 700;
  font-size: 13px;
  cursor: pointer;
  transition: all .2s;
  white-space: nowrap;
}}

.tab.active {{
  color: #000;
  background: var(--accent);
}}

.tab.tab-ru.active {{
  color: #fff;
  background: var(--accent2);
}}

.tab:hover:not(.active) {{ color: var(--text); }}

.panel {{ display: none; }}
.panel.active {{ display: block; }}

.search-bar {{
  width: 100%;
  max-width: 400px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  color: var(--text);
  font-family: var(--mono);
  font-size: 13px;
  padding: 10px 16px;
  margin-bottom: 16px;
  outline: none;
  transition: border-color .2s;
}}

.search-bar:focus {{ border-color: var(--accent); }}
.search-bar.ru:focus {{ border-color: var(--accent2); }}

.table-wrap {{
  overflow-x: auto;
  border-radius: var(--radius);
  border: 1px solid var(--border);
}}

table {{
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
}}

thead th {{
  background: #0d1017;
  color: var(--subtext);
  font-size: 10px;
  text-transform: uppercase;
  letter-spacing: .1em;
  padding: 12px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  font-weight: 600;
}}

tbody tr {{
  border-bottom: 1px solid var(--border);
  transition: background .15s;
}}

tbody tr:last-child {{ border-bottom: none; }}
tbody tr:hover {{ background: rgba(0,229,255,.03); }}

td {{
  padding: 11px 14px;
  vertical-align: middle;
  white-space: nowrap;
}}

.num {{ color: var(--muted); width: 40px; }}

.tag {{
  color: var(--text);
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
  vertical-align: middle;
}}

.badge {{
  display: inline-block;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: .04em;
  text-transform: uppercase;
}}

.badge-vless   {{ background: rgba(0,229,255,.12); color: var(--accent); border: 1px solid rgba(0,229,255,.2); }}
.badge-trojan  {{ background: rgba(255,107,53,.12); color: var(--accent2); border: 1px solid rgba(255,107,53,.2); }}
.badge-hysteria2 {{ background: rgba(255,209,102,.12); color: var(--gold); border: 1px solid rgba(255,209,102,.2); }}
.badge-ss      {{ background: rgba(6,214,160,.12); color: var(--green); border: 1px solid rgba(6,214,160,.2); }}
.badge-net     {{ background: rgba(255,255,255,.05); color: var(--subtext); border: 1px solid var(--border); }}
.badge-sec     {{ background: rgba(255,255,255,.05); color: var(--subtext); border: 1px solid var(--border); }}

.ping-good {{ color: var(--green); font-weight: 600; }}
.ping-mid  {{ color: var(--gold); font-weight: 600; }}
.ping-bad  {{ color: var(--red); font-weight: 600; }}
.jitter    {{ color: var(--subtext); }}
.loss-ok   {{ color: var(--green); }}
.loss-bad  {{ color: var(--red); font-weight: 600; }}

.copy-btn {{
  background: rgba(0,229,255,.08);
  border: 1px solid rgba(0,229,255,.15);
  color: var(--accent);
  border-radius: 5px;
  padding: 4px 9px;
  cursor: pointer;
  font-size: 14px;
  transition: all .15s;
}}

.copy-btn:hover {{ background: rgba(0,229,255,.18); }}
.copy-btn.copied {{ color: var(--green); border-color: var(--green); }}

#toast {{
  position: fixed;
  bottom: 30px;
  right: 30px;
  background: var(--green);
  color: #000;
  font-family: var(--display);
  font-weight: 700;
  font-size: 13px;
  padding: 10px 20px;
  border-radius: 8px;
  opacity: 0;
  transform: translateY(10px);
  transition: all .25s;
  pointer-events: none;
  z-index: 999;
}}

#toast.show {{
  opacity: 1;
  transform: translateY(0);
}}

footer {{
  margin-top: 60px;
  padding-top: 24px;
  border-top: 1px solid var(--border);
  color: var(--muted);
  font-size: 11px;
  text-align: center;
}}
</style>
</head>
<body>
<div class="container">

  <header>
    <div class="logo">VPN<span>.</span>Scout</div>
    <div class="meta">
      Обновлено: <strong>{updated}</strong><br>
      Время проверки: <strong>{elapsed}с</strong>
    </div>
  </header>

  <div class="stats">
    <div class="stat">
      <div class="stat-val">{len(intl_results)}</div>
      <div class="stat-label">🌍 Зарубежных</div>
    </div>
    <div class="stat">
      <div class="stat-val">{len(ru_results)}</div>
      <div class="stat-label">🇷🇺 Российских</div>
    </div>
    <div class="stat">
      <div class="stat-val">{total}</div>
      <div class="stat-label">Всего живых</div>
    </div>
    <div class="stat">
      <div class="stat-val">{min((r[2] for r in intl_results), default=0)}мс</div>
      <div class="stat-label">Лучший пинг</div>
    </div>
  </div>

  <div class="tabs">
    <button class="tab active" onclick="switchTab('intl', this)">🌍 Зарубежные ({len(intl_results)})</button>
    <button class="tab tab-ru" onclick="switchTab('ru', this)">🇷🇺 Российские ({len(ru_results)})</button>
  </div>

  <!-- ЗАРУБЕЖНЫЕ -->
  <div class="panel active" id="panel-intl">
    <input class="search-bar" type="text" placeholder="Поиск по адресу, протоколу, тегу..." oninput="filterTable(this, 'tbl-intl')">
    <div class="table-wrap">
      <table id="tbl-intl">
        <thead>
          <tr>
            <th>#</th><th>Сервер</th><th>Протокол</th><th>Транспорт</th>
            <th>Безопасность</th><th>Пинг</th><th>Jitter</th><th>Loss</th><th></th>
          </tr>
        </thead>
        <tbody>
          {intl_rows if intl_rows else '<tr><td colspan="9" style="text-align:center;color:var(--subtext);padding:40px">Нет зарубежных серверов</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>

  <!-- РОССИЙСКИЕ -->
  <div class="panel" id="panel-ru">
    <input class="search-bar ru" type="text" placeholder="Поиск по адресу, протоколу, тегу..." oninput="filterTable(this, 'tbl-ru')">
    <div class="table-wrap">
      <table id="tbl-ru">
        <thead>
          <tr>
            <th>#</th><th>Сервер</th><th>Протокол</th><th>Транспорт</th>
            <th>Безопасность</th><th>Пинг</th><th>Jitter</th><th>Loss</th><th></th>
          </tr>
        </thead>
        <tbody>
          {ru_rows if ru_rows else '<tr><td colspan="9" style="text-align:center;color:var(--subtext);padding:40px">Нет российских серверов</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>

</div>

<div id="toast">✓ Скопировано!</div>

<footer>
  VPN.Scout — автоматическая проверка серверов каждый час
</footer>

<script>
function switchTab(name, btn) {{
  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  btn.classList.add('active');
  document.getElementById('panel-' + name).classList.add('active');
}}

function filterTable(input, tableId) {{
  const q = input.value.toLowerCase();
  document.querySelectorAll('#' + tableId + ' tbody tr').forEach(row => {{
    row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
  }});
}}

function copyUrl(btn) {{
  navigator.clipboard.writeText(btn.dataset.url).then(() => {{
    btn.classList.add('copied');
    btn.textContent = '✓';
    setTimeout(() => {{ btn.classList.remove('copied'); btn.textContent = '⎘'; }}, 1500);
    const toast = document.getElementById('toast');
    toast.classList.add('show');
    setTimeout(() => toast.classList.remove('show'), 2000);
  }});
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
    print("=" * 60)

    # --- Сбор ---
    print("\n[1/4] Сбор конфигов...")
    all_configs = fetch_configs()
    print(f"      Итого уникальных (по хосту:порту): {len(all_configs)}")

    if not all_configs:
        print("Нет кандидатов.")
        return

    # --- Этап 1: TCP ---
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
        print("❌ Нет рабочих серверов. Старый файл сохранён.")
        return

    results.sort(key=lambda x: x[1])
    top = results[:TOP_N]

    # Разделяем по гео
    intl_results = []
    ru_results   = []
    for entry in top:
        url = entry[0]
        host, _ = _extract_host_port(url)
        if _is_russian_server(host or ''):
            ru_results.append(entry)
        else:
            intl_results.append(entry)

    # Зарубежные сначала
    ordered = intl_results + ru_results

    print(f"\n{'─'*60}")
    print(f"  Всего: {len(all_configs)} → TCP: {len(alive)} → xray: {len(results)} → топ: {len(top)}")
    print(f"  🌍 Зарубежных: {len(intl_results)}  |  🇷🇺 Российских: {len(ru_results)}")
    print(f"  Время: {elapsed_total}с")
    print(f"{'─'*60}")

    print("\n  Топ-10 зарубежных:")
    for i, (url, score, avg, jitter, losses) in enumerate(intl_results[:10], 1):
        name = urllib.parse.unquote(url.split('#')[-1])[:40] if '#' in url else url[8:48]
        print(f"  {i:<3} {avg:>5}мс  jitter:{jitter:>4}мс  loss:{losses}/{PING_ROUNDS}  {name}")

    # Записываем plain-текст (зарубежные первыми)
    final_urls = [r[0] for r in ordered]
    with open(FILE_NAME, "w", encoding="utf-8") as f:
        f.write("\n".join(final_urls))
    print(f"\n✅ Сохранено {len(final_urls)} серверов в {FILE_NAME}")

    # Генерируем HTML-viewer
    html = generate_html_viewer(intl_results, ru_results, elapsed_total)
    with open(VIEWER_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ HTML-viewer сохранён в {VIEWER_FILE}")

    # ============================================================
    # FIX: Обновляем Gist через GitHub REST API (PATCH /gists/{id})
    # вместо сломанной команды gh gist edit с несколькими файлами
    # ============================================================
    if GID:
        print("Обновляем Gist (два файла: vps.txt + index.html)...")

        # Читаем содержимое файлов
        with open(FILE_NAME, "r", encoding="utf-8") as f:
            vps_content = f.read()
        with open(VIEWER_FILE, "r", encoding="utf-8") as f:
            html_content = f.read()

        # Получаем токен через gh CLI
        token_res = subprocess.run(
            ["gh", "auth", "token"],
            capture_output=True, text=True
        )
        token = token_res.stdout.strip()

        if token:
            import urllib.request as url_req

            payload = json.dumps({
                "files": {
                    FILE_NAME:   {"content": vps_content},
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
                        print("✅ Gist обновлён.")
                    else:
                        print(f"❌ Gist ошибка: статус {resp.status}")
            except Exception as e:
                print(f"❌ Gist ошибка: {e}")
        else:
            print("❌ Не удалось получить токен через gh auth token")
    else:
        print("⚠️  MY_GIST_ID не задан.")


if __name__ == "__main__":
    run()
