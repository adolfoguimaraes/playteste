"""Publica os scripts de windmill/f/ no Windmill via API REST (workspace 'rpa').

Uso: python windmill/deploy.py [--url http://localhost:8000] [--email ...] [--password ...]
"""
import argparse
import json
import pathlib
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).parent
WORKSPACE = "rpa"

# path -> (resumo, schema dos parâmetros)
SCRIPTS = {
    "f/rpa/guac_session": ("Módulo compartilhado: desktop + Guacamole por execução", None),
    "f/rpa/coletar_cursos": (
        "Coletar cursos e colar      planilha",
        {
            "properties": {
                "sheet_url": {"type": "string", "default": "https://docs.google.com/spreadsheets/d/1zLrWjVJrCdkjZEtlIj9pHrLiFktvWtGjqJr3P1DuGmw/edit?usp=sharing"},
                "assisted": {"type": "boolean", "default": True, "description": "Espera o usuário clicar em Cursos e fechar a planilha"},
                "max_wait_s": {"type": "integer", "default": 1800},
            },
            "required": [],
        },
    ),
    "f/rpa/coleta_candidatos": (
        "Coletar candidatos a Governador e Senador de Sergipe (TSE)",
        {
            "properties": {
                "sheet_url": {"type": "string", "default": "", "description": "Planilha editável: Governador na 1ª aba e Senador na 2ª; vazio = não grava"},
                "assisted": {"type": "boolean", "default": True, "description": "Com planilha, espera a aba ser fechada para encerrar"},
                "max_wait_s": {"type": "integer", "default": 1800},
            },
            "required": [],
        },
    ),
}


def call(base, path, data=None, token=None, raw=False):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(f"{base}/api/{path}", data=body, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            text = r.read().decode()
    except urllib.error.HTTPError as e:
        raise SystemExit(f"{path}: HTTP {e.code} {e.read().decode()}")
    return text if raw else (json.loads(text) if text else None)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--email", default="admin@windmill.dev")
    ap.add_argument("--password", default="changeme")
    a = ap.parse_args()

    token = call(a.url, "auth/login", {"email": a.email, "password": a.password}, raw=True).strip('"')

    if WORKSPACE not in [w["id"] for w in call(a.url, "workspaces/list", token=token)]:
        call(a.url, "workspaces/create", {"id": WORKSPACE, "name": "RPA"}, token, raw=True)
        print(f"Workspace '{WORKSPACE}' criado")

    for path, (summary, schema) in SCRIPTS.items():
        content = (ROOT / f"{path}.py").read_text(encoding="utf-8")
        payload = {
            "path": path,
            "summary": summary,
            "description": "",
            "content": content,
            "language": "python3",
            "schema": {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object", **(schema or {"properties": {}, "required": []})},
        }
        parent = None
        try:
            parent = call(a.url, f"w/{WORKSPACE}/scripts/get/p/{path}", token=token)["hash"]
        except SystemExit:
            pass
        if parent:
            payload["parent_hash"] = parent
        call(a.url, f"w/{WORKSPACE}/scripts/create", payload, token, raw=True)
        print(f"Publicado {path}")

    env_file = ROOT.parent / ".env"
    if "WM_TOKEN=" not in (env_file.read_text() if env_file.exists() else ""):
        tok = call(a.url, "users/tokens/create", {"label": "portal"}, token, raw=True).strip('"')
        with env_file.open("a") as f:
            f.write(f"WM_TOKEN={tok}\n")
        print("Token do portal gravado em .env. Rode: docker compose -f docker-compose.guacamole.yml up -d portal")


if __name__ == "__main__":
    main()
