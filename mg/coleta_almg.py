"""Coleta diária da ALMG (Minas Gerais): agenda e pautas de comissões, Plenário, Diário do Legislativo e notícias.
Grava em mg/almg/. Janela de agenda: de ontem até hoje+JANELA dias (a ALMG só publica convocações com poucos dias de antecedência)."""
import datetime, json, os, re, subprocess, sys, tempfile, time, urllib.error, urllib.request
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

BASE = "https://www.almg.gov.br"
HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
           "Accept": "text/html,application/pdf,*/*"}
HOJE = datetime.datetime.now(ZoneInfo("America/Sao_Paulo")).date()
JANELA = int(os.environ.get("JANELA", "30"))
SAIDA = "mg/almg"
erros = []

def get(url, tentativas=3):
    ultimo = None
    for i in range(tentativas):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=60) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            ultimo = f"HTTP {e.code}"
        except Exception as e:
            ultimo = f"{type(e).__name__}: {e}"
        time.sleep(2 * (i + 1))
    erros.append({"url": url, "erro": ultimo})
    return None

class Texto(HTMLParser):
    def __init__(self):
        super().__init__(); self.p = []; self.skip = 0
    def handle_starttag(self, tag, a):
        if tag in ("script", "style", "nav", "header", "footer"): self.skip += 1
        if tag in ("p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table", "section"): self.p.append("\n")
        if tag in ("td", "th"): self.p.append(" | ")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "nav", "header", "footer") and self.skip: self.skip -= 1
    def handle_data(self, d):
        if not self.skip: self.p.append(d)

def html_para_texto(b):
    s = b.decode("utf-8", "replace")
    t = Texto(); t.feed(s)
    txt = re.sub(r"[ \t\xa0]+", " ", "".join(t.p))
    return re.sub(r"\n\s*\n+", "\n", txt).strip()

def grava(caminho, conteudo, binario=False):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "wb" if binario else "w", **({} if binario else {"encoding": "utf-8"})) as f:
        f.write(conteudo)

RE_COM = re.compile(r'comissoes/reuniao/\?idTipo=\d+&(?:amp;)?idCom=\d+&(?:amp;)?dia=\d+&(?:amp;)?mes=\d+&(?:amp;)?ano=\d+&(?:amp;)?hr=\d\d:\d\d')
RE_PLE = re.compile(r'plenario/reuniao/\?dia=\d+&(?:amp;)?mes=\d+&(?:amp;)?ano=\d+&(?:amp;)?hr=\d\d:\d\d')

def params(link):
    return dict(p.split("=", 1) for p in link.split("?", 1)[1].replace("&amp;", "&").split("&") if "=" in p)

def links_periodo(caminho, regex, ini, fim):
    """A agenda aceita dataInicio e dataFim (dd/mm/aaaa) e pagina=N (10 itens por página)."""
    achados, paginas = {}, 0
    for pg in range(1, 80):
        url = (f"{BASE}{caminho}?pesquisou=true&dataInicio={ini:%d/%m/%Y}&dataFim={fim:%d/%m/%Y}"
               + (f"&pagina={pg}" if pg > 1 else ""))
        b = get(url)
        if b is None:
            break
        paginas += 1
        novos = 0
        for l in regex.findall(b.decode("utf-8", "replace")):
            l = l.replace("&amp;", "&")
            if l not in achados:
                achados[l] = True; novos += 1
        if novos == 0:
            break
        time.sleep(0.3)
    return list(achados), paginas

def coletar_agenda(nome, caminho, regex, prefixo):
    ini, fim = HOJE - datetime.timedelta(days=1), HOJE + datetime.timedelta(days=JANELA)
    links, pags = links_periodo(caminho, regex, ini, fim)
    todos = {l: params(l) for l in links}
    reunioes = []
    for l, q in sorted(todos.items(), key=lambda x: (x[1]["ano"], x[1]["mes"].zfill(2), x[1]["dia"].zfill(2), x[1].get("hr", ""))):
        dd = datetime.date(int(q["ano"]), int(q["mes"]), int(q["dia"]))
        hr = q.get("hr", "").replace(":", "")
        arq = f"{SAIDA}/pautas/{dd.isoformat()}_{hr}_{prefixo}" + (f"_com{q['idCom']}_tipo{q.get('idTipo','')}" if "idCom" in q else "") + ".txt"
        if dd < HOJE and os.path.exists(arq):
            reunioes.append({"data": dd.isoformat(), **q, "arquivo": arq, "ja_baixada": True}); continue
        url = BASE + "/atividade-parlamentar/" + l
        b = get(url)
        if b is None:
            continue
        grava(arq, f"URL: {url}\n\n" + html_para_texto(b))
        reunioes.append({"data": dd.isoformat(), **q, "arquivo": arq})
        time.sleep(0.3)
    return reunioes, {"periodo": f"{ini} a {fim}", "paginas_lidas": pags, "reunioes_encontradas": len(links)}

def diario_legislativo():
    ok = []
    for d in range(0, 8):
        dia = HOJE - datetime.timedelta(days=d)
        txtf = f"{SAIDA}/diario_legislativo/{dia.isoformat()}.txt"
        if os.path.exists(txtf):
            continue
        b = get(f"https://diariolegislativo.almg.gov.br/{dia.year}/L{dia.strftime('%Y%m%d')}.pdf")
        if not b or not b.startswith(b"%PDF"):
            continue
        pdf = os.path.join(tempfile.gettempdir(), f"L{dia:%Y%m%d}.pdf"); open(pdf, "wb").write(b)
        os.makedirs(os.path.dirname(txtf), exist_ok=True)
        r = subprocess.run(["pdftotext", pdf, txtf], capture_output=True, text=True)
        ok.append({"data": dia.isoformat(), "bytes_pdf": len(b), "rc": r.returncode})
    return ok

def noticias():
    url = f"{BASE}/comunicacao/noticias/index.html?lq=&reloaded=&pesquisou=true&q=&di=&df=&tagLocalizacao=73"
    b = get(url)
    if not b:
        return 0
    s = b.decode("utf-8", "replace")
    itens = []
    for m in re.finditer(r'<a[^>]+href="([^"]*comunicacao/noticias/[^"]+)"[^>]*>(.*?)</a>', s, flags=re.S):
        titulo = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", m.group(2))).strip()
        if titulo and len(titulo) > 15:
            itens.append({"titulo": titulo, "url": m.group(1) if m.group(1).startswith("http") else BASE + m.group(1)})
    vistos, unicos = set(), []
    for i in itens:
        if i["url"] not in vistos:
            vistos.add(i["url"]); unicos.append(i)
    grava(f"{SAIDA}/noticias.json", json.dumps({"coletado_em": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "itens": unicos}, ensure_ascii=False, indent=1))
    return len(unicos)

def main():
    status = {"coletado_em_utc": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z", "hoje": HOJE.isoformat(), "janela_dias": JANELA}
    com, diag_com = coletar_agenda("comissoes", "/atividade-parlamentar/comissoes/agenda/", RE_COM, "comissao")
    ple, diag_ple = coletar_agenda("plenario", "/atividade-parlamentar/plenario/agenda/", RE_PLE, "plenario")
    grava(f"{SAIDA}/reunioes_comissoes.json", json.dumps(com, ensure_ascii=False, indent=1))
    grava(f"{SAIDA}/reunioes_plenario.json", json.dumps(ple, ensure_ascii=False, indent=1))
    status.update(reunioes_comissoes=len(com), reunioes_plenario=len(ple), diario_legislativo=diario_legislativo(),
                  noticias=noticias(), diagnostico_agenda_comissoes=diag_com, diagnostico_agenda_plenario=diag_ple, erros=erros)
    grava(f"{SAIDA}/status.json", json.dumps(status, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in status.items() if not k.startswith("diagnostico")}, ensure_ascii=False, indent=1))
    sys.exit(1 if not com and not ple and erros else 0)

main()
