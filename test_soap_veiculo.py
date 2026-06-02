import requests
import re
from config import WS_URL, WS_USUARIO, WS_SENHA, WS_DOMINIO, CD_PAS, CD_CLIENTE

def post_soap(action, body):
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"http://tempuri.org/{action}"'
    }
    r = requests.post(WS_URL, data=body.encode("utf-8"), headers=headers, timeout=30)
    return r.text

def sgr_login():
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/"><soapenv:Header/><soapenv:Body><tem:sgrLogin><tem:usuario>{WS_USUARIO}</tem:usuario><tem:senha>{WS_SENHA}</tem:senha><tem:dominio>{WS_DOMINIO}</tem:dominio></tem:sgrLogin></soapenv:Body></soapenv:Envelope>"""
    r = requests.post(WS_URL, data=body.encode("utf-8"), headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"http://tempuri.org/sgrLogin"'})
    match = re.search(r"<ReturnKey>(.*?)</ReturnKey>", r.text)
    return match.group(1) if match else None

# Verifica os parametros de sgrListaAcessoriosVeiculo
with open("wsdl.xml", "r", encoding="utf-8") as f:
    wsdl = f.read()

print("=== Estrutura para sgrListaAcessoriosVeiculo ===")
match = re.search(r'<s:element name="sgrListaAcessoriosVeiculo">(.*?)</s:element>', wsdl, re.DOTALL)
if match:
    elements = re.findall(r'<s:element minOccurs=".*?" maxOccurs=".*?" name="(.*?)" type="(.*?)" />', match.group(1))
    for name, t in elements:
        print(f"  {name} ({t})")

chave = sgr_login()
placa = "SJG4G96"

# Tenta com cdpas=0 e cdcli=0 (sem filtro)
print("\n=== sgrListaAcessoriosVeiculo (cdpas=0, cdcli=0) ===")
body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrListaAcessoriosVeiculo>
      <tem:chaveacesso>{chave}</tem:chaveacesso>
      <tem:nrPlaca>{placa}</tem:nrPlaca>
      <tem:cdcli>0</tem:cdcli>
      <tem:cdpas>0</tem:cdpas>
    </tem:sgrListaAcessoriosVeiculo>
  </soapenv:Body>
</soapenv:Envelope>"""
resp = post_soap("sgrListaAcessoriosVeiculo", body)
print(resp[:600])

# Tenta sgrAdicionarIsca passando o ID do veículo (1464712 - descoberto anteriormente)
print("\n=== sgrAdicionarIsca com cdveic=1464712 ===")
with open("wsdl.xml", "r", encoding="utf-8") as f:
    wsdl = f.read()
m = re.search(r'<s:element name="sgrAdicionarIsca">(.*?)</s:element>', wsdl, re.DOTALL)
if m:
    els = re.findall(r'<s:element minOccurs=".*?" maxOccurs=".*?" name="(.*?)" type="(.*?)" />', m.group(1))
    for n, t in els:
        print(f"  {n} ({t})")

# Tenta sgrRetornaDataUltimaPosicaoVeiculoV2 com CD correto
print("\n=== sgrRetornaDataUltimaPosicaoVeiculoV2 params ===")
m2 = re.search(r'<s:element name="sgrRetornaDataUltimaPosicaoVeiculoV2">(.*?)</s:element>', wsdl, re.DOTALL)
if m2:
    els2 = re.findall(r'<s:element minOccurs=".*?" maxOccurs=".*?" name="(.*?)" type="(.*?)" />', m2.group(1))
    for n, t in els2:
        print(f"  {n} ({t})")

body_v2 = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrRetornaDataUltimaPosicaoVeiculoV2>
      <tem:chaveacesso>{chave}</tem:chaveacesso>
      <tem:cdpas>{CD_PAS}</tem:cdpas>
      <tem:nrplaca>{placa}</tem:nrplaca>
    </tem:sgrRetornaDataUltimaPosicaoVeiculoV2>
  </soapenv:Body>
</soapenv:Envelope>"""
resp_v2 = post_soap("sgrRetornaDataUltimaPosicaoVeiculoV2", body_v2)
print("Resp V2:", resp_v2[:400])
