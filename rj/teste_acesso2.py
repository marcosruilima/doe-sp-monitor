import urllib.request, base64, pathlib, re, json
out = pathlib.Path("rj/teste"); out.mkdir(exist_ok=True, parents=True)
def get(u, name):
    try:
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read(); (out/name).write_bytes(b); return len(b)
    except Exception as e:
        return repr(e)[:200]
res = {}
base = "https://www3.alerj.rj.gov.br/lotus_notes/default.asp?id=66&url="
for nome, path in {
 "ed_expand": "/compcom.nsf/EditalInt?OpenForm&Start=1&Count=500&Expand=1",
 "ed_start1_count1000": "/compcom.nsf/EditalInt?OpenForm&Start=1&Count=1000",
 "ed_expandall": "/compcom.nsf/EditalInt?OpenForm&ExpandView",
}.items():
    res[nome] = get(base + base64.b64encode(path.encode()).decode(), nome + ".html")
res["pauta59"] = get("http://www3.alerj.rj.gov.br/lotus_notes/default.asp?id=59", "pauta59.html")
o = (out/"plenario_ordemdodia.html").read_text(encoding="utf-8", errors="ignore")
for s in re.findall(r'src="(scripts/[^"]+)"', o):
    if "services" in s or "javascript" in s or "ordem" in s.lower():
        res[s] = get("https://www2.alerj.rj.gov.br/ordemdodia/" + s, s.replace("/", "_"))
res["default_aspx"] = get("https://www2.alerj.rj.gov.br/ordemdodia/Default.aspx", "ordem_default.html")
(out/"resultado2.json").write_text(json.dumps(res, indent=1))
print(res)
