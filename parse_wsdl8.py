import re

with open("wsdl.xml", "r", encoding="utf-8") as f:
    wsdl = f.read()

ops = re.findall(r'<wsdl:operation name="(.*?)"', wsdl)
for op in set(ops):
    op_lower = op.lower()
    if 'tecnologia' in op_lower or 'rastre' in op_lower or 'secundari' in op_lower or 'autoriz' in op_lower:
        print("-", op)
