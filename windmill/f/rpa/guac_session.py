"""Sessão de desktop por execução: sobe um container, registra a conexão no Guacamole
e garante a limpeza de ambos ao final (mesmo em caso de erro)."""
import base64
import json
import os
import secrets
import time
import urllib.parse
import urllib.request
from contextlib import contextmanager
from dataclasses import dataclass

import docker


def _env(name, default=None):
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Variável de ambiente {name} não definida no worker")
    return value


class Guacamole:
    def __init__(self):
        self.base = _env("GUAC_URL")
        self.public = _env("GUAC_PUBLIC_URL", self.base)
        self.ds = "postgresql"
        self.token = None

    def _call(self, path, data=None, form=False, method=None, auth=True):
        url = f"{self.base}/api/{path}"
        if auth:
            url += f"?token={self.token}"
        headers, body = {}, None
        if form:
            body = urllib.parse.urlencode(data).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif data is not None:
            body = json.dumps(data).encode()
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            return json.loads(raw) if raw else None

    def login(self):
        self.token = self._call(
            "tokens", {"username": _env("GUAC_USER"), "password": _env("GUAC_PASS")}, form=True, auth=False
        )["authToken"]

    def create_connection(self, name, hostname, password):
        conn = self._call(f"session/data/{self.ds}/connections", {
            "parentIdentifier": "ROOT",
            "name": name,
            "protocol": "vnc",
            "parameters": {"hostname": hostname, "port": "5901", "password": password},
            "attributes": {},
        })
        return conn["identifier"]

    def client_url(self, conn_id):
        raw = f"{conn_id}\0c\0{self.ds}".encode()
        return f"{self.public}/#/client/{base64.b64encode(raw).decode().rstrip('=')}"

    def delete_connection(self, conn_id):
        active = self._call(f"session/data/{self.ds}/activeConnections") or {}
        ops = [{"op": "remove", "path": f"/{aid}"} for aid, a in active.items()
               if a.get("connectionIdentifier") == conn_id]
        if ops:
            self._call(f"session/data/{self.ds}/activeConnections", ops, method="PATCH")
        self._call(f"session/data/{self.ds}/connections/{conn_id}", method="DELETE")

    def logout(self):
        if self.token:
            self._call(f"tokens/{self.token}", method="DELETE")


@dataclass
class Desktop:
    cdp_url: str
    viewer_url: str


def _wait_cdp(cdp_url, timeout_s):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{cdp_url}/json/version", timeout=3).close()
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError(f"CDP do desktop indisponível em {cdp_url}")


@contextmanager
def desktop_session(run_name, startup_timeout_s=120):
    """Cria um desktop descartável + conexão Guacamole. Remove tudo ao sair do bloco."""
    suffix = secrets.token_hex(4)
    container_name = f"rpa-desktop-{suffix}"
    vnc_password = secrets.token_urlsafe(8)

    client = docker.from_env()
    guac = Guacamole()
    container = None
    conn_id = None
    try:
        container = client.containers.run(
            _env("DESKTOP_IMAGE", "rpa-desktop:latest"),
            name=container_name,
            detach=True,
            network=_env("DESKTOP_NETWORK", "rpa-net"),
            shm_size="2g",
            environment={"VNC_PASSWORD": vnc_password},
            labels={"rpa.desktop": "true", "rpa.run": run_name},
        )
        # o Chromium só aceita CDP quando o Host é um IP ou localhost, então usamos o IP do container
        container.reload()
        ip = container.attrs["NetworkSettings"]["Networks"][_env("DESKTOP_NETWORK", "rpa-net")]["IPAddress"]
        cdp_url = f"http://{ip}:9223"
        _wait_cdp(cdp_url, startup_timeout_s)

        guac.login()
        conn_id = guac.create_connection(f"{run_name}-{suffix}", container_name, vnc_password)
        yield Desktop(cdp_url=cdp_url, viewer_url=guac.client_url(conn_id))
    finally:
        for step in (
            lambda: conn_id and guac.delete_connection(conn_id),
            guac.logout,
            lambda: container and container.remove(force=True),
        ):
            try:
                step()
            except Exception as e:
                print(f"[cleanup] falha ao limpar: {e}")
        print("Desktop e conexão do Guacamole removidos.")
