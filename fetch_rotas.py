import requests, re, json
import config
from soap_client import sgr_login

chave = sgr_login()
body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrRetornaRotasModelo>
      <tem:chaveAcesso>{chave}</tem:chaveAcesso>
      <tem:cdpas>{config.CD_PAS}</tem:cdpas>
      <tem:cdcliente>{config.CD_CLIENTE}</tem:cdcliente>
    </tem:sgrRetornaRotasModelo>
  </soapenv:Body>
</soapenv:Envelope>"""

print("Fetching routes...")
r = requests.post(config.WS_URL, data=body.encode('utf-8'), headers={"Content-Type": "text/xml;charset=utf-8", "SOAPAction": '"http://tempuri.org/sgrRetornaRotasModelo"'}, timeout=120)
print(r.status_code)
if r.status_code == 200:
    blocks = re.findall(r"<RotaModelo[^>]*>(.*?)</RotaModelo>", r.text, re.DOTALL)
    rotas = []
    for b in blocks:
        cd_rota = re.search(r"<cdRotaModelo>(.*?)</cdRotaModelo>", b)
        ds_rota = re.search(r"<dsRotaModelo>(.*?)</dsRotaModelo>", b)
        cd_orig = re.search(r"<cdCidOrigem>(.*?)</cdCidOrigem>", b)
        cd_dest = re.search(r"<cdCidDestino>(.*?)</cdCidDestino>", b)
        
        rotas.append({
            "cd_rota": int(cd_rota.group(1)) if cd_rota else 0,
            "ds_rota": ds_rota.group(1).strip() if ds_rota else "",
            "cd_cidade_origem": int(cd_orig.group(1)) if cd_orig else 0,
            "cd_cidade_destino": int(cd_dest.group(1)) if cd_dest else 0
        })
    with open("rotas_opentech.json", "w", encoding="utf-8") as f:
        json.dump(rotas, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(rotas)} routes!")
else:
    print(r.text[:500])
