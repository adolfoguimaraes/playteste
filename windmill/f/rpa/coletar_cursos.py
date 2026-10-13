from playwright.sync_api import sync_playwright

from f.rpa.guac_session import desktop_session

SHEET_URL = "https://docs.google.com/spreadsheets/d/1zLrWjVJrCdkjZEtlIj9pHrLiFktvWtGjqJr3P1DuGmw/edit?usp=sharing"


def main(
    sheet_url: str = SHEET_URL,
    assisted: bool = True,
    max_wait_s: int = 1800,
):
    """Coleta os títulos dos cursos e cola na planilha, dentro de um desktop do Guacamole.

    assisted=True: espera o usuário clicar em 'Cursos' e só termina quando a planilha for fechada.
    assisted=False: navega direto para /courses e termina sozinho após preencher a planilha.
    """
    sheet_url = sheet_url or SHEET_URL
    with desktop_session("coletar-cursos") as desktop:
        print(f"Acompanhe o robô em: {desktop.viewer_url}")

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(desktop.cdp_url)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            if assisted:
                page.goto("https://adolfoguimaraes.dev")
                print("Clique no menu 'Cursos' no desktop...")
                page.wait_for_url("**/courses", timeout=max_wait_s * 1000)
            else:
                page.goto("https://adolfoguimaraes.dev/courses")

            page.wait_for_selector("h3", timeout=60000)
            titulos = page.locator("h3").all_text_contents()
            print(f"Total de títulos coletados: {len(titulos)}")
            if not titulos:
                raise RuntimeError("Nenhum título encontrado em <h3> na página de cursos.")

            sheet_page = context.new_page()
            sheet_page.goto(sheet_url)
            sheet_page.goto(f"{sheet_url.split('?')[0]}?gid=0#gid=0")
            sheet_page.wait_for_selector("div.docs-sheet-tab", timeout=120000)

            # a caixa de nome garante o foco na célula A1 antes de digitar
            name_box = sheet_page.locator("#t-name-box")
            name_box.click()
            name_box.fill("A1")
            name_box.press("Enter")

            for linha, titulo in enumerate(titulos, start=1):
                print(f"Preenchendo A{linha}: {titulo}")
                sheet_page.keyboard.type(titulo)
                sheet_page.keyboard.press("Enter")

            if assisted:
                print("Aguardando a planilha ser fechada para encerrar o robô...")
                sheet_page.wait_for_event("close", timeout=max_wait_s * 1000)

    return {"status": "finalizado", "total_cursos": len(titulos), "cursos": titulos}
