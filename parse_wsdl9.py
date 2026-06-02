import re

with open("wsdl.xml", "r", encoding="utf-8") as f:
    wsdl = f.read()

ops = ["sgrRelInstRastreamento"]
for op in ops:
    print(f"\n--- Estrutura para {op} ---")
    match = re.search(f'<s:element name="{op}">(.*?)</s:element>', wsdl, re.DOTALL | re.IGNORECASE)
    if match:
        content = match.group(1)
        elements = re.findall(r'<s:element minOccurs=".*?" maxOccurs=".*?" name="(.*?)" type="(.*?)" />', content)
        for name, t in elements:
            print(f"  {name} ({t})")
