"""Dispara um robô no Windmill, abre o Guacamole no navegador assim que o desktop estiver pronto
e acompanha o job até o fim.

Uso: python windmill/launch.py f/rpa/coletar_cursos [--args '{"assisted": true}']
"""
import argparse
import json
import re
import time
import urllib.request
import webbrowser

WORKSPACE = "rpa"
URL_RE = re.compile(r"Acompanhe o robô em:\s*(\S+)")


def call(base, path, token=None, data=None, raw=False):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    with urllib.request.urlopen(urllib.request.Request(f"{base}/api/{path}", data=body, headers=headers), timeout=30) as r:
        text = r.read().decode()
    return text.strip('"') if raw else json.loads(text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--args", default="{}", help="JSON com os parâmetros do robô")
    ap.add_argument("--url", default="http://localhost:8000")
    ap.add_argument("--email", default="admin@windmill.dev")
    ap.add_argument("--password", default="changeme")
    a = ap.parse_args()

    token = call(a.url, "auth/login", data={"email": a.email, "password": a.password}, raw=True)
    job_id = call(a.url, f"w/{WORKSPACE}/jobs/run/p/{a.script}", token, json.loads(a.args), raw=True)
    print(f"Job {job_id} iniciado: {a.url}/run/{job_id}?workspace={WORKSPACE}")

    opened, offset = False, 0
    while True:
        upd = call(a.url, f"w/{WORKSPACE}/jobs_u/getupdate/{job_id}?running=true&log_offset={offset}", token)
        new_logs = upd.get("new_logs") or ""
        if new_logs:
            print(new_logs, end="" if new_logs.endswith("\n") else "\n")
            offset = upd.get("log_offset", offset + len(new_logs))
            m = URL_RE.search(new_logs)
            if m and not opened:
                webbrowser.open(m.group(1))
                opened = True
        if upd.get("completed"):
            break
        time.sleep(2)

    job = call(a.url, f"w/{WORKSPACE}/jobs_u/get/{job_id}", token)
    print("Finalizado com", "sucesso" if job.get("success") else "FALHA")
    raise SystemExit(0 if job.get("success") else 1)


if __name__ == "__main__":
    main()
