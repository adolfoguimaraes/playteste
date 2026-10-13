import re
from playwright.sync_api import Playwright, sync_playwright, expect


def run(playwright: Playwright) -> None:
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()
    page.goto("https://divulgacandcontas.tse.jus.br/divulga/")
    page.goto("https://divulgacandcontas.tse.jus.br/divulga/#/home")
    page.locator("a").filter(has_text="Nordeste Alagoas, Bahia, Cear").click()
    page.get_by_role("button", name="SERGIPE").click()
    page.get_by_role("button", name="Candidaturas").click()
    page.get_by_label("Cargo *:").select_option("3")
    page.get_by_role("button", name="Pesquisar").click()
    page.locator(".d-flex.w-100").first.click()
    page.get_by_role("heading", name="DR. HELTON").click()
    page.get_by_text("CPF: 884.248.555-").click()
    page.get_by_text("Partido Socialismo E Liberdade - PSOL").click()
    page.locator("dvg-candidato-header").get_by_text("50").click()
    page.goto("https://divulgacandcontas.tse.jus.br/divulga/#/candidato/NORDESTE/SE/20322002026")
    page.get_by_text("EMANUEL CACHO - EMANUEL").click()
    page.get_by_role("heading", name="EMANUEL CACHO").click()
    page.get_by_text("CPF: 170.231.225-").click()
    page.get_by_text("Partido Da Social Democracia").click()
    page.locator("dvg-candidato-header").get_by_text("45").click()

    # ---------------------
    context.close()
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
