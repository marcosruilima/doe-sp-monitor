import json, os, re, sys, time, urllib.request, urllib.error
from datetime import datetime, timezone, timedelta

hoje = datetime.now(timezone(timedelta(hours=-3)))
d, m, a = hoje.day, hoje.month, hoje.year
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ALVOS = {
 "almg_comissoes_agenda": f"https://www.almg.gov.br/atividade-parlamentar/comissoes/agenda/?dia={d}&mes={m}&ano={a}",
 "almg_comissoes_agenda_base": "https://www.almg.gov.br/atividade-parlamentar/comissoes/agenda/",
 "almg_reuniao_ccj": f"https://www.almg.gov.br/atividade-parlamentar/comissoes/reuniao/?idTipo=1&idCom=5&dia=17&mes=11&ano=2026&hr=10:30",
 "almg_plenario_agenda": "https://www.almg.gov.br/atividade-parlamentar/plenario/agenda/",
 "almg_plenario_reuniao": "https://www.almg.gov.br/atividade-parlamentar/plenario/reuniao/?dia=17&mes=11&ano=2026&hr=14:00",
 "almg_diario_legislativo_pagina": "https://www.almg.gov.br/transparencia/diario-do-legislativo/",
 "almg_diario_legislativo_pdf": f"https://diariolegislativo.almg.gov.br/{a}/L{a}{m:02d}{d:02d}.pdf",
 "almg_diario_legislativo_pdf_17": "https://diariolegislativo.almg.gov.br/2026/L20261117.pdf",
 "almg_noticias": "https://www.almg.gov.br/comunicacao/noticias/index.html?lq=&reloaded=&pesquisou=true&q=&di=&df=&tagLocalizacao=73",
 "almg_dados_abertos": "https://www.almg.gov.br/transparencia/dados-abertos/",
 "almg_api_v2": "https://dadosabertos.almg.gov.br/api/v2/",
 "jornal_mg_home": "https://www.jornalminasgerais.mg.gov.br/",
 "agencia_minas": "https://www.agenciaminas.mg.gov.br/",
 "sedectes_noticias": "https://desenvolvimento.mg.gov.br/noticias",
 "fazenda_noticias": "https://www.fazenda.mg.gov.br/noticias",
}
def tenta(url, com_ua=True):
    h = {"Accept": "text/html,application/pdf,application/json,*/*"}
    if com_ua: h["User-Agent"] = UA
    req = urllib.request.Request(url, headers=h)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            corpo = r.read(400000)
            return dict(status=r.status, tipo=r.headers.get("Content-Type"), bytes_lidos=len(corpo),
                        final=r.geturl(), seg=round(time.time()-t0,1), inicio=corpo[:300].decode("utf-8","replace")), corpo
    except urllib.error.HTTPError as e:
        return dict(status=e.code, erro=str(e), seg=round(time.time()-t0,1)), b""
    except Exception as e:
        return dict(status=None, erro=repr(e), seg=round(time.time()-t0,1)), b""

os.makedirs("mg/teste", exist_ok=True)
res = {}
corpos = {}
for nome, url in ALVOS.items():
    r, c = tenta(url)
    res[nome] = dict(url=url, **r)
    corpos[nome] = c
    print(nome, r.get("status"), r.get("tipo"), r.get("bytes_lidos"), flush=True)

# links do jornal minas gerais (para descobrir padrão de download)
c = corpos.get("jornal_mg_home", b"").decode("utf-8", "replace")
res["jornal_mg_links"] = sorted(set(re.findall(r'href="([^"]+)"', c)))[:80]
res["jornal_mg_pdf_refs"] = sorted(set(re.findall(r'[^"\'\s]+\.pdf[^"\'\s]*', c)))[:40]
res["jornal_mg_scripts"] = sorted(set(re.findall(r'src="([^"]+\.js[^"]*)"', c)))[:20]
# estrutura das agendas (primeiros links de reunião)
c = corpos.get("almg_comissoes_agenda", b"").decode("utf-8", "replace")
res["almg_agenda_links_reuniao"] = sorted(set(re.findall(r'href="([^"]*comissoes/reuniao/[^"]+)"', c)))[:30]
# amostra do texto de uma pauta
c = corpos.get("almg_reuniao_ccj", b"").decode("utf-8", "replace")
open("mg/teste/almg_reuniao_ccj.html", "w").write(c)
json.dump(res, open("mg/teste/resultado.json", "w"), ensure_ascii=False, indent=1)
