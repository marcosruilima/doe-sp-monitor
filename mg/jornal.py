"""Coleta o Diário do Executivo de Minas Gerais (Jornal Minas Gerais) via a API do próprio portal.
- Autentica como visitante público (POST vazio em Autenticacao/Autenticar), como faz o site.
- O servidor do portal envia o certificado intermediário errado; aqui baixamos o intermediário correto
  (endereço AIA publicado no certificado do site), conferimos que ele fecha a cadeia até uma raiz
  confiável e só então o usamos. A verificação de certificado permanece ligada.
"""
import base64, json, os, re, shutil, ssl, subprocess, sys, tempfile, urllib.request
from datetime import datetime, timezone, timedelta

H = "www.jornalminasgerais.mg.gov.br"
BASE = f"https://{H}/api/v1/"
SAIDA = "mg/jornal"
INTER = "mg/certs/intermediario_jornal_mg.pem"
DIAS = int(os.environ.get("DIAS", "10"))
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, **kw)

def garantir_intermediario():
    folha = ssl.get_server_certificate((H, 443))  # apenas lê o certificado público do servidor
    tmp = tempfile.mkdtemp()
    fpem = os.path.join(tmp, "folha.pem"); open(fpem, "w").write(folha)
    txt = sh(["openssl", "x509", "-in", fpem, "-noout", "-text"]).stdout
    m = re.search(r"CA Issuers - URI:(\S+)", txt)
    if not m:
        raise SystemExit("AIA do certificado não encontrado")
    url = m.group(1)
    dados = urllib.request.urlopen(url, timeout=30).read()
    try:
        inter_pem = ssl.DER_cert_to_PEM_cert(dados)
    except Exception:
        inter_pem = dados.decode()
    ipem = os.path.join(tmp, "inter.pem"); open(ipem, "w").write(inter_pem)
    v = sh(["openssl", "verify", "-untrusted", ipem, fpem])
    print("openssl verify:", (v.stdout + v.stderr).strip())
    if "OK" not in v.stdout:
        raise SystemExit("O intermediário baixado não fecha a cadeia até uma raiz confiável; abortando")
    os.makedirs(os.path.dirname(INTER), exist_ok=True)
    shutil.copy(ipem, INTER)
    print("Intermediário gravado em", INTER, "origem", url)

if not os.path.exists(INTER):
    garantir_intermediario()
ctx = ssl.create_default_context()
ctx.load_verify_locations(INTER)

def chamar(caminho, metodo="GET", token=None, corpo=None):
    h = {"User-Agent": UA, "Accept": "application/json"}
    if token: h["Authorization"] = f"Bearer {token}"
    dados = None
    if metodo == "POST":
        h["Content-Type"] = "application/json"; dados = json.dumps(corpo if corpo is not None else {}).encode()
    req = urllib.request.Request(BASE + caminho, data=dados, headers=h, method=metodo)
    with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
        return json.loads(r.read())

tok = chamar("Autenticacao/Autenticar", "POST")["dados"]
home = chamar("Jornal/ObterUltimaEdicaoECalendarioParaHome", token=tok)["dados"]
ed = home["edicoesCalendario"]
corte = (datetime.now(timezone(timedelta(hours=-3))) - timedelta(days=DIAS)).date()
os.makedirs(SAIDA, exist_ok=True)
status = {"coletado_em_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
          "ultima_edicao": home.get("dataPublicacaoUltimaEdicao"), "edicoes": [], "erros": []}
for e in ed:
    data = e["dataPublicacao"][:10]
    if datetime.fromisoformat(data).date() < corte:
        continue
    nome = f"{data}{'_extra' if e.get('edicaoExtra') and False else ''}"
    nome = f"{data}_id{e['idCadernoPrincipal']}"
    txtf = os.path.join(SAIDA, f"{nome}_executivo.txt")
    if os.path.exists(txtf):
        continue
    try:
        r = chamar(f"Jornal/ObterEdicaoPorId/{e['idCadernoPrincipal']}?pagina=1", token=tok)["dados"]
        pdfb = base64.b64decode(r["arquivoCadernoPrincipal"]["arquivo"])
        pdff = os.path.join(tempfile.gettempdir(), nome + ".pdf"); open(pdff, "wb").write(pdfb)
        p = sh(["pdftotext", pdff, txtf])
        sumario = {"data": data, "id": e["idCadernoPrincipal"], "extra": e.get("edicaoExtra"),
                   "cadernos": [{"descricao": c["descricao"], "secoes": c["secoes"]} for c in r["cadernos"]],
                   "chaves_resposta": [k for k in r.keys()]}
        json.dump(sumario, open(os.path.join(SAIDA, f"{nome}_sumario.json"), "w"), ensure_ascii=False, indent=1)
        status["edicoes"].append({"data": data, "id": e["idCadernoPrincipal"], "bytes_pdf": len(pdfb),
                                  "pdftotext_rc": p.returncode})
        print("OK", nome, len(pdfb))
    except Exception as ex:
        status["erros"].append({"data": data, "id": e["idCadernoPrincipal"], "erro": repr(ex)})
        print("ERRO", nome, repr(ex))
json.dump(status, open(os.path.join(SAIDA, "status.json"), "w"), ensure_ascii=False, indent=1)
sys.exit(1 if status["erros"] and not status["edicoes"] else 0)
