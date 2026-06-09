import sys, re, json, requests
import config
from soap_client import sgr_login, post_soap

chave = sgr_login()
body = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:tem="http://tempuri.org/"><soapenv:Header/><soapenv:Body>'
    '<tem:sgrListaCidades>'
    f'<tem:chaveacesso>{chave}</tem:chaveacesso>'
    f'<tem:cdpas>{config.CD_PAS}</tem:cdpas>'
    f'<tem:cdcliente>{config.CD_CLIENTE}</tem:cdcliente>'
    '</tem:sgrListaCidades>'
    '</soapenv:Body></soapenv:Envelope>'
)

headers = {"Content-Type":"text/xml;charset=utf-8", "SOAPAction":'"http://tempuri.org/sgrListaCidades"'}
r = requests.post(config.WS_URL, data=body.encode("utf-8"), headers=headers, timeout=30)
cidades = re.findall(r'<CDCID>(\d+)</CDCID>.*?<DSCIDADE>([^<]+)</DSCIDADE>.*?<SGUF>([^<]+)</SGUF>', r.text, re.DOTALL | re.IGNORECASE)
cidades_map = {}
for cd, nome, uf in cidades:
    cd = int(cd)
    nome = nome.strip().title()
    uf = uf.strip().upper()
    if uf not in cidades_map:
        cidades_map[uf] = {}
    cidades_map[uf][nome] = cd

with open("cidades_opentech.json", "w", encoding="utf-8") as f:
    json.dump(cidades_map, f, ensure_ascii=False, indent=2)
print("Salvo cidades_opentech.json com", sum(len(x) for x in cidades_map.values()), "cidades!")
