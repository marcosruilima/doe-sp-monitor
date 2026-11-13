import datetime, os, pathlib, sys
import pymupdf
from playwright.sync_api import sync_playwright

try:
    from zoneinfo import ZoneInfo
    _hoje = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).date()
except Exception:
    _hoje = datetime.date.today()

# No GitHub, os arquivos ficam dentro do repositorio (pasta doe_sp/).
PASTA = pathlib.Path(os.environ.get("DOE_PASTA", "doe_sp"))
PASTA.mkdir(parents=True, exist_ok=True)
PASTA_PDF = pathlib.Path(os.environ.get("DOE_PASTA_PDF", "pdf_tmp"))  # PDFs vao como artefato, nao para o repositorio
PASTA_PDF.mkdir(parents=True, exist_ok=True)
hoje = _hoje.strftime("%Y%m%d")
URL = "https://doe.sp.gov.br/sumario?journalName=Executivo&rootSectionName=Atos+de+Pessoal"
LIMITE = 450_000  # caracteres por arquivo de texto


def extrair(pdf):
    doc = pymupdf.open(str(pdf))
    total = doc.page_count
    partes, atual, tam, ini = [], [], 0, 1
    for i in range(1, total + 1):
        try:
            txt = doc[i - 1].get_text("text") or ""
        except Exception as e:
            txt = f"[erro ao extrair pagina: {e}]"
        bloco = f"\n=== PAGINA {i}/{total} ===\n{txt}\n"
        if tam + len(bloco) > LIMITE and atual:
            partes.append((ini, i - 1, "".join(atual)))
            atual, tam, ini = [], 0, i
        atual.append(bloco)
        tam += len(bloco)
    if atual:
        partes.append((ini, total, "".join(atual)))
    for n, (a, b, texto) in enumerate(partes, start=1):
        arq = PASTA / f"{pdf.stem}_texto_parte{n}_pag{a}-{b}.txt"
        arq.write_text(texto, encoding="utf-8")
        print("  texto:", arq.name, len(texto), "caracteres")


falhas = []
# Se o texto de hoje ja existe (execucao de reserva), nao baixa de novo.
if any(PASTA.glob(f"DOE_{hoje}_secao1_texto*")) and any(PASTA.glob(f"DOE_{hoje}_secao2_texto*")):
    print("Arquivos de hoje ja existem; nada a fazer.")
    sys.exit(0)

with sync_playwright() as p:
    nav = p.chromium.launch(headless=True)
    ctx = nav.new_context(viewport={"width": 1400, "height": 1000})
    pag = ctx.new_page()
    vistas = []
    ctx.on("request", lambda r: vistas.append(r.url))
    pag.goto(URL)
    pag.wait_for_timeout(5000)
    for secao, rotulo in [("secao1", "Atos Normativos"), ("secao2", "Atos de Pessoal")]:
        try:
            pag.get_by_text("Executivo", exact=True).first.click()
            pag.wait_for_timeout(3000)
            pag.get_by_text(rotulo, exact=False).first.click()
            pag.wait_for_timeout(5000)
            vistas.clear()
            pag.get_by_text("Diário completo certificado", exact=False).first.click()
            # Em headless o PDF vira download e a aba nunca "carrega": captura a URL pela rede.
            for _ in range(60):
                if any("/v1/" in u for u in vistas):
                    break
                pag.wait_for_timeout(1000)
            candidatas = [u for u in vistas if "/v1/" in u]
            if not candidatas:
                raise Exception("URL do PDF nao apareceu. Requisicoes vistas: " + " | ".join(vistas[-8:]) + " | abas: " + " | ".join(x.url for x in ctx.pages))
            url_pdf = candidatas[-1]
            print("  url do PDF:", url_pdf)
            resp = ctx.request.get(url_pdf, timeout=300000)
            corpo = resp.body()
            if not corpo.startswith(b"%PDF"):
                raise Exception("a resposta nao e um PDF: " + url_pdf)
            destino = PASTA_PDF / f"DOE_{hoje}_{secao}.pdf"
            destino.write_bytes(corpo)
            print("baixado:", secao, len(corpo) // 1024, "KB")
            for extra in ctx.pages[1:]:
                extra.close()
            extrair(destino)
        except Exception as e:
            falhas.append(secao)
            print("FALHOU", secao, "->", str(e)[:1500])
            pag.screenshot(path=str(PASTA_PDF / f"erro_{hoje}_{secao}.png"), full_page=True)
    nav.close()

if falhas:
    sys.exit(1)  # faz o workflow ficar vermelho e avisa por e-mail
