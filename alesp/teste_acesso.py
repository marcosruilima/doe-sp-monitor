"""Teste: o GitHub Actions alcança a API da Alesp? Grava status e amostras em alesp/teste/."""
import json, os, sys, urllib.request, urllib.error, urllib.parse, datetime, socket

BASE = "https://legis-api-portal-prd.al.sp.gov.br"
hoje = datetime.date.today()
ini = (hoje - datetime.timedelta(days=1)).isoformat()
fim = (hoje + datetime.timedelta(days=7)).isoformat()

TESTES = {
    "reunioes": "/colegiado/reunioes?" + urllib.parse.urlencode({
        "page": 0, "size": 100, "dataInicio": ini, "dataFim": fim,
        "pesquisarAtas": "false", "pesquisarConjuntas": "false"}),
    "sessoes": "/sessoes-plenarias/consulta?" + urllib.parse.urlencode({
        "page": 0, "size": 20, "dataInicial": ini, "dataFinal": fim}),
    "legislaturas": "/legislaturas/todos",
}
HEADERS = {
    "sem_origem": {"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    "com_origem": {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
                   "Origin": "https://www.al.sp.gov.br", "Referer": "https://www.al.sp.gov.br/"},
}
os.makedirs("alesp/teste", exist_ok=True)
resumo = {"data": hoje.isoformat(), "janela": [ini, fim], "resultados": []}

try:
    socket.getaddrinfo("legis-api-portal-prd.al.sp.gov.br", 443)
    resumo["dns"] = "ok"
except Exception as e:
    resumo["dns"] = f"erro: {e}"

for nome, caminho in TESTES.items():
    for hnome, h in HEADERS.items():
        r = {"teste": nome, "headers": hnome, "url": BASE + caminho}
        try:
            req = urllib.request.Request(BASE + caminho, headers=h)
            with urllib.request.urlopen(req, timeout=30) as resp:
                corpo = resp.read()
                r["status"] = resp.status
                r["bytes"] = len(corpo)
                r["content_type"] = resp.headers.get("Content-Type")
                with open(f"alesp/teste/{nome}_{hnome}.json", "wb") as f:
                    f.write(corpo[:200000])
        except urllib.error.HTTPError as e:
            r["status"] = e.code
            r["erro"] = e.read()[:300].decode("utf-8", "ignore")
        except Exception as e:
            r["erro"] = f"{type(e).__name__}: {e}"
        print(json.dumps(r, ensure_ascii=False))
        resumo["resultados"].append(r)

with open("alesp/teste/resumo.json", "w", encoding="utf-8") as f:
    json.dump(resumo, f, ensure_ascii=False, indent=2)
ok = any(r.get("status") == 200 for r in resumo["resultados"])
print("ALCANCOU A API:", ok)
sys.exit(0)
