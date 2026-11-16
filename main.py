import atexit
import ctypes
import os
import random
import shutil
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
import winreg

RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[92m"
CYAN = "\033[96m"
DIM = "\033[2m"
RED = "\033[91m"

APPLE_OUIS = ["001CB3", "0025BC", "3C0754", "A45E60", "F0DCE2", "D89695"]
IOS_PARAM_LIST = [1, 3, 6, 15, 119, 252, 95, 44, 46, 101]
IOS_USER_AGENT = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1"

TCPIP_PATH = r"SYSTEM\CurrentControlSet\Services\Tcpip\Parameters"
COMPNAME_PATH = r"SYSTEM\CurrentControlSet\Control\ComputerName\ActiveComputerName"
INTERNET_SETTINGS = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

LETTERS = {
    "T": ["#######", "   #   ", "   #   ", "   #   ", "   #   ", "   #   "],
    "O": [" ##### ", "##   ##", "##   ##", "##   ##", "##   ##", " ##### "],
    "L": ["##     ", "##     ", "##     ", "##     ", "##     ", "#######"],
    "G": [" ##### ", "##     ", "##  ###", "##   ##", "##   ##", " ##### "],
    "A": [" ##### ", "##   ##", "##   ##", "#######", "##   ##", "##   ##"],
}

_cleanup_done = False
_layer1_backup = {}
_adapter_name = None
_adapter_reg_path = None
_proxy_server = None
_proxy_backup = {}


def enable_ansi():
    os.system("")


def build_word(word):
    rows = ["" for _ in range(6)]
    for ch in word:
        glyph = LETTERS[ch]
        for i in range(6):
            rows[i] += glyph[i] + "  "
    return rows


def matrix_rain(duration=1.0):
    cols = shutil.get_terminal_size().columns
    end = time.time() + duration
    while time.time() < end:
        line = "".join(random.choice("01") if random.random() > 0.4 else " " for _ in range(cols))
        print(GREEN + DIM + line + RESET)
        time.sleep(0.03)
    os.system("cls")


def print_banner():
    for row in build_word("TOLGA"):
        print(GREEN + BOLD + row + RESET)
        time.sleep(0.05)
    print()
    subtitle = "NETWORK IDENTITY MASKING TOOL"
    line = ""
    for ch in subtitle:
        line += ch
        print("\r" + CYAN + line + RESET, end="", flush=True)
        time.sleep(0.015)
    print("\n")


def spin(label, func, *args, **kwargs):
    result = {}
    error = {}

    def target():
        try:
            result["value"] = func(*args, **kwargs)
        except Exception as e:
            error["value"] = e

    t = threading.Thread(target=target)
    t.start()
    frames = "|/-\\"
    i = 0
    while t.is_alive():
        print("\r" + GREEN + "[" + frames[i % len(frames)] + "] " + label + RESET + "    ", end="", flush=True)
        time.sleep(0.08)
        i += 1
    t.join()
    print("\r" + GREEN + "[+] " + label + RESET + " " * 15)
    if "value" in error:
        raise error["value"]
    return result.get("value")


def is_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def relaunch_as_admin():
    params = " ".join(f'"{a}"' for a in sys.argv)
    ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{os.path.abspath(__file__)}" {params}', None, 1)


def run_cmd(cmd):
    subprocess.run(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def generate_apple_mac():
    oui = random.choice(APPLE_OUIS)
    nic = "".join(random.choices("0123456789ABCDEF", k=6))
    return oui + nic


def get_adapter_reg_path(adapter_name):
    cmd = f'powershell -Command "(Get-NetAdapter -Name \'{adapter_name}\').InterfaceGuid"'
    guid = subprocess.check_output(cmd, shell=True).decode().strip()
    if not guid:
        raise ValueError(f"'{adapter_name}' adinda bir adaptor bulunamadi")
    base_path = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e972-e325-11ce-bfc1-08002be10318}"
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base_path) as key:
        for i in range(200):
            subkey_name = f"{i:04d}"
            try:
                with winreg.OpenKey(key, subkey_name) as subkey:
                    val, _ = winreg.QueryValueEx(subkey, "NetCfgInstanceId")
                    if val.lower() == guid.lower():
                        return f"{base_path}\\{subkey_name}"
            except FileNotFoundError:
                continue
    raise ValueError("Adaptor kayit defterinde bulunamadi")


def get_reg_value(path, name, root=winreg.HKEY_LOCAL_MACHINE):
    try:
        with winreg.OpenKey(root, path, 0, winreg.KEY_READ) as key:
            val, _ = winreg.QueryValueEx(key, name)
            return val
    except FileNotFoundError:
        return None


def set_reg_value(path, name, value, value_type=winreg.REG_SZ, root=winreg.HKEY_LOCAL_MACHINE):
    with winreg.OpenKey(root, path, 0, winreg.KEY_WRITE) as key:
        if value is None:
            try:
                winreg.DeleteValue(key, name)
            except FileNotFoundError:
                pass
        else:
            winreg.SetValueEx(key, name, 0, value_type, value)


def restart_adapter(adapter_name):
    run_cmd(f'netsh interface set interface "{adapter_name}" admin=disable')
    time.sleep(2)
    run_cmd(f'netsh interface set interface "{adapter_name}" admin=enable')
    time.sleep(3)


def apply_layer1(adapter_name, adapter_reg_path, new_mac, hostname):
    set_reg_value(adapter_reg_path, "NetworkAddress", new_mac)
    set_reg_value(TCPIP_PATH, "Hostname", hostname)
    set_reg_value(TCPIP_PATH, "NV Hostname", hostname)
    set_reg_value(COMPNAME_PATH, "ComputerName", hostname)
    run_cmd("netsh int ipv4 set glob defaultcurhoplimit=64")
    restart_adapter(adapter_name)


def revert_layer1():
    if not _layer1_backup:
        return
    set_reg_value(_adapter_reg_path, "NetworkAddress", _layer1_backup.get("mac"))
    set_reg_value(TCPIP_PATH, "Hostname", _layer1_backup.get("hostname"))
    set_reg_value(TCPIP_PATH, "NV Hostname", _layer1_backup.get("nv_hostname"))
    set_reg_value(COMPNAME_PATH, "ComputerName", _layer1_backup.get("compname"))
    run_cmd("netsh int ipv4 set glob defaultcurhoplimit=128")
    restart_adapter(_adapter_name)


def build_dhcp_discover(mac_bytes, xid, hostname):
    header = struct.pack(
        "!BBBBIHH4s4s4s4s16s64s128s4s",
        1, 1, 6, 0, xid, 0, 0x8000,
        b"\x00\x00\x00\x00", b"\x00\x00\x00\x00", b"\x00\x00\x00\x00", b"\x00\x00\x00\x00",
        mac_bytes.ljust(16, b"\x00"), b"\x00" * 64, b"\x00" * 128, b"\x63\x82\x53\x63",
    )
    options = bytes([53, 1, 1])
    options += bytes([61, 7, 1]) + mac_bytes
    hb = hostname.encode()
    options += bytes([12, len(hb)]) + hb
    options += bytes([55, len(IOS_PARAM_LIST)]) + bytes(IOS_PARAM_LIST)
    options += bytes([255])
    return header + options


def attempt_dhcp_spoof(mac_str, hostname, timeout=4):
    mac_bytes = bytes.fromhex(mac_str.replace(":", "").replace("-", ""))
    xid = random.randint(0, 0xFFFFFFFF)
    packet = build_dhcp_discover(mac_bytes, xid, hostname)
    run_cmd("sc stop Dhcp")
    time.sleep(1)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    success = False
    try:
        sock.bind(("0.0.0.0", 68))
        sock.sendto(packet, ("255.255.255.255", 67))
        sock.settimeout(timeout)
        data, _ = sock.recvfrom(1024)
        if len(data) > 242 and data[242] == 2:
            success = True
    except Exception:
        success = False
    finally:
        sock.close()
        run_cmd("sc start Dhcp")
    return success


def relay(a, b):
    def pipe(src, dst):
        try:
            while True:
                data = src.recv(65536)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                dst.shutdown(socket.SHUT_WR)
            except Exception:
                pass

    t1 = threading.Thread(target=pipe, args=(a, b), daemon=True)
    t2 = threading.Thread(target=pipe, args=(b, a), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()


def handle_proxy_client(conn):
    try:
        request = conn.recv(65536)
        if not request:
            conn.close()
            return
        method, target, _ = request.split(b"\r\n", 1)[0].split(b" ", 2)
        if method == b"CONNECT":
            host, port = target.split(b":")
            remote = socket.create_connection((host.decode(), int(port)))
            conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
            relay(conn, remote)
        else:
            headers, _, body = request.partition(b"\r\n\r\n")
            host = None
            new_lines = []
            for line in headers.split(b"\r\n"):
                if line.lower().startswith(b"host:"):
                    host = line.split(b":", 1)[1].strip()
                if line.lower().startswith(b"user-agent:"):
                    continue
                new_lines.append(line)
            new_lines.append(b"User-Agent: " + IOS_USER_AGENT.encode())
            new_request = b"\r\n".join(new_lines) + b"\r\n\r\n" + body
            port = 80
            if b":" in host:
                h, p = host.split(b":")
                host, port = h, int(p)
            remote = socket.create_connection((host.decode(), port))
            remote.sendall(new_request)
            relay(conn, remote)
    except Exception:
        pass
    finally:
        conn.close()


def start_proxy(port=8899):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(100)

    def loop():
        while True:
            try:
                conn, _ = srv.accept()
            except Exception:
                break
            threading.Thread(target=handle_proxy_client, args=(conn,), daemon=True).start()

    threading.Thread(target=loop, daemon=True).start()
    return srv


def notify_proxy_change():
    ctypes.windll.wininet.InternetSetOptionW(0, 39, 0, 0)
    ctypes.windll.wininet.InternetSetOptionW(0, 37, 0, 0)


def set_system_proxy(enable, server=None):
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, INTERNET_SETTINGS, 0, winreg.KEY_WRITE) as key:
        winreg.SetValueEx(key, "ProxyEnable", 0, winreg.REG_DWORD, 1 if enable else 0)
        if server is not None:
            winreg.SetValueEx(key, "ProxyServer", 0, winreg.REG_SZ, server)
    notify_proxy_change()


def apply_layer3(port=8899):
    global _proxy_server, _proxy_backup
    _proxy_backup = {
        "enable": get_reg_value(INTERNET_SETTINGS, "ProxyEnable", winreg.HKEY_CURRENT_USER) or 0,
        "server": get_reg_value(INTERNET_SETTINGS, "ProxyServer", winreg.HKEY_CURRENT_USER),
    }
    _proxy_server = start_proxy(port)
    set_system_proxy(True, f"127.0.0.1:{port}")


def revert_layer3():
    global _proxy_server
    if _proxy_server is not None:
        try:
            _proxy_server.close()
        except Exception:
            pass
        _proxy_server = None
    if _proxy_backup:
        set_system_proxy(bool(_proxy_backup.get("enable")), _proxy_backup.get("server"))


def cleanup():
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True
    print("\n" + GREEN + "[*] Orijinal ayarlar geri yukleniyor..." + RESET)
    try:
        spin("Proxy ve sistem ayarlari kaldiriliyor", revert_layer3)
    except Exception as e:
        print(RED + f"[!] Proxy geri alma hatasi: {e}" + RESET)
    try:
        spin("MAC, hostname ve TTL eski haline donduruluyor", revert_layer1)
    except Exception as e:
        print(RED + f"[!] Katman 1 geri alma hatasi: {e}" + RESET)
    print(GREEN + "[+] Sistem orijinal haline donduruldu." + RESET)


def handle_signal(signum, frame):
    cleanup()
    sys.exit(0)


def main():
    global _adapter_name, _adapter_reg_path, _layer1_backup

    if not is_admin():
        relaunch_as_admin()
        return

    enable_ansi()
    os.system("title TOLGA - NETMASK")
    matrix_rain()
    print_banner()

    adapter_name = input(GREEN + "Maskelenecek adaptorun tam adi (orn: Wi-Fi): " + RESET).strip()
    extra = input(GREEN + "DHCP fingerprint (Option 55) + HTTP User-Agent proxy da aktif edilsin mi? (e/h): " + RESET).strip().lower()

    adapter_reg_path = spin(f"'{adapter_name}' adaptoru bulunuyor", get_adapter_reg_path, adapter_name)
    _adapter_name = adapter_name
    _adapter_reg_path = adapter_reg_path

    _layer1_backup = {
        "mac": get_reg_value(adapter_reg_path, "NetworkAddress"),
        "hostname": get_reg_value(TCPIP_PATH, "Hostname"),
        "nv_hostname": get_reg_value(TCPIP_PATH, "NV Hostname"),
        "compname": get_reg_value(COMPNAME_PATH, "ComputerName"),
    }

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, handle_signal)
    atexit.register(cleanup)

    new_mac = generate_apple_mac()
    hostname = "iPhone"

    print()
    spin("Katman 1: MAC, hostname ve TTL uygulaniyor", apply_layer1, adapter_name, adapter_reg_path, new_mac, hostname)

    dhcp_ok = False
    if extra == "e":
        dhcp_ok = spin("Katman 2: DHCP fingerprint (Option 55) deneniyor", attempt_dhcp_spoof, new_mac, hostname)
        spin("Katman 3: HTTP User-Agent proxy baslatiliyor", apply_layer3)

    formatted_mac = ":".join(new_mac[i:i + 2] for i in range(0, 12, 2))
    print()
    print(GREEN + BOLD + "[AKTIF] Cihaz agda bir iPhone gibi gorunuyor" + RESET)
    print(CYAN + f" -> MAC adresi : {formatted_mac} (Apple Inc. OUI)" + RESET)
    print(CYAN + f" -> Hostname   : {hostname}" + RESET)
    print(CYAN + " -> TTL imzasi : 64 (iOS standardi)" + RESET)
    if extra == "e":
        status = "basarili" if dhcp_ok else "basarisiz, normal DHCP ile devam ediliyor"
        print(CYAN + f" -> DHCP Option 55 : {status}" + RESET)
        print(CYAN + " -> HTTP proxy : 127.0.0.1:8899 (sadece duz HTTP)" + RESET)
    print()
    print(DIM + "Bitirmek icin CTRL+C" + RESET)

    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        mins, secs = divmod(elapsed, 60)
        print(f"\r{GREEN}[AKTIF] Sure: {mins:02d}:{secs:02d}{RESET}", end="", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(RED + f"[!] Hata: {e}" + RESET)
        input("Kapatmak icin Enter...")
    finally:
        cleanup()
