import xml.etree.ElementTree as ET
import re

with open("wsdl.xml", "r", encoding="utf-8") as f:
    wsdl = f.read()

# We can just extract the element definitions for the requests
ops = ["sgrListaInformacoesVeiculo", "sgrCheckListStatusVeiculos", "sgrRetornaUltimaPosicaoVeiculo", "sgrConsultarMotoristaVeiculos"]

for op in ops:
    print(f"\n--- Estrutura para {op} ---")
    # find <s:element name="op">
    # get the inner text until </s:element>
    match = re.search(f'<s:element name="{op}">(.*?)</s:element>', wsdl, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1)
        elements = re.findall(r'<s:element minOccurs=".*?" maxOccurs=".*?" name="(.*?)" type="(.*?)" />', content)
        for name, t in elements:
            print(f"  {name} ({t})")
    else:
        print("  Não encontrado.")
