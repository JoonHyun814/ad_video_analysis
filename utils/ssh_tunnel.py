"""SSH 터널 컨텍스트 매니저 — OpenSSH subprocess 래퍼."""
from __future__ import annotations

import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

from utils.env_loader import load_env

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_SSH_ENV = _PROJECT_ROOT / "env" / "ssh.env"


def _ssh_cfg() -> dict:
    e = load_env(_SSH_ENV)
    return {
        "host": e["SSH_HOST"],
        "port": int(e.get("SSH_PORT", 22)),
        "user": e["SSH_USER"],
        "password": e["SSH_PASSWORD"],
        "local_port": int(e.get("SSH_TUNNEL_LOCAL_PORT", 3307)),
    }


@contextmanager
def mysql_tunnel() -> Generator[int, None, None]:
    """원격 MySQL 3306 → localhost:<local_port> 터널을 열고 local_port 를 yield 한다.

    plink(PuTTY) 또는 OpenSSH 중 사용 가능한 것을 자동 선택한다.
    """
    cfg = _ssh_cfg()
    local_port = cfg["local_port"]

    # plink 우선, 없으면 sshpass+ssh 시도
    import shutil
    plink = shutil.which("plink")
    if plink:
        cmd = [
            plink, "-ssh",
            f"{cfg['user']}@{cfg['host']}", "-P", str(cfg["port"]),
            "-pw", cfg["password"],
            "-N",
            "-L", f"127.0.0.1:{local_port}:127.0.0.1:3306",
            "-batch",
        ]
    else:
        # OpenSSH: StrictHostKeyChecking=no, BatchMode 불가(암호 입력 필요)
        # sshpass 가 있으면 사용, 없으면 paramiko 직접 사용
        sshpass = shutil.which("sshpass")
        ssh = shutil.which("ssh")
        if sshpass and ssh:
            cmd = [
                sshpass, "-p", cfg["password"],
                ssh, "-o", "StrictHostKeyChecking=no",
                "-N", "-L", f"127.0.0.1:{local_port}:127.0.0.1:3306",
                f"{cfg['user']}@{cfg['host']}", "-p", str(cfg["port"]),
            ]
        else:
            # paramiko 직접 포워딩
            yield from _paramiko_tunnel(cfg)
            return

    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(2)  # 터널 연결 대기
    try:
        yield local_port
    finally:
        proc.terminate()
        proc.wait(timeout=5)


def _paramiko_tunnel(cfg: dict):
    """paramiko 로 로컬 포트 → 원격 MySQL 포워딩 (local-forward)."""
    import socket
    import threading
    import paramiko

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        cfg["host"], port=cfg["port"],
        username=cfg["user"], password=cfg["password"],
        look_for_keys=False, allow_agent=False,
        timeout=10,
    )

    local_port = cfg["local_port"]
    _stop = threading.Event()
    transport = client.get_transport()

    def _copy(src, dst):
        try:
            while True:
                data = src.recv(4096)
                if not data:
                    break
                dst.sendall(data)
        except Exception:
            pass
        finally:
            try:
                dst.close()
            except Exception:
                pass

    def _forward(local_sock: socket.socket):
        """로컬 소켓 ↔ 원격 MySQL direct-tcpip 채널."""
        try:
            chan = transport.open_channel(
                "direct-tcpip",
                ("127.0.0.1", 3306),
                local_sock.getpeername(),
            )
        except Exception as e:
            local_sock.close()
            return
        # 양방향 복사: 각 방향을 별도 스레드에서 실행
        t1 = threading.Thread(target=_copy, args=(local_sock, chan), daemon=True)
        t2 = threading.Thread(target=_copy, args=(chan, local_sock), daemon=True)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", local_port))
    srv.listen(20)
    srv.settimeout(0.5)

    def _accept():
        while not _stop.is_set():
            try:
                sock, _ = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=_forward, args=(sock,), daemon=True).start()

    threading.Thread(target=_accept, daemon=True).start()

    try:
        yield local_port
    finally:
        _stop.set()
        srv.close()
        client.close()
