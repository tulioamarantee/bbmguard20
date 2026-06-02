import requests
import re
from datetime import datetime, timedelta
from config import WS_URL, WS_USUARIO, WS_SENHA, WS_DOMINIO, CD_PAS, CD_CLIENTE

def post_soap(action, body):
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"http://tempuri.org/{action}"'
    }
    r = requests.post(WS_URL, data=body.encode("utf-8"), headers=headers, timeout=20)
    return r.text

def sgr_login():
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/"><soapenv:Header/><soapenv:Body><tem:sgrLogin><tem:usuario>{WS_USUARIO}</tem:usuario><tem:senha>{WS_SENHA}</tem:senha><tem:dominio>{WS_DOMINIO}</tem:dominio></tem:sgrLogin></soapenv:Body></soapenv:Envelope>"""
    r = requests.post(WS_URL, data=body.encode("utf-8"), headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"http://tempuri.org/sgrLogin"'})
    match = re.search(r"<ReturnKey>(.*?)</ReturnKey>", r.text)
    return match.group(1) if match else None

chave = sgr_login()
placa = "SJG4G96"

# Test sgrRetornaPosicaoVeiculo
print("\n=== sgrRetornaPosicaoVeiculo ===")
# Pass the exact date or the current date minus a few hours
dt = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%S")
body_pos = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/><soapenv:Body><tem:sgrRetornaPosicaoVeiculo><tem:chaveacesso>{chave}</tem:chaveacesso><tem:cdpas>{CD_PAS}</tem:cdpas><tem:cdcliente>{CD_CLIENTE}</tem:cdcliente><tem:data>{dt}</tem:data><tem:nrplaca>{placa}</tem:nrplaca></tem:sgrRetornaPosicaoVeiculo></soapenv:Body></soapenv:Envelope>"""
print(post_soap("sgrRetornaPosicaoVeiculo", body_pos)[:500])

# What if we just call sgrRetornaDataUltimaPosicaoVeiculo?
print("\n=== sgrRetornaDataUltimaPosicaoVeiculo ===")
body_dt = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/><soapenv:Body><tem:sgrRetornaDataUltimaPosicaoVeiculo><tem:chaveacesso>{chave}</tem:chaveacesso><tem:nrplaca>{placa}</tem:nrplaca></tem:sgrRetornaDataUltimaPosicaoVeiculo></soapenv:Body></soapenv:Envelope>"""
print(post_soap("sgrRetornaDataUltimaPosicaoVeiculo", body_dt)[:500])

# What about check list and tracker?
print("\n=== sgrListaInformacoesVeiculo (revisit) ===")
body_info = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/><soapenv:Body><tem:sgrListaInformacoesVeiculo><tem:chaveacesso>{chave}</tem:chaveacesso><tem:strPlaca>{placa}</tem:strPlaca></tem:sgrListaInformacoesVeiculo></soapenv:Body></soapenv:Envelope>"""
print(post_soap("sgrListaInformacoesVeiculo", body_info))
