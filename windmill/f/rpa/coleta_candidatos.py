import re

from playwright.sync_api import Page, sync_playwright

from f.rpa.guac_session import desktop_session

HOME_URL = "https://divulgacandcontas.tse.jus.br/divulga/"
UF = "SE"
CARGOS = {"Governador": "3", "Senador": "5"}
COLUNAS = ["Nome", "CPF", "Partido", "Número"]
ITEM = ".d-flex.w-100"


def abrir_candidaturas(page: Page):
    # o portal só carrega a home corretamente após acessar a raiz primeiro
    page.goto(HOME_URL)
    page.goto(f"{HOME_URL}#/home")
    page.locator("a").filter(has_text="Nordeste").first.click(timeout=60000)
    page.get_by_role("button", name="SERGIPE").click()
    page.get_by_role("button", name="Candidaturas").click()


def pesquisar(page: Page, codigo_cargo: str) -> int:
    page.get_by_label("Cargo *:").select_option(codigo_cargo)
    page.get_by_role("button", name="Pesquisar").click()
    page.wait_for_selector(ITEM, timeout=60000)
    return page.locator(ITEM).count()


def ler_candidato(page: Page) -> list[str]:
    header = page.locator("dvg-candidato-header")
    header.locator("h2").wait_for(timeout=60000)
    nome = header.locator("h2").inner_text().strip()
    labels = [t.strip() for t in header.locator("span label").all_inner_texts()]
    cpf = next((m.group(1) for t in labels if (m := re.search(r"CPF:\s*([\d.\-]+)", t))), "")
    # o partido é o rótulo logo após "Cargo - Estado/UF"
    idx = next((i for i, t in enumerate(labels) if t.endswith(f"/{UF}")), None)
    partido = labels[idx + 1] if idx is not None and idx + 1 < len(labels) else ""
    numero = header.locator(".numero-partido").inner_text().strip()
    return [nome, cpf, partido, numero]


def coletar(page: Page) -> dict[str, list[list[str]]]:
    abrir_candidaturas(page)
    por_cargo = {}
    for cargo, codigo in CARGOS.items():
        total = pesquisar(page, codigo)
        linhas = por_cargo[cargo] = []
        print(f"{cargo}: {total} candidato(s) em Sergipe")
        for i in range(total):
            page.locator(ITEM).nth(i).click()
            linha = ler_candidato(page)
            print(f"  {i + 1}/{total}: {linha}")
            linhas.append(linha)
            # voltar mantém o cargo e a lista da pesquisa
            page.go_back()
            page.wait_for_selector(ITEM, timeout=60000)
    return por_cargo


def preencher_aba(sheet: Page, indice: int, linhas: list[list[str]]):
    abas = sheet.locator("div.docs-sheet-tab")
    if abas.count() <= indice:
        # Shift+F11 insere uma nova aba na planilha
        sheet.keyboard.press("Shift+F11")
        sheet.wait_for_function(
            "n => document.querySelectorAll('div.docs-sheet-tab').length > n", arg=indice, timeout=30000
        )
    abas.nth(indice).click()

    name_box = sheet.locator("#t-name-box")
    for numero_linha, linha in enumerate([COLUNAS, *linhas], start=1):
        # posiciona o cursor explicitamente em A<linha>: não depende do Enter voltar à coluna A
        name_box.click()
        name_box.fill(f"A{numero_linha}")
        name_box.press("Enter")
        for valor in linha:
            sheet.keyboard.type(valor)
            # remove a sugestão de autocompletar do Sheets, que o Tab aceitaria
            sheet.keyboard.press("Delete")
            sheet.keyboard.press("Tab")


def escrever_planilha(context, sheet_url: str, por_cargo: dict[str, list[list[str]]]):
    """Grava cada cargo em uma aba: a primeira recebe Governador e a segunda, Senador."""
    sheet = context.new_page()
    sheet.goto(sheet_url)
    sheet.goto(f"{sheet_url.split('?')[0]}?gid=0#gid=0")
    sheet.wait_for_selector("div.docs-sheet-tab", timeout=120000)

    for indice, cargo in enumerate(CARGOS):
        print(f"Gravando {cargo} na aba {indice + 1}")
        preencher_aba(sheet, indice, por_cargo[cargo])
    return sheet

def main(
    sheet_url: str = "",
    assisted: bool = True,
    max_wait_s: int = 1800,
):
    """Coleta nome, CPF, partido e número dos candidatos a Governador e Senador de Sergipe.

    sheet_url: planilha editável; Governador vai na primeira aba e Senador na segunda (criada se faltar).
    Vazio = só retorna o resultado.
    assisted=True: com planilha, mantém o desktop aberto até a aba da planilha ser fechada.
    """
    with desktop_session("coleta-candidatos") as desktop:
        print(f"Acompanhe o robô em: {desktop.viewer_url}")

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(desktop.cdp_url)
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            por_cargo = coletar(page)
            total = sum(len(v) for v in por_cargo.values())
            print(f"Total de candidatos coletados: {total}")
            if not total:
                raise RuntimeError("Nenhum candidato encontrado em Sergipe.")

            if sheet_url:
                sheet = escrever_planilha(context, sheet_url, por_cargo)
                print("Candidatos gravados na planilha.")
                if assisted:
                    print("Aguardando a planilha ser fechada para encerrar o robô...")
                    sheet.wait_for_event("close", timeout=max_wait_s * 1000)

    return {"status": "finalizado", "estado": UF, "total": total, "colunas": COLUNAS, "candidatos": por_cargo}
