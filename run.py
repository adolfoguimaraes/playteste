from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from playwright.async_api import async_playwright
import argparse
import asyncio
import base64
import json
import time
import urllib.parse
import urllib.request

parser = argparse.ArgumentParser()
parser.add_argument("--os", choices=["guacamole", "linux", "windows"], default="guacamole", help="Máquina onde o navegador roda")
args = parser.parse_args()

GUAC_URL = "http://localhost:8080/guacamole"
GUAC_USER = "guacadmin"
GUAC_PASS = "guacadmin"
GUAC_CONN_NAME = "Desktop Linux"


guac_state = {}


def guac_request(path, token=None, data=None, form=False, method=None):
    url = f"{GUAC_URL}/api/{path}" + (f"?token={token}" if token else "")
    headers = {}
    if data is not None and form:
        body = urllib.parse.urlencode(data).encode()
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif data is not None:
        body = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    else:
        body = None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read() or b"null")


def guac_viewer_url():
    """Garante a conexão VNC para o container 'desktop' no Guacamole e devolve o link direto."""
    token = None
    for _ in range(60):  # aguarda o Guacamole subir
        try:
            token = guac_request("tokens", data={"username": GUAC_USER, "password": GUAC_PASS}, form=True)["authToken"]
            break
        except Exception:
            time.sleep(2)
    if not token:
        raise RuntimeError("Guacamole indisponível em " + GUAC_URL)

    ds = "postgresql"
    conns = guac_request(f"session/data/{ds}/connections", token)
    conn = next((c for c in conns.values() if c["name"] == GUAC_CONN_NAME), None)
    if conn is None:
        conn = guac_request(f"session/data/{ds}/connections", token, data={
            "parentIdentifier": "ROOT",
            "name": GUAC_CONN_NAME,
            "protocol": "vnc",
            "parameters": {"hostname": "desktop", "port": "5901", "password": "guacdesktop"},
            "attributes": {},
        })
    guac_state.update(token=token, ds=ds, conn_id=conn["identifier"])
    # o identificador do cliente é base64("<id>\0c\0<datasource>") sem padding
    raw = f"{conn['identifier']}\0c\0{ds}".encode()
    return f"{GUAC_URL}/#/client/{base64.b64encode(raw).decode().rstrip('=')}"


def guac_disconnect():
    """Encerra as sessões ativas da conexão com o desktop e invalida o token da API."""
    token = guac_state.get("token")
    if not token:
        return
    ds = guac_state["ds"]
    try:
        active = guac_request(f"session/data/{ds}/activeConnections", token) or {}
        ops = [{"op": "remove", "path": f"/{aid}"} for aid, a in active.items()
               if a.get("connectionIdentifier") == guac_state["conn_id"]]
        if ops:
            guac_request(f"session/data/{ds}/activeConnections", token, data=ops, method="PATCH")
        print(f"Conexão com o desktop encerrada ({len(ops)} sessão(ões)).")
        guac_request(f"tokens/{token}", method="DELETE")
    except Exception as e:
        print(f"Falha ao encerrar a conexão do Guacamole: {e}")

# Link da planilha do Google Sheets onde os cursos serão colados
SHEET_URL = "https://docs.google.com/spreadsheets/d/1zLrWjVJrCdkjZEtlIj9pHrLiFktvWtGjqJr3P1DuGmw/edit?usp=sharing"


async def main():
    driver = None
    try:
        if args.os == "guacamole":
            # Chromium do desktop XFCE, exposto na 9224 (ver docker-compose.guacamole.yml)
            cdp_url = "http://localhost:9224"
            viewer_url = guac_viewer_url()
            for _ in range(60):
                try:
                    urllib.request.urlopen(f"{cdp_url}/json/version", timeout=5).close()
                    break
                except Exception:
                    time.sleep(2)
            else:
                raise RuntimeError("CDP do desktop indisponível em " + cdp_url)
        elif args.os == "linux":
            # porta 4444 é o Selenium Grid (WebDriver), não CDP puro
            driver = webdriver.Remote(command_executor="http://localhost:4444", options=Options())
            # Selenium 4 expõe o endpoint CDP real via a capability "se:cdp"
            cdp_url = driver.capabilities["se:cdp"]
            viewer_url = "http://localhost:7900"
        else:
            # Chrome dentro da VM Windows, exposto na 9223 (ver oem/install.bat)
            cdp_url = "http://localhost:9223"
            viewer_url = "http://localhost:8006"
            urllib.request.urlopen(f"{cdp_url}/json/version", timeout=10).close()

        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(cdp_url)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else await context.new_page()

            await page.goto("https://adolfoguimaraes.dev")

            print(f"Acesse {viewer_url} e clique no menu 'Cursos'...")
            await page.wait_for_url("**/courses", timeout=300000)

            # Os títulos dos cursos são os únicos <h3> da página de catálogo
            await page.wait_for_selector("h3", timeout=300000)
            titulos = await page.locator("h3").all_text_contents()

            print(f"Total de títulos coletados: {len(titulos)}")
            for i, titulo in enumerate(titulos, start=1):
                print(f"  {i}. {titulo}")

            if not titulos:
                raise RuntimeError("Nenhum título encontrado em <h3> na página de cursos.")

            sheet_page = await context.new_page()
            await sheet_page.goto(SHEET_URL)
            await sheet_page.goto(f"{SHEET_URL.split('?')[0]}?gid=0#gid=0")

            # a planilha está com edição liberada para qualquer pessoa com o link, sem necessidade de login
            await sheet_page.wait_for_selector("div.docs-sheet-tab", timeout=300000)
            await sheet_page.screenshot(path="sheet_debug.png")
            print("Screenshot salvo em sheet_debug.png para conferência")

            # a caixa de nome garante foco na célula correta antes de digitar (o grid não tem foco por padrão)
            name_box = sheet_page.locator("#t-name-box")
            await name_box.click()
            await name_box.fill("A1")
            await name_box.press("Enter")

            # o editor de célula só fica visível quando a digitação começa; o Sheets captura
            # as teclas no grid, não num input/contenteditable estático, então usamos o teclado direto
            for linha, titulo in enumerate(titulos, start=1):
                print(f"Preenchendo A{linha}: {titulo}")
                await sheet_page.keyboard.type(titulo)
                await sheet_page.keyboard.press("Enter")

            print("Cursos colados na planilha.")
            print("Aguardando a planilha ser fechada para encerrar o script...")
            await sheet_page.wait_for_event("close", timeout=0)
    finally:
        if driver:
            driver.quit()
        guac_disconnect()

asyncio.run(main())