import requests
from xml.etree import ElementTree as ET

url = "https://ws.opentechgr.com.br/sgrOpentech/sgropentech.asmx?WSDL"

print("Baixando WSDL...")
response = requests.get(url)
wsdl = response.text

print("Salvando wsdl.xml...")
with open("wsdl.xml", "w", encoding="utf-8") as f:
    f.write(wsdl)

print("Operações contendo 'Veiculo', 'Placa', 'Auto' ou 'Carreta':")
# WSDL parsing is complex because of namespaces, but we can just use regex on the raw text
import re
operations = re.findall(r'<wsdl:operation name="(.*?)"', wsdl)
for op in set(operations):
    op_lower = op.lower()
    if 'veiculo' in op_lower or 'placa' in op_lower or 'auto' in op_lower or 'carreta' in op_lower or 'frota' in op_lower:
        print("-", op)
