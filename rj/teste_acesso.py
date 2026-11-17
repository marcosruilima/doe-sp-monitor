import ssl, urllib.request, pathlib, json, re
URLS = {
 "plenario_ordemdodia": "https://www2.alerj.rj.gov.br/ordemdodia/",
 "comissoes_editais": "https://www3.alerj.rj.gov.br/lotus_notes/default.asp?id=66",
 "noticias": "https://www.alerj.rj.gov.br/Comunicacao/SalaDeImprensa/Noticias",
 "odia": "https://odia.ig.com.br/rio-de-janeiro",
 "oglobo_rio": "https://oglobo.globo.com/rio/",
 "extra_politica": "https://extra.globo.com/politica/",
 "extra_rio": "https://extra.globo.com/rio/",
}
out = pathlib.Path("rj/teste"); out.mkdir(parents=True, exist_ok=True)
res = {}
for k, u in URLS.items():
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=40) as r:
            b = r.read()
            (out / f"{k}.html").write_bytes(b)
            res[k] = {"status": r.status, "bytes": len(b), "final_url": r.geturl()}
    except Exception as e:
        res[k] = {"erro": repr(e)[:300]}
(out / "resultado.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
print(json.dumps(res, indent=1, ensure_ascii=False))
