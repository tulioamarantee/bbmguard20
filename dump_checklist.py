import requests
from config import WS_URL, WS_USUARIO, WS_SENHA, WS_DOMINIO, CD_PAS, CD_CLIENTE
import re

def sgr_login():
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/"><soapenv:Header/><soapenv:Body><tem:sgrLogin><tem:usuario>{WS_USUARIO}</tem:usuario><tem:senha>{WS_SENHA}</tem:senha><tem:dominio>{WS_DOMINIO}</tem:dominio></tem:sgrLogin></soapenv:Body></soapenv:Envelope>"""
    r = requests.post(WS_URL, data=body.encode("utf-8"), headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"http://tempuri.org/sgrLogin"'})
    match = re.search(r"<ReturnKey>(.*?)</ReturnKey>", r.text)
    return match.group(1) if match else None

chave = sgr_login()
body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/><soapenv:Body><tem:sgrCheckListStatusVeiculos><tem:chaveacesso>{chave}</tem:chaveacesso><tem:cdcli>{CD_CLIENTE}</tem:cdcli><tem:cdpas>{CD_PAS}</tem:cdpas></tem:sgrCheckListStatusVeiculos></soapenv:Body></soapenv:Envelope>"""
r = requests.post(WS_URL, data=body.encode("utf-8"), headers={"Content-Type": "text/xml; charset=utf-8", "SOAPAction": '"http://tempuri.org/sgrCheckListStatusVeiculos"'})
with open("checklist.xml", "w", encoding="utf-8") as f:
    f.write(r.text)
print("Salvo em checklist.xml")
