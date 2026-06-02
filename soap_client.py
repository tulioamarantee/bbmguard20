import requests
import xml.etree.ElementTree as ET
import re
import logging
from datetime import datetime
from config import WS_URL, WS_USUARIO, WS_SENHA, WS_DOMINIO, CD_PAS, CD_CLIENTE, get_status_label

logger = logging.getLogger("soap_client")

def post_soap(action, body):
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"http://tempuri.org/{action}"'
    }
    try:
        r = requests.post(WS_URL, data=body.encode("utf-8"), headers=headers, timeout=20)
        r.raise_for_status()
        return r.text
    except Exception as e:
        logger.error(f"Erro na chamada SOAP {action}: {e}")
        return None

def find_text(xml_string, tag, parent_tag=None):
    if not xml_string:
        return None
    try:
        if parent_tag:
            # Encontra o bloco do nó pai tolerando atributos na tag (ex: <ConsultaVeiculoResponse diffgr:id="ConsultaVeiculoResponse1">)
            parent_match = re.search(r"<%s\b[^>]*>(.*?)</%s>" % (parent_tag, parent_tag), xml_string, re.DOTALL)
            if parent_match:
                block = parent_match.group(1)
                match = re.search(f"<{tag}>(.*?)</{tag}>", block, re.DOTALL)
                return match.group(1) if match else None
            return None
        # Busca normal
        match = re.search(f"<{tag}>(.*?)</{tag}>", xml_string, re.DOTALL)
        return match.group(1) if match else None
    except Exception:
        return None

def sgr_login():
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrLogin>
      <tem:usuario>{WS_USUARIO}</tem:usuario>
      <tem:senha>{WS_SENHA}</tem:senha>
      <tem:dominio>{WS_DOMINIO}</tem:dominio>
    </tem:sgrLogin>
  </soapenv:Body>
</soapenv:Envelope>"""
    
    resp = post_soap("sgrLogin", body)
    return find_text(resp, "ReturnKey")

def consultar_motorista(cpf):
    """
    Consulta o status do motorista na OpenTech via sgrConsultaPFV3.
    Retorna um dicionário com nome, status_original, status_label e data_expiracao.
    """
    chave = sgr_login()
    if not chave:
        return {"error": "Falha na autenticação com OpenTech"}

    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrConsultaPFV3>
      <tem:chaveacesso>{chave}</tem:chaveacesso>
      <tem:cdpas>{CD_PAS}</tem:cdpas>
      <tem:cdcliente>{CD_CLIENTE}</tem:cdcliente>
      <tem:cdpaisorigem>1</tem:cdpaisorigem>
      <tem:nrdocumento>{cpf_limpo}</tem:nrdocumento>
      <tem:cdOrigemConsulta>1</tem:cdOrigemConsulta>
    </tem:sgrConsultaPFV3>
  </soapenv:Body>
</soapenv:Envelope>"""

    resp = post_soap("sgrConsultaPFV3", body)
    if not resp:
        return {"error": "Sem resposta da OpenTech"}

    return_id = find_text(resp, "ReturnID")
    if return_id != "0":
        desc = find_text(resp, "ReturnDescription")
        return {"error": desc or f"Erro ID {return_id}"}

    # Extração de dados do diffgram
    nome = find_text(resp, "DSNOME")
    status_cod = find_text(resp, "FLSITPF")
    status_desc = find_text(resp, "DSSITUACAO")
    expira = find_text(resp, "DTEXPIRACAO")
    cnh = find_text(resp, "NRCNH") or find_text(resp, "CNH") # Campos variam dependendo da versão
    cat = find_text(resp, "CDCATCNH") or find_text(resp, "DSCATCNH")

    return {
        "nome": nome,
        "status_cod": status_cod,
        "status_label": status_desc if status_desc else get_status_label(status_cod),
        "data_expiracao": expira,
        "cnh": cnh,
        "categoria": cat,
        "raw_status": status_desc
    }

# Mapeamento de empresas de rastreamento (ID para Nome)
TRACKER_MAP = {
    "2578438": "3S",
    "696234": "AUTOTRAC",
    "75657": "CONTROL LOC",
    "37206": "OMNILINK",
    "17803": "ONIXSAT",
    "164048": "SASCAR",
    "580314": "SIGHRA",
    "3779907": "T4S"
}

def consultar_veiculo(placa):
    """
    Consulta real do veículo na OpenTech usando sgrListaInformacoesVeiculo e sgrRetornaUltimaPosicaoVeiculo.
    Consulta real do veículo na OpenTech usando sgrRetornaVeicV2 e sgrRetornaUltimaPosicaoVeiculo.
    Retorna o status SIL, validade, última posição e checklist.
    """
    chave = sgr_login()
    if not chave:
        return {"error": "Falha na autenticação com OpenTech"}

    placa_limpa = placa.upper().replace("-", "").strip()
    
    # Chamada 1: Informações base do veículo e Rastreadores (sgrRetornaVeicV2)
    body_info = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrRetornaVeicV2>
      <tem:chaveacesso>{chave}</tem:chaveacesso>
      <tem:cdcliente>{CD_CLIENTE}</tem:cdcliente>
      <tem:cdpas>{CD_PAS}</tem:cdpas>
      <tem:cdPaisOrigem>1</tem:cdPaisOrigem>
      <tem:nrplaca>{placa_limpa}</tem:nrplaca>
    </tem:sgrRetornaVeicV2>
  </soapenv:Body>
</soapenv:Envelope>"""
    resp_info = post_soap("sgrRetornaVeicV2", body_info)
    
    # Chamada 2: Dados Consolidados do Motorista/Veículo (sgrConsultarMotoristaVeiculos)
    # Traz a data da Última Posição, Data de Expiração SIL e Status SIL
    body_mot_veic = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrConsultarMotoristaVeiculos>
      <tem:chaveacesso>{chave}</tem:chaveacesso>
      <tem:cdpas>{CD_PAS}</tem:cdpas>
      <tem:cdcliente>{CD_CLIENTE}</tem:cdcliente>
      <tem:cdPaisoOrigemMot>1</tem:cdPaisoOrigemMot>
      <tem:cpfMot>00000000000</tem:cpfMot>
      <tem:cdpaisorigemplaca1>1</tem:cdpaisorigemplaca1>
      <tem:nrplaca1>{placa_limpa}</tem:nrplaca1>
      <tem:cdpaisorigemplaca2>0</tem:cdpaisorigemplaca2>
      <tem:nrplaca2></tem:nrplaca2>
      <tem:cdpaisorigemplaca3>0</tem:cdpaisorigemplaca3>
      <tem:nrplaca3></tem:nrplaca3>
    </tem:sgrConsultarMotoristaVeiculos>
  </soapenv:Body>
</soapenv:Envelope>"""
    resp_mot_veic = post_soap("sgrConsultarMotoristaVeiculos", body_mot_veic)
    
    # Chamada 3: Consulta do CheckList (sgrCheckListConsulta)
    body_checklist = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrCheckListConsulta>
      <tem:chaveacesso>{chave}</tem:chaveacesso>
      <tem:nrplaca>{placa_limpa}</tem:nrplaca>
      <tem:cdcli>{CD_CLIENTE}</tem:cdcli>
      <tem:cdpas>{CD_PAS}</tem:cdpas>
      <tem:cdSolicCheckList>0</tem:cdSolicCheckList>
    </tem:sgrCheckListConsulta>
  </soapenv:Body>
</soapenv:Envelope>"""
    resp_checklist = post_soap("sgrCheckListConsulta", body_checklist)
    
    return_id = find_text(resp_info, "ReturnID")
    if return_id != "0":
        desc = find_text(resp_info, "ReturnDescription")
        return {"error": desc or f"Erro ID {return_id}"}
        
    # Extração de dados da Info Básica (Rastreadores)
    rastreadores = []
    segundo_rastreador = "Não possui"
    
    import re
    m1 = re.search(r"<CDEMPRASTREA>(.*?)</CDEMPRASTREA>", resp_info, re.IGNORECASE)
    m2 = re.search(r"<CDEMPRASTREA2>(.*?)</CDEMPRASTREA2>", resp_info, re.IGNORECASE)
    
    cd_emp1 = m1.group(1).strip() if m1 else None
    cd_emp2 = m2.group(1).strip() if m2 else None
    
    if cd_emp1 and cd_emp1 != "0":
        nome_principal = TRACKER_MAP.get(cd_emp1, f"ID {cd_emp1}")
        rastreadores.append(nome_principal)
        
    if cd_emp2 and cd_emp2 not in ["0", "00", ""]:
        nome_secundario = TRACKER_MAP.get(cd_emp2, f"ID {cd_emp2}")
        rastreadores.append(nome_secundario)
        if nome_secundario in ["T4S", "3S"] or any(t in nome_secundario.upper() for t in ["T4S", "3S"]):
            segundo_rastreador = nome_secundario
            
    if not rastreadores:
        rastreadores = ["N/I"]
        
    # Extração do ConsultarMotoristaVeiculos (especificando ConsultaVeiculoResponse)
    tipo_veiculo = find_text(resp_mot_veic, "DSTPVEIC", parent_tag="ConsultaVeiculoResponse") or "N/I"
    status_desc = find_text(resp_mot_veic, "DSSITUACAO", parent_tag="ConsultaVeiculoResponse") or "Liberado"
    status_cod = find_text(resp_mot_veic, "FLSITVEIC", parent_tag="ConsultaVeiculoResponse") or "N/I"
    expira_raw = find_text(resp_mot_veic, "DTEXPIRACAO", parent_tag="ConsultaVeiculoResponse")
    
    expira = "N/I"
    if expira_raw:
        try:
            dt_obj = datetime.strptime(expira_raw[:19], "%Y-%m-%dT%H:%M:%S")
            expira = dt_obj.strftime("%d/%m/%Y %H:%M:%S")
        except:
            expira = expira_raw
            
    # Última posição
    ultima_posicao = "N/I"
    pos_raw = find_text(resp_mot_veic, "DTULTPOS", parent_tag="ConsultaVeiculoResponse")
    if pos_raw:
        try:
            dt_pos = datetime.strptime(pos_raw[:19], "%Y-%m-%dT%H:%M:%S")
            ultima_posicao = dt_pos.strftime("%d/%m/%Y %H:%M:%S")
        except:
            ultima_posicao = pos_raw
            
    # Extração do CheckList
    checklist = "N/I"
    if find_text(resp_checklist, "ReturnID") == "0":
        sit_check = find_text(resp_checklist, "Situacao")
        exp_check_raw = find_text(resp_checklist, "DataExpiracao")
        if sit_check and exp_check_raw:
            checklist = f"{sit_check} (Até {exp_check_raw})"
        elif sit_check:
            checklist = sit_check

    return {
        "placa": placa_limpa,
        "tipo_veiculo": tipo_veiculo,
        "status_cod": status_cod,
        "status_label": status_desc,
        "data_expiracao": expira,
        "ultima_posicao": ultima_posicao,
        "checklist": checklist,
        "rastreadores": ", ".join(rastreadores),
        "segundo_rastreador": segundo_rastreador
    }
