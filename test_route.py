import config
from soap_client import sgr_login, post_soap

chave = sgr_login()
body = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"'
    ' xmlns:tem="http://tempuri.org/"><soapenv:Header/><soapenv:Body>'
    '<tem:sgrListaRotas>'
    f'<tem:chaveacesso>{chave}</tem:chaveacesso>'
    f'<tem:cdpas>{config.CD_PAS}</tem:cdpas>'
    f'<tem:cdcliente>{config.CD_CLIENTE}</tem:cdcliente>'
    '</tem:sgrListaRotas>'
    '</soapenv:Body></soapenv:Envelope>'
)

r = post_soap("sgrListaRotas", body)
print("Response:", r[:600])
