import re

with open("wsdl.xml", "r", encoding="utf-8") as f:
    wsdl = f.read()

ops = re.findall(r'<wsdl:operation name="(.*?)"', wsdl)
for op in set(ops):
    if 'isca' in op.lower() or 'secund' in op.lower() or 'rastre' in op.lower():
        print("-", op)
