#!/usr/bin/env python3
"""Coleta o DOERJ (IOERJ): Parte I (Executivo) e Parte II (Legislativo) do dia e do dia anterior,
incluindo edicoes extras (qualquer caderno cujo nome comece por 'Parte I (' ou 'Parte II (').
Fluxo: do_seleciona_edicao.php?data=b64(AAAAMMDD) -> links mostra_edicao.php?session=... ->
pagina do visualizador traz var pd = GUID -> PDF em mostra_edicao.php?k=pd[:12]+'P'+pd[12:].
Salva texto (pdftotext (ordem de leitura)) e sumario em rj/doerj/AAAA-MM-DD_<caderno>.txt (PDF nao e versionado)."""
import base64, datetime, html, json, os, re, subprocess, sys, zoneinfo
import requests

BASE = "https://www.ioerj.com.br/portal/modules/conteudoonline/"
OUT = "rj/doerj"
HOJE = datetime.datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo")).date()
DIAS = int(os.environ.get("DIAS", "1"))
S = requests.Session()
S.headers["User-Agent"] = "Mozilla/5.0 (compatible; relgov-monitor)"
status = {"coletado_em_utc": datetime.datetime.utcnow().isoformat(timespec="seconds"), "hoje": str(HOJE), "cadernos": [], "erros": []}

def slug(t):
    t = re.sub(r"[^a-z0-9]+", "-", t.lower().replace("(", " ").replace(")", " ")).strip("-")
    return t[:40]

def coletar(dia):
    data = base64.b64encode(dia.strftime("%Y%m%d").encode()).decode()
    r = S.get(f"{BASE}do_seleciona_edicao.php?data={data}", timeout=60)
    r.raise_for_status(); r.encoding = "utf-8"
    links = re.findall(r'<a href="(mostra_edicao\.php\?session=[^"]+)"[^>]*>([^<]+)</a>', r.text)
    if not links:
        status["cadernos"].append({"dia": str(dia), "caderno": None, "nota": "sem cadernos listados"})
    for href, nome in links:
        nome = html.unescape(nome).strip()
        if not re.match(r"Parte (I|II) \(", nome):  # exclui IB, IV, V
            continue
        arq = f"{OUT}/{dia}_{slug(nome)}.txt"
        if dia < HOJE and os.path.exists(arq):
            continue
        try:
            p = S.get(BASE + html.unescape(href), timeout=60); p.encoding = "utf-8"
            pd = re.search(r'var pd = "([0-9A-F-]{36})"', p.text).group(1)
            sumario = [html.unescape(re.sub(r"\s+", " ", o)).strip() for o in re.findall(r'<option[^>]*value="\d+"[^>]*>([^<]+)</option>', p.text.split('id="sumario"')[1].split("</select>")[0])]
            pdf = S.get(f"{BASE}mostra_edicao.php?k={pd[:12]}P{pd[12:]}", timeout=180)
            assert pdf.content[:4] == b"%PDF", "resposta nao e PDF"
            tmp = "/tmp/doerj.pdf"; open(tmp, "wb").write(pdf.content)
            txt = subprocess.run(["pdftotext", tmp, "-"], capture_output=True, text=True).stdout
            os.makedirs(OUT, exist_ok=True)
            with open(arq, "w") as f:
                f.write(f"# DOERJ {dia} - {nome}\n# bytes_pdf={len(pdf.content)} caracteres_texto={len(txt)}\n\n## SUMARIO\n" + "\n".join(sumario) + "\n\n## TEXTO\n" + txt)
            status["cadernos"].append({"dia": str(dia), "caderno": nome, "arquivo": arq, "bytes_pdf": len(pdf.content), "chars": len(txt), "itens_sumario": len(sumario)})
        except Exception as e:
            status["erros"].append(f"{dia} {nome}: {e!r}")

for i in range(DIAS + 1):
    try:
        coletar(HOJE - datetime.timedelta(days=i))
    except Exception as e:
        status["erros"].append(f"{HOJE - datetime.timedelta(days=i)}: {e!r}")
# retencao: apaga textos com mais de 7 dias (volume ~3 MB/dia)
if os.path.isdir(OUT):
    corte = str(HOJE - datetime.timedelta(days=7))
    for n in os.listdir(OUT):
        if n[:10] < corte and n.endswith(".txt"):
            os.remove(f"{OUT}/{n}")
os.makedirs(OUT, exist_ok=True)
json.dump(status, open(f"{OUT}/status.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(status, ensure_ascii=False, indent=1))
