import requests
import xml.etree.ElementTree as ET
import re
import logging
from datetime import datetime
from config import WS_URL, WS_USUARIO, WS_SENHA, WS_DOMINIO, CD_PAS, CD_CLIENTE, get_status_label
import json

logger = logging.getLogger("soap_client")

def post_soap(action, body):
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"http://tempuri.org/{action}"'
    }
    import os
    os.makedirs("scratch", exist_ok=True)
    with open(f"scratch/soap_body_debug_{action}.xml", "w", encoding="utf-8") as f:
        f.write(body)
    try:
        r = requests.post(WS_URL, data=body.encode("utf-8"), headers=headers, timeout=60)
        with open("scratch/soap_debug.log", "w", encoding="utf-8") as f:
            f.write(r.text)
        r.raise_for_status()
        if not r.text:
            import os
        os.makedirs("scratch", exist_ok=True)
        with open("scratch/soap_error.txt", "a", encoding="utf-8") as f:
                f.write(f"Vazio para {action}. Status: {r.status_code}\n")
        return r.text
    except Exception as e:
        import os
        os.makedirs("scratch", exist_ok=True)
        try:
            with open("scratch/soap_error.txt", "a", encoding="utf-8") as f:
                f.write(f"ERRO SOAPSGR {action}: {e}\n")
                if hasattr(e, 'response') and e.response is not None:
                    f.write(f"Response: {e.response.text}\n")
        except:
            pass
        print(f"ERRO SOAPSGR {action}: {e}")
        logger.error(f"Erro na chamada SOAP {action}: {e}")
        return None

def find_text(xml_string, tag, parent_tag=None):
    if not xml_string:
        return None
    try:
        if parent_tag:
            parent_match = re.search(r"<%s\b[^>]*>(.*?)</%s>" % (parent_tag, parent_tag), xml_string, re.DOTALL | re.IGNORECASE)
            if parent_match:
                block = parent_match.group(1)
                match = re.search(r"<%s\b[^>]*>(.*?)</%s>" % (tag, tag), block, re.DOTALL | re.IGNORECASE)
                return match.group(1) if match else None
            return None
        match = re.search(r"<%s\b[^>]*>(.*?)</%s>" % (tag, tag), xml_string, re.DOTALL | re.IGNORECASE)
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

def adicionar_programacao(dados):
    """
    Adiciona uma programação na OpenTech via sgrAdicionarProgramacao.
    Retorna o cdProgramacao gerado ou dicionário com erro.
    """
    chave = sgr_login()
    if not chave:
        return {"error": "Falha na autenticação com OpenTech"}

    # Valores default
    cnpj_padrao = "21930065000106"
    cnpj_transp = ''.join(filter(str.isdigit, str(dados.get("cnpj_transp") or cnpj_padrao)))
    if not cnpj_transp: cnpj_transp = cnpj_padrao
    
    cnpj_origem = ''.join(filter(str.isdigit, str(dados.get("cnpj_origem") or cnpj_transp)))
    if not cnpj_origem: cnpj_origem = cnpj_transp
    
    cnpj_destino = ''.join(filter(str.isdigit, str(dados.get("cnpj_destino") or cnpj_transp)))
    if not cnpj_destino: cnpj_destino = cnpj_transp
    
    nome_destino = dados.get("nome_destino") or "Destino Padrão"
    cd_cidade_destino = dados.get("cd_cidade_destino") or 9999
    
    # Gerar um nrProgramacao único (ex: 202403121530) se não fornecido
    import time
    nr_programacao = dados.get("nr_programacao") or time.strftime("%Y%m%d%H%M")
    cd_produto = dados.get("cd_produto") or 4546
    
    dt_prev_inicio = dados.get("dt_prev_inicio") or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    dt_prev_fim = dados.get("dt_prev_fim") or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    dt_prev_chegada = dados.get("dt_prev_chegada") or dt_prev_fim
    dt_confirmacao = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    try:
        valor_carga = int(float(str(dados.get("valor_carga") or "1000").replace(',', '.')))
    except ValueError:
        valor_carga = 1000
        
    try:
        peso = int(float(str(dados.get("peso") or "1000").replace(',', '.')))
    except ValueError:
        peso = 1000

    try:
        volume = int(float(str(dados.get("volume") or "1").replace(',', '.')))
    except ValueError:
        volume = 1
    cd_tipo_veiculo = dados.get("cd_tipo_veiculo") or 1

    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:sgrAdicionarProgramacao>
         <tem:chaveacesso>{chave}</tem:chaveacesso>
         <tem:cdpas>{CD_PAS}</tem:cdpas>
         <tem:cdcliente>{CD_CLIENTE}</tem:cdcliente>
         <tem:programacao>
            <tem:destinatarios>
               <tem:DestinatarioProgramacao>
                  <tem:cdProgramacao>0</tem:cdProgramacao>
                  <tem:cdProgramacaoDestinatario>0</tem:cdProgramacaoDestinatario>
                  <tem:cdTipoOperacaoProgramacao>1</tem:cdTipoOperacaoProgramacao>
                  <tem:nrCGCCPFLocalDescarga>{cnpj_destino}</tem:nrCGCCPFLocalDescarga>
                  <tem:dsCliDestino>{nome_destino}</tem:dsCliDestino>
                  <tem:cdCidDestino>{cd_cidade_destino}</tem:cdCidDestino>
                  <tem:dtPrevChegada>{dt_prev_chegada}</tem:dtPrevChegada>
                  <tem:cdProdutoDestinatario>{cd_produto}</tem:cdProdutoDestinatario>
                  <tem:vlProdutoDestinatario>{int(valor_carga)}</tem:vlProdutoDestinatario>
                  <tem:vlCubagem>0</tem:vlCubagem>
                  <tem:vlPeso>{int(peso)}</tem:vlPeso>
                  <tem:vlVolume>{int(volume)}</tem:vlVolume>
                  <tem:vlQtd>1</tem:vlQtd>
                  <tem:cdCli>{CD_CLIENTE}</tem:cdCli>
                  <tem:flTrocaNota>0</tem:flTrocaNota>
                  <tem:dtPrevSaida>{dt_prev_inicio}</tem:dtPrevSaida>
               </tem:DestinatarioProgramacao>
            </tem:destinatarios>
            <tem:cdProgramacao>0</tem:cdProgramacao>
            <tem:nrProgramacao>{nr_programacao}</tem:nrProgramacao>
            <tem:cdProduto>{cd_produto}</tem:cdProduto>
            <tem:vlPeso>{int(peso)}</tem:vlPeso>
            <tem:vlCubagem>0</tem:vlCubagem>
            <tem:vlVolume>{int(volume)}</tem:vlVolume>
            <tem:cdTipoCarga>1</tem:cdTipoCarga>
            <tem:cdTipoAcondicionamento>1</tem:cdTipoAcondicionamento>
            <tem:nrCGCCPFLocalCarregamento>{cnpj_origem}</tem:nrCGCCPFLocalCarregamento>
            <tem:dtPrevIniCarreg>{dt_prev_inicio}</tem:dtPrevIniCarreg>
            <tem:dtPrevFimCarreg>{dt_prev_fim}</tem:dtPrevFimCarreg>
            <tem:cdTipoProgramacao>1</tem:cdTipoProgramacao>
            <tem:cdTipoServico>1</tem:cdTipoServico>
            <tem:dtConfirmacao>{dt_confirmacao}</tem:dtConfirmacao>
            <tem:nrCGCCPFTransp>{cnpj_transp}</tem:nrCGCCPFTransp>
            <tem:cdTipoVeic>{cd_tipo_veiculo}</tem:cdTipoVeic>
            <tem:cdTipoCarroceria>1</tem:cdTipoCarroceria>
            <tem:cdGrupoTransp>1</tem:cdGrupoTransp>
            <tem:cdCli>{CD_CLIENTE}</tem:cdCli>
            <tem:nrCGCCPFEmbarcador>{cnpj_origem}</tem:nrCGCCPFEmbarcador>
         </tem:programacao>
      </tem:sgrAdicionarProgramacao>
   </soapenv:Body>
</soapenv:Envelope>"""

    resp = post_soap("sgrAdicionarProgramacao", body)
    if not resp:
        return {"error": "Sem resposta da OpenTech ao criar Programação"}

    return_id = find_text(resp, "ReturnID")
    if return_id != "0":
        with open("scratch/soap_response.xml", "w", encoding="utf-8") as f:
            f.write(resp)
        desc = find_text(resp, "ReturnDescription")
        
        # Extrair detalhes dos erros se houverem no diffgram
        import re
        descricoes = re.findall(r'<descricao[^>]*>(.*?)</descricao>', resp)
        if descricoes:
            desc = (desc or "Erros: ") + "\n- " + "\n- ".join(descricoes)
            
        return {"error": desc or f"Erro ID {return_id}"}

    # Geralmente a chave gerada (cdProgramacao) é retornada no ReturnKey
    cd_prog = find_text(resp, "ReturnKey")
    
    # Se por acaso retornar no dataset, podemos tentar extrair
    if not cd_prog or cd_prog == "0":
        # Tentativa de pegar do dataset
        cd_prog_ds = find_text(resp, "CDPROGRAMACAO")
        if cd_prog_ds:
            cd_prog = cd_prog_ds

    if not cd_prog:
        return {"error": "Programação criada mas cdProgramacao não identificado no retorno."}

    return {"cd_programacao": int(cd_prog), "xml_resposta": resp}


def gerar_ae_programacao(dados):
    """
    Gera a AE de monitoramento na OpenTech associada a uma programação via sgrGeraAeProgramacao.
    Retorna o cdViagem (ID da AE/Viagem) gerado.
    """
    chave = sgr_login()
    if not chave:
        return {"error": "Falha na autenticação com OpenTech"}

    cd_programacao = dados["cd_programacao"]
    placa_cavalo = dados["placa_cavalo"].upper().replace("-", "").strip()
    placa_carreta = dados.get("placa_carreta", "").upper().replace("-", "").strip()
    cpf_motorista = ''.join(filter(str.isdigit, dados["cpf_motorista"]))
    
    dt_prev_ini = dados.get("dt_prev_ini") or datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    dt_prev_fim = dados.get("dt_prev_fim") or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    
    cd_cid_origem = dados.get("cd_cid_origem") or 9999
    cd_cid_destino = dados.get("cd_cid_destino") or cd_cid_origem
    cd_rota = dados.get("cd_rota") or 1
    cd_transp = dados.get("cd_transp") or CD_CLIENTE
    ds_controle_carga = dados.get("ds_controle_carga") or "Emissao BBM Risk"
    
    # Processar número da Isca
    numero_isca = dados.get("numero_isca", "").strip()
    tag_iscas = ""
    if numero_isca:
        tag_iscas = f"""<tem:iscas>
            <tem:sgrIsca>
               <tem:cdemprastrea>1955576</tem:cdemprastrea>
               <tem:nrisca>{numero_isca}</tem:nrisca>
               <tem:dssiteisca></tem:dssiteisca>
               <tem:dsususiteisca></tem:dsususiteisca>
               <tem:dssenhasiteisca></tem:dssenhasiteisca>
               <tem:dsnumerovolumeisca></tem:dsnumerovolumeisca>
            </tem:sgrIsca>
         </tem:iscas>"""
    else:
        tag_iscas = "<tem:iscas/>"

    # Placa da carreta vazia ou com tag apropriada
    tag_carreta1 = f"<tem:nrPlacaCarreta1>{placa_carreta}</tem:nrPlacaCarreta1>" if placa_carreta else "<tem:nrPlacaCarreta1></tem:nrPlacaCarreta1>"

    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:sgrGeraAeProgramacao>
         <tem:chaveacesso>{chave}</tem:chaveacesso>
         <tem:cdpas>{CD_PAS}</tem:cdpas>
         <tem:cdcliente>{CD_CLIENTE}</tem:cdcliente>
         <tem:cdProgramacao>{cd_programacao}</tem:cdProgramacao>
         <tem:nrPlacaCavalo>{placa_cavalo}</tem:nrPlacaCavalo>
         {tag_carreta1}
         <tem:nrPlacaCarreta2></tem:nrPlacaCarreta2>
         <tem:nrDocMotorista1>{cpf_motorista}</tem:nrDocMotorista1>
         <tem:dtPrevIni>{dt_prev_ini}</tem:dtPrevIni>
         <tem:dtPrevFim>{dt_prev_fim}</tem:dtPrevFim>
         <tem:cdCidOrigem>{cd_cid_origem}</tem:cdCidOrigem>
         <tem:cdCidDestino>{cd_cid_destino}</tem:cdCidDestino>
         <tem:cdRota>{cd_rota}</tem:cdRota>
         <tem:cdTransp>{cd_transp}</tem:cdTransp>
         <tem:dsControleCarga>{ds_controle_carga}</tem:dsControleCarga>
         {tag_iscas}
      </tem:sgrGeraAeProgramacao>
   </soapenv:Body>
</soapenv:Envelope>"""

    resp = post_soap("sgrGeraAeProgramacao", body)
    if not resp:
        return {"error": "Sem resposta da OpenTech ao gerar AE"}

    return_id = find_text(resp, "ReturnID")
    if return_id != "0":
        desc = find_text(resp, "ReturnDescription")
        return {"error": desc or f"Erro ID {return_id}"}

    # O código da viagem costuma ser retornado no ReturnKey ou na tag CDVIAGEM
    cd_viagem = find_text(resp, "ReturnKey")
    if not cd_viagem or cd_viagem == "0":
        cd_viagem_ds = find_text(resp, "CDVIAGEM")
        if cd_viagem_ds:
            cd_viagem = cd_viagem_ds

    if not cd_viagem:
        return {"error": "AE gerada mas cdViagem não identificado no retorno."}

    return {"cd_viagem": int(cd_viagem), "xml_resposta": resp}


def cancelar_programacao(cd_programacao, cd_motivo=1):
    """
    Cancela uma programação de viagem na OpenTech via sgrCancelaProgramacao.
    """
    chave = sgr_login()
    if not chave:
        return {"error": "Falha na autenticação com OpenTech"}

    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:sgrCancelaProgramacao>
         <tem:chaveacesso>{chave}</tem:chaveacesso>
         <tem:cdpas>{CD_PAS}</tem:cdpas>
         <tem:cdcliente>{CD_CLIENTE}</tem:cdcliente>
         <tem:cdProgramacao>{cd_programacao}</tem:cdProgramacao>
         <tem:cdMotivoCancelaProg>{cd_motivo}</tem:cdMotivoCancelaProg>
      </tem:sgrCancelaProgramacao>
   </soapenv:Body>
</soapenv:Envelope>"""

    resp = post_soap("sgrCancelaProgramacao", body)
    if not resp:
        return {"error": "Sem resposta da OpenTech"}

    return_id = find_text(resp, "ReturnID")
    if return_id != "0":
        desc = find_text(resp, "ReturnDescription")
        return {"error": desc or f"Erro ID {return_id}"}

    return {"success": True, "message": "Programação cancelada com sucesso!"}


def baixar_programacao(cd_programacao):
    """
    Dá baixa (finaliza) em uma programação/viagem na OpenTech via sgrBaixarProgramacao.
    """
    chave = sgr_login()
    if not chave:
        return {"error": "Falha na autenticação com OpenTech"}

    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
   <soapenv:Header/>
   <soapenv:Body>
      <tem:sgrBaixarProgramacao>
         <tem:chaveacesso>{chave}</tem:chaveacesso>
         <tem:cdpas>{CD_PAS}</tem:cdpas>
         <tem:cdcliente>{CD_CLIENTE}</tem:cdcliente>
         <tem:cdProgramacao>{cd_programacao}</tem:cdProgramacao>
         <tem:nrCGCCPFLocalBaixa></tem:nrCGCCPFLocalBaixa>
      </tem:sgrBaixarProgramacao>
   </soapenv:Body>
</soapenv:Envelope>"""

    resp = post_soap("sgrBaixarProgramacao", body)
    if not resp:
        return {"error": "Sem resposta da OpenTech"}

    return_id = find_text(resp, "ReturnID")
    if return_id != "0":
        desc = find_text(resp, "ReturnDescription")
        return {"error": desc or f"Erro ID {return_id}"}

    return {"success": True, "message": "Baixa realizada com sucesso!"}


def obter_rotas_modelo():
    """
    Retorna todas as Rotas Modelo carregadas do arquivo local rotas_opentech.json.
    """
    import json
    try:
        with open("rotas_opentech.json", "r", encoding="utf-8") as f:
            rotas = json.load(f)
        return rotas
    except Exception as e:
        return {"error": f"Erro ao ler rotas locais: {str(e)}"}


def obter_dados_ae(cd_viagem):
    """
    Busca os dados completos de uma AE na Opentech via sgrRetornaAE.
    Recebe o cd_viagem (ID da AE) e retorna um dicionário com todos os campos disponíveis.
    Em caso de erro, retorna dict com chave 'error'.
    """
    chave = sgr_login()
    if not chave:
        return {"error": "Falha na autenticação com OpenTech"}

    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrRetornaAE>
      <tem:chaveacesso>{chave}</tem:chaveacesso>
      <tem:cdpas>{CD_PAS}</tem:cdpas>
      <tem:cdcliente>{CD_CLIENTE}</tem:cdcliente>
      <tem:cdviag>{cd_viagem}</tem:cdviag>
    </tem:sgrRetornaAE>
  </soapenv:Body>
</soapenv:Envelope>"""

    resp = post_soap("sgrRetornaAE", body)
    if not resp:
        return {"error": "Sem resposta da OpenTech ao buscar AE"}

    return_id = find_text(resp, "ReturnID")
    if return_id and return_id != "0":
        desc = find_text(resp, "ReturnDescription")
        return {"error": desc or f"Erro ID {return_id}"}

    # Extrair campos do diffgram/dataset retornado
    # Os campos variam entre versões mas os mais comuns são:
    dados = {
        "cd_viagem":        cd_viagem,
        "cd_programacao":   find_text(resp, "CDPROGRAMACAO") or find_text(resp, "cdProgramacao"),
        "nr_ae":            find_text(resp, "NRAE") or find_text(resp, "nrAE") or find_text(resp, "CDVIAG"),
        "cpf_motorista":    find_text(resp, "NRDOCMOT1") or find_text(resp, "cpfMotorista") or find_text(resp, "NRCPFMOT1"),
        "nome_motorista":   find_text(resp, "DSNOMEMOT1") or find_text(resp, "nomeMotorista") or find_text(resp, "DSMOTORISTA1"),
        "placa_cavalo":     find_text(resp, "NRPLACACAVALO") or find_text(resp, "nrPlacaCavalo"),
        "placa_carreta":    find_text(resp, "NRPLACAREBOQUE1") or find_text(resp, "nrPlacaCarreta1") or "",
        "cidade_origem":    find_text(resp, "DSCIDORIGEM") or find_text(resp, "dsCidOrigem"),
        "cidade_destino":   find_text(resp, "DSCIDDESTINO") or find_text(resp, "dsCidDestino"),
        "dt_prev_ini":      find_text(resp, "DTPREVINI") or find_text(resp, "dtPrevIni"),
        "dt_prev_fim":      find_text(resp, "DTPREVFIM") or find_text(resp, "dtPrevFim"),
        "valor_carga":      find_text(resp, "VLCARGA") or find_text(resp, "vlCarga"),
        "produto":          find_text(resp, "DSPRODUTO") or find_text(resp, "dsProduto"),
        "nr_isca":          find_text(resp, "NRISCA") or find_text(resp, "nrIsca") or "",
        "ds_rota":          find_text(resp, "DSROTA") or find_text(resp, "dsRota"),
        "ds_situacao":      find_text(resp, "DSSITUACAO") or find_text(resp, "dsSituacao"),
        "ds_controle_carga": find_text(resp, "DSCONTROLECARGA") or find_text(resp, "dsControleCarga"),
        "dt_inclusao":      find_text(resp, "DTINCLUSAO") or find_text(resp, "dtInclusao"),
        "_raw_resp":        resp,  # Guardar resposta bruta para debug se necessário
    }

    # Extrair trechos da rota (DSTRECHOS vem como JSON)
    ds_trechos_json = find_text(resp, "DSTRECHOS")
    trechos_rota = []
    if ds_trechos_json:
        try:
            trechos_rota = json.loads(ds_trechos_json)
        except Exception as e:
            logger.error(f"Erro ao parsear DSTRECHOS: {e}")
            pass
    dados["trechos_rota"] = trechos_rota

    # Extrair locais de parada (sgrPontosApoio)
    pontos_apoio = []
    blocos_pontos = re.findall(r"<sgrPontosApoio[^>]*>(.*?)</sgrPontosApoio>", resp, re.DOTALL)
    for bloco in blocos_pontos:
        ponto = {
            "fantasia": find_text(bloco, "DSFANTASIA") or "",
            "cidade": find_text(bloco, "DSCIDADE") or "",
            "uf": find_text(bloco, "DSSIGLAUF") or "",
            "tipo": find_text(bloco, "DSTIPOAPOIO") or "",
            "telefone": find_text(bloco, "NRFONE1") or "",
            "ddd": find_text(bloco, "NRDDD") or "",
            "km": find_text(bloco, "VLDISTTOT") or ""
        }
        pontos_apoio.append(ponto)
    dados["pontos_apoio"] = pontos_apoio

    return dados
def gerar_ae_v9(dados):
    chave = sgr_login()
    if not chave:
        return {"error": "Falha na autenticação com OpenTech"}
    
    cnpj_padrao = "21930065000106"
    cnpj_transp = ''.join(filter(str.isdigit, str(dados.get("cnpj_transp") or cnpj_padrao)))
    if not cnpj_transp: cnpj_transp = cnpj_padrao
    
    cnpj_origem = ''.join(filter(str.isdigit, str(dados.get("cnpj_origem") or cnpj_transp)))
    if not cnpj_origem: cnpj_origem = cnpj_transp
    
    cnpj_destino = ''.join(filter(str.isdigit, str(dados.get("cnpj_destino") or cnpj_transp)))
    if not cnpj_destino: cnpj_destino = cnpj_transp

    nrplacacarreta1 = dados.get("nrplacacarreta1", "")
    cdpaiscarreta1 = -1 if not nrplacacarreta1 else 1
    nrplacacarreta2 = dados.get("nrplacacarreta2", "")
    cdpaiscarreta2 = -1 if not nrplacacarreta2 else 1
    nrdocmotorista2 = dados.get("nrdocmotorista2", "")
    nomemot2 = dados.get("nomemot2", "")
    cdvincmot2 = dados.get("cdvincmot2", "")
    cdpaisorigemmot2 = -1 if not nrdocmotorista2 else 1
    rastreadorcavalo = dados.get("rastreadorcavalo", "")
    rastreadorcarreta1 = dados.get("rastreadorcarreta1", "")
    
    numero_isca = dados.get("nrIsca", "").strip()
    tag_iscas = ""
    if numero_isca:
        tag_iscas = f"""<tem:iscas>
            <tem:sgrIsca>
               <tem:cdemprastrea>1955576</tem:cdemprastrea>
               <tem:nrisca>{numero_isca}</tem:nrisca>
               <tem:dssiteisca></tem:dssiteisca>
               <tem:dsususiteisca></tem:dsususiteisca>
               <tem:dssenhasiteisca></tem:dssenhasiteisca>
               <tem:dsnumerovolumeisca></tem:dsnumerovolumeisca>
            </tem:sgrIsca>
         </tem:iscas>"""
    else:
        tag_iscas = "<tem:iscas/>"

    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                  xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrGerarAEv9>
      <tem:chaveacesso>{chave}</tem:chaveacesso>
      <tem:cdpas>{CD_PAS}</tem:cdpas>
      <tem:cdcliente>{CD_CLIENTE}</tem:cdcliente>
      <tem:cdpaisorigemcavalo>1</tem:cdpaisorigemcavalo>
      <tem:nrplacacavalo>{dados.get('nrplacacavalo', '')}</tem:nrplacacavalo>
      <tem:cdpaisorigemcarreta1>{cdpaiscarreta1}</tem:cdpaisorigemcarreta1>
      <tem:nrplacacarreta1>{nrplacacarreta1}</tem:nrplacacarreta1>
      <tem:cdpaisorigemcarreta2>{cdpaiscarreta2}</tem:cdpaisorigemcarreta2>
      <tem:nrplacacarreta2>{nrplacacarreta2}</tem:nrplacacarreta2>
      <tem:cdpaisorigemmot1>1</tem:cdpaisorigemmot1>
      <tem:nrdocmotorista1>{dados.get('nrdocmotorista1', '')}</tem:nrdocmotorista1>
      <tem:cdpaisorigemmot2>{cdpaisorigemmot2}</tem:cdpaisorigemmot2>
      <tem:nrdocmotorista2>{nrdocmotorista2}</tem:nrdocmotorista2>
      <tem:nomemot1>{dados.get('nomemot1', '')}</tem:nomemot1>
      <tem:nomemot2>{nomemot2}</tem:nomemot2>
      <tem:cdvincmot1>{dados.get('cdvincmot1', 'A')}</tem:cdvincmot1>
      <tem:cdvincmot2>{cdvincmot2}</tem:cdvincmot2>
      <tem:dtprevini>{dados.get('dtprevini', '')}</tem:dtprevini>
      <tem:dtprevfim>{dados.get('dtprevfim', '')}</tem:dtprevfim>
      <tem:rastreadorcavalo>{rastreadorcavalo}</tem:rastreadorcavalo>
      <tem:cdemprastrcavalo>1955576</tem:cdemprastrcavalo>
      <tem:rastreadorcarreta1>{rastreadorcarreta1}</tem:rastreadorcarreta1>
      <tem:cdemprastrcarreta1>{1955576 if nrplacacarreta1 else -1}</tem:cdemprastrcarreta1>
      <tem:cdcidorigem>{dados.get('cdcidorigem', 9999)}</tem:cdcidorigem>
      <tem:cdciddestino>{dados.get('cdciddestino', 9999)}</tem:cdciddestino>
      <tem:cdrota>-1</tem:cdrota>
      <tem:vlcarga>{int(dados.get('vlcarga', 1000))}</tem:vlcarga>
      <tem:cdtransp>{dados.get('cdtransp', CD_CLIENTE)}</tem:cdtransp>
      <tem:nrfonecel>{dados.get('nrfonecel', '999999999')}</tem:nrfonecel>
      <tem:cdtipooperacao>1</tem:cdtipooperacao>
      <tem:cdembarcador>{dados.get('cdembarcador', CD_CLIENTE)}</tem:cdembarcador>
      <tem:nrcontrolecarga></tem:nrcontrolecarga>
      <tem:nrfrota></tem:nrfrota>
      <tem:distanciatotal>0</tem:distanciatotal>
      <tem:pesocarga>0</tem:pesocarga>
      <tem:dscontroleviag1></tem:dscontroleviag1>
      <tem:dscontroleviag2></tem:dscontroleviag2>
      <tem:dscontroleviag3></tem:dscontroleviag3>
      <tem:dscontroleviag4></tem:dscontroleviag4>
      <tem:dscontroleviag5></tem:dscontroleviag5>
      <tem:dscontroleviag6></tem:dscontroleviag6>
      <tem:dscontroleviag7></tem:dscontroleviag7>
      <tem:dscontroleviag8></tem:dscontroleviag8>
      <tem:dscontroleviag9></tem:dscontroleviag9>
      <tem:dscontroleviag10></tem:dscontroleviag10>
      <tem:produtos>
        <tem:sgrProduto>
          <tem:cdprod>{dados.get('cdprod', 1)}</tem:cdprod>
          <tem:valor>{int(dados.get('vlcarga', 1000))}</tem:valor>
        </tem:sgrProduto>
      </tem:produtos>
      <tem:documentos>
        <tem:sgrDocumentoProdutosSeqV2>
          <tem:nrDoc>{dados.get('nrDoc', 'DOC-GERADO')}</tem:nrDoc>
          <tem:tpDoc>{dados.get('tpDoc', 2)}</tem:tpDoc>
          <tem:valorDoc>{int(dados.get('valorDoc', dados.get('vlcarga', 1000)))}</tem:valorDoc>
          <tem:tpOperacao>1</tem:tpOperacao>
          <tem:dtPrevista>{dados.get('dtprevfim', '')}</tem:dtPrevista>
          <tem:dtPrevistaSaida>{dados.get('dtprevini', '')}</tem:dtPrevistaSaida>
          <tem:cdCid>{dados.get('cdciddestino', 9999)}</tem:cdCid>
          <tem:dsRua>RUA PADRAO</tem:dsRua>
          <tem:nrRua>100</tem:nrRua>
          <tem:complementoRua></tem:complementoRua>
          <tem:dsBairro>CENTRO</tem:dsBairro>
          <tem:nrCep>00000000</tem:nrCep>
          <tem:nrFone1></tem:nrFone1>
          <tem:nrFone2></tem:nrFone2>
          <tem:cdembarcador>-1</tem:cdembarcador>
          <tem:cdPaisOrigemEmitente>1</tem:cdPaisOrigemEmitente>
          <tem:nrCnpjCpfEmitente>{cnpj_origem}</tem:nrCnpjCpfEmitente>
          <tem:cdPaisOrigemDestinatario>1</tem:cdPaisOrigemDestinatario>
          <tem:nrCnpjCPFDestinatario>{cnpj_destino}</tem:nrCnpjCPFDestinatario>
          <tem:nrCnpjCpfDestinatarioSequencia></tem:nrCnpjCpfDestinatarioSequencia>
          <tem:Latitude>0</tem:Latitude>
          <tem:Longitude>0</tem:Longitude>
          <tem:dsNome>{dados.get('destino_nome', 'DESTINATARIO PADRAO')}</tem:dsNome>
          <tem:qtVolumes>0</tem:qtVolumes>
          <tem:qtPecas>0</tem:qtPecas>
          <tem:nrLacreSIF>0</tem:nrLacreSIF>
          <tem:nrLacreArmador>0</tem:nrLacreArmador>
          <tem:dsNavio></tem:dsNavio>
          <tem:dsSiglaOrig></tem:dsSiglaOrig>
          <tem:dsSiglaDest></tem:dsSiglaDest>
          <tem:flRegiao>-1</tem:flRegiao>
          <tem:nrControleCliente1></tem:nrControleCliente1>
          <tem:nrControleCliente2></tem:nrControleCliente2>
          <tem:nrControleCliente3></tem:nrControleCliente3>
          <tem:produtos>
            <tem:sgrProduto>
              <tem:cdprod>{dados.get('cdprod', 1)}</tem:cdprod>
              <tem:valor>{int(dados.get('valorDoc', dados.get('vlcarga', 1000)))}</tem:valor>
            </tem:sgrProduto>
          </tem:produtos>
        </tem:sgrDocumentoProdutosSeqV2>
      </tem:documentos>
      <tem:paradas>
        <tem:sgrPontoApoioViagem/>
      </tem:paradas>
      <tem:sensorestemperatura>
        <tem:sgrSensorTemperatura/>
      </tem:sensorestemperatura>
      <tem:nrDDDCelMot>{dados.get('nrDDDCelMot', '11')}</tem:nrDDDCelMot>
      <tem:dsnomerespviag></tem:dsnomerespviag>
      <tem:dsfone1respviag></tem:dsfone1respviag>
      <tem:dsfone2respviag></tem:dsfone2respviag>
      {tag_iscas}
      <tem:rotas>
        <tem:Rota>
           <tem:cdRotaModelo>{dados.get('cdrota', -1)}</tem:cdRotaModelo>
        </tem:Rota>
      </tem:rotas>
    </tem:sgrGerarAEv9>
  </soapenv:Body>
</soapenv:Envelope>"""

    resp = post_soap("sgrGerarAEv9", body)
    if not resp:
        return {"error": "Sem resposta da OpenTech ao gerar AE"}

    return_id = find_text(resp, "ReturnID")
    if return_id != "0":
        desc = find_text(resp, "ReturnDescription")
        erros_list = re.findall(r"<DSERRO[^>]*>(.*?)</DSERRO>", resp, re.DOTALL)
        erros_str = "\n".join(erros_list) if erros_list else ""
        return {"error": f"{desc}\n{erros_str}"}

    cd_viagem = find_text(resp, "cdviagem") or find_text(resp, "cdviag")
    if cd_viagem:
        return {"cd_viagem": cd_viagem}
    return {"error": "AE gerada, mas CDVIAG não retornado."}
