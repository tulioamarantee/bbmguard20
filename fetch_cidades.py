import sys, re, requests, xml.etree.ElementTree as ET
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
print(r.status_code)
print(r.text[:800])
