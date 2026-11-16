"""Coleta diária da Alesp (reuniões de comissão, pautas e sessões do Plenário).
Grava em alesp/dados, alesp/pautas e alesp/sessoes. Janela: hoje-7 até hoje+60."""
import datetime, json, os, re, sys, time, urllib.error, urllib.parse, urllib.request
from html.parser import HTMLParser

BASE = "https://legis-api-portal-prd.al.sp.gov.br"
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
           "Origin": "https://www.al.sp.gov.br", "Referer": "https://www.al.sp.gov.br/"}
HOJE = datetime.date.today()
INI = (HOJE - datetime.timedelta(days=7)).isoformat()
FIM = (HOJE + datetime.timedelta(days=60)).isoformat()
CORTE_PAUTA = (HOJE - datetime.timedelta(days=1)).isoformat()   # baixa pautas de reuniões de ontem em diante
CORTE_SESSAO = (HOJE + datetime.timedelta(days=45)).isoformat() # pauta/ordem do dia das sessões nos próximos 45 dias
erros = []


def get(url, binario=False, tentativas=3):
    ultimo = None
    for i in range(tentativas):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=40) as r:
                corpo = r.read()
                if binario:
                    return corpo
                return json.loads(corpo.decode("utf-8"))
        except Exception as e:
            ultimo = f"{type(e).__name__}: {e}"
            time.sleep(2 * (i + 1))
    erros.append({"url": url, "erro": ultimo})
    return None


class Texto(HTMLParser):
    def __init__(self):
        super().__init__(); self.p = []; self.skip = 0
    def handle_starttag(self, tag, a):
        if tag in ("script", "style"): self.skip += 1
        if tag in ("p", "div", "br", "tr", "li", "h1", "h2", "h3", "h4", "table"): self.p.append("\n")
        if tag in ("td", "th"): self.p.append(" | ")
    def handle_endtag(self, tag):
        if tag in ("script", "style") and self.skip: self.skip -= 1
    def handle_data(self, d):
        if not self.skip: self.p.append(d)


def html_para_texto(b):
    for enc in ("utf-8", "latin-1"):
        try:
            s = b.decode(enc); break
        except UnicodeDecodeError:
            continue
    t = Texto(); t.feed(s)
    txt = "".join(t.p)
    txt = re.sub(r"[ \t\xa0]+", " ", txt)
    return re.sub(r"\n\s*\n+", "\n", txt).strip()


def paginar(caminho, params):
    itens, page = [], 0
    while True:
        q = dict(params, page=page, size=100)
        d = get(BASE + caminho + "?" + urllib.parse.urlencode(q))
        if d is None:
            return None
        itens += d.get("content", [])
        if d.get("last", True) or page >= 20:
            return itens
        page += 1


def grava(caminho, obj):
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1, sort_keys=True)


def main():
    # 1) Reuniões de comissão
    reunioes = paginar("/colegiado/reunioes", {
        "dataInicio": INI, "dataFim": FIM, "pesquisarAtas": "false", "pesquisarConjuntas": "false"})
    n_pautas = 0
    if reunioes is None:
        print("FALHA: reuniões", file=sys.stderr)
    else:
        reunioes.sort(key=lambda r: (r.get("dtReuniao") or "", r.get("idReuniao")))
        grava("alesp/dados/reunioes.json", reunioes)
        os.makedirs("alesp/pautas", exist_ok=True)
        for r in reunioes:
            if (r.get("dtReuniao") or "")[:10] < CORTE_PAUTA:
                continue
            for d in r.get("documentosReuniao") or []:
                if d.get("tipo") not in ("Pauta de colegiado", "Comunicado de colegiado") or not d.get("linkArquivo"):
                    continue
                b = get(d["linkArquivo"], binario=True)
                if b is None:
                    continue
                cab = (f"REUNIAO {r['idReuniao']} | {r.get('dtReuniao')} | "
                       f"{', '.join(c.get('sigla') or c.get('nome') or '' for c in r.get('colegiadosRelacionados') or [])} | "
                       f"{d.get('tipo')} | {d.get('resumo')}\nFONTE {d['linkArquivo']}\n\n")
                tipo = "pauta" if d["tipo"].startswith("Pauta") else "comunicado"
                with open(f"alesp/pautas/reuniao_{r['idReuniao']}_{tipo}.txt", "w", encoding="utf-8") as f:
                    f.write(cab + html_para_texto(b) + "\n")
                n_pautas += 1

    # 2) Sessões do Plenário
    sessoes = paginar("/sessoes-plenarias/consulta", {"dataInicial": INI, "dataFinal": FIM})
    n_sess = 0
    if sessoes is None:
        print("FALHA: sessões", file=sys.stderr)
    else:
        sessoes.sort(key=lambda s: (s.get("dtInicio") or "", s.get("id")))
        grava("alesp/dados/sessoes.json", sessoes)
        for s in sessoes:
            ini = (s.get("dtInicio") or "")[:10]
            if ini < CORTE_PAUTA or ini > CORTE_SESSAO:
                continue
            if s.get("temPauta"):
                d = get(f"{BASE}/sessoes-plenarias/{s['id']}/pauta")
                if d is not None:
                    grava(f"alesp/sessoes/{s['id']}_pauta.json", d); n_sess += 1
            if s.get("temOrdemDoDia"):
                d = get(f"{BASE}/sessoes-plenarias/{s['id']}/ordem-do-dia")
                if d is not None:
                    grava(f"alesp/sessoes/{s['id']}_ordem_do_dia.json", d); n_sess += 1

    status = {
        "coletado_em_utc": datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "janela": [INI, FIM],
        "reunioes": None if reunioes is None else len(reunioes),
        "pautas_baixadas": n_pautas,
        "sessoes": None if sessoes is None else len(sessoes),
        "arquivos_de_sessao": n_sess,
        "erros": erros,
    }
    grava("alesp/dados/status.json", status)
    print(json.dumps(status, ensure_ascii=False, indent=1))
    sys.exit(1 if (reunioes is None or sessoes is None) else 0)


main()
