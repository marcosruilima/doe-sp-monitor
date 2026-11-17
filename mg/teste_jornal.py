import json, subprocess, os
H="www.jornalminasgerais.mg.gov.br"
out={}
def sh(c):
    p=subprocess.run(c,shell=True,capture_output=True,text=True,timeout=90); return (p.stdout+p.stderr)[-3000:]
out["cadeia_certificados"]=sh(f"echo | openssl s_client -connect {H}:443 -servername {H} -showcerts 2>&1 | grep -E 'depth|s:|i:|Verify|verify' | head -20")
out["curl_verificando"]=sh(f"curl -sS -m 30 -o /dev/null -w 'HTTP %{{http_code}}' https://{H}/api/v1/Jornal/ObterUltimaEdicaoECalendarioParaHome 2>&1")
os.makedirs("mg/teste",exist_ok=True)
json.dump(out,open("mg/teste/jornal.json","w"),ensure_ascii=False,indent=1)
print(json.dumps(out,ensure_ascii=False,indent=1))
