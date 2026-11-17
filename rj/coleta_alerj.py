"""Coleta ALERJ: editais das comissões (Lotus Notes), sessões do Plenário (Ordem do Dia) e manchetes dos jornais do RJ.
Saída em rj/alerj/ e rj/jornais/. Dados públicos brutos."""
import base64, html, json, os, pathlib, re, urllib.request, datetime, hashlib, zoneinfo
HOJE = datetime.datetime.now(zoneinfo.ZoneInfo("America/Sao_Paulo")).date()
DE = HOJE - datetime.timedelta(days=int(os.environ.get("RETRO", "2")))
UA = {"User-Agent": "Mozilla/5.0"}
BASE = "https://www3.alerj.rj.gov.br/lotus_notes/default.asp?id=%d&url=%s"
erros = []

def get(u, timeout=90):
    req = urllib.request.Request(u, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")

def notes(id_, path, timeout=120):
    return get(BASE % (id_, base64.b64encode(path.encode()).decode()), timeout)

def texto(h):
    h = re.sub(r"(?is)<(script|style).*?</\1>", "", h)
    h = re.sub(r"(?i)<br\s*/?>|</p>|</tr>|</div>|</li>", "\n", h)
    h = re.sub(r"(?s)<[^>]+>", " ", h)
    h = html.unescape(h)
    h = re.sub(r"[ \t\xa0]+", " ", h)
    return re.sub(r"\n\s*\n+", "\n", h).strip()

def conteudo_doc(h):
    """Retira o menu do portal e o rodapé; mantém só o edital/pauta."""
    t = texto(h)
    m = t.rfind('alt="por ano">Por Ano')
    if m >= 0:
        t = t[m + len('alt="por ano">Por Ano'):].strip()
    f = t.find("Clique aqui caso você tenha dificuldade")
    if f >= 0:
        t = t[:f].strip()
    return t

def d(s):
    return datetime.datetime.strptime(s, "%d/%m/%Y").date()

out = pathlib.Path("rj/alerj"); (out / "pautas").mkdir(parents=True, exist_ok=True); (out / "plenario").mkdir(exist_ok=True)

# 1) Comissões: editais
reunioes = []
try:
    lista = notes(66, "/compcom.nsf/EditalInt?OpenForm&Start=1&Count=1000")
    rows = re.findall(r'data-role="([^"]+)">(\d\d/\d\d/\d{4})</a></font></td><td><font >([^<]*)</font></td><td><font[^>]*>([^<]*)</font></td><td>([^<]*)</td>', lista)
    for path, dt, tipo, com, canc in rows:
        path = html.unescape(path)
        if d(dt) < DE:
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", com.lower().encode("ascii", "ignore").decode())[:40].strip("-")
        arq = f"{d(dt).isoformat()}_{slug}_{hashlib.md5(path.encode()).hexdigest()[:6]}.txt"
        ja = (out / "pautas" / arq).exists() and d(dt) < HOJE
        if not ja:
            try:
                (out / "pautas" / arq).write_text(conteudo_doc(notes(66, path)), encoding="utf-8")
            except Exception as e:
                erros.append(f"edital {dt} {com}: {e!r}"[:200]); arq = None
        reunioes.append({"data": d(dt).isoformat(), "tipo": tipo.strip(), "comissao": html.unescape(com).strip(), "situacao": canc.strip(), "arquivo": arq})
    total_lista = len(rows)
except Exception as e:
    erros.append(f"lista editais: {e!r}"[:300]); total_lista = 0
(out / "reunioes_comissoes.json").write_text(json.dumps(sorted(reunioes, key=lambda r: r["data"]), ensure_ascii=False, indent=1))

# 2) Plenário: sessões (Ordem do Dia)
sess = []
try:
    p = notes(59, "/ordemdia.nsf/OrdemInt?OpenForm&Start=1&Count=1000")
    rows = re.findall(r'data-role="(/ordemdia\.nsf/[^"]+OpenDocument)">(\d\d/\d\d/\d{4})</a></font></td><td[^>]*><font >([^<]*)</font></td>.*?<font >\s*([^<]*)</font>', p, re.S)
    for path, dt, hora, tipo in rows:
        if d(dt) < DE:
            continue
        arq = f"{d(dt).isoformat()}_{hora.replace(':','')[:4]}_plenario.txt"
        if not ((out / "plenario" / arq).exists() and d(dt) < HOJE):
            try:
                (out / "plenario" / arq).write_text(conteudo_doc(notes(59, html.unescape(path))), encoding="utf-8")
            except Exception as e:
                erros.append(f"plenario {dt}: {e!r}"[:200]); arq = None
        sess.append({"data": d(dt).isoformat(), "hora": hora.strip(), "tipo": tipo.strip(), "arquivo": arq})
    total_pl = len(rows)
except Exception as e:
    erros.append(f"plenario: {e!r}"[:300]); total_pl = 0
(out / "reunioes_plenario.json").write_text(json.dumps(sess, ensure_ascii=False, indent=1))

# 3) Notícias ALERJ: guarda o script que carrega a lista (para descobrir o endpoint)
try:
    (out / "noticias_listar.js").write_text(get("https://www.alerj.rj.gov.br/Scripts/Listar/listarNoticias.js"), encoding="utf-8")
except Exception as e:
    erros.append(f"noticias js: {e!r}"[:200])

# 4) Jornais do RJ: manchetes e links das páginas de listagem
J = {"odia_rio": "https://odia.ig.com.br/rio-de-janeiro", "oglobo_rio": "https://oglobo.globo.com/rio/",
     "extra_politica": "https://extra.globo.com/politica/", "extra_rio": "https://extra.globo.com/rio/"}
jd = pathlib.Path("rj/jornais"); jd.mkdir(exist_ok=True)
for k, u in J.items():
    try:
        h = get(u, 60)
        itens, vistos = [], set()
        for href, inner in re.findall(r'<a[^>]+href="([^"#]+)"[^>]*>(.*?)</a>', h, re.S):
            t = texto(inner)
            if len(t) < 35 or href in vistos:
                continue
            vistos.add(href)
            itens.append({"titulo": t[:220], "url": href if href.startswith("http") else u.split("/", 3)[0] + "//" + u.split("/")[2] + href})
        (jd / f"{k}.json").write_text(json.dumps({"coletado_em": datetime.datetime.utcnow().isoformat() + "Z", "fonte": u, "itens": itens[:80]}, ensure_ascii=False, indent=1))
    except Exception as e:
        erros.append(f"jornal {k}: {e!r}"[:200])

(out / "status.json").write_text(json.dumps({"coletado_em_utc": datetime.datetime.utcnow().isoformat() + "Z", "hoje": HOJE.isoformat(),
    "editais_na_lista": total_lista, "editais_coletados": len(reunioes), "sessoes_plenario_na_lista": total_pl, "sessoes_coletadas": len(sess), "erros": erros}, indent=1, ensure_ascii=False))
print(open(out / "status.json").read())
