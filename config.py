# CONFIGURAÇÕES DA INTEGRAÇÃO OPENTECH SIL
import os

# --- Credenciais do WebService B2B ---
# Fallback seguro para streamlit secrets sem levantar erro de inicialização
try:
    import streamlit as st
    # Força a leitura do st.secrets, se não encontrar/falhar, usamos fallback
    WS_URL = os.environ.get("WS_URL", st.secrets.get("WS_URL", "https://ws.opentechgr.com.br/sgrOpentech/sgropentech.asmx"))
    WS_DOMINIO = os.environ.get("WS_DOMINIO", st.secrets.get("WS_DOMINIO", "Transportadoras"))
    WS_USUARIO = os.environ.get("WS_USUARIO", st.secrets.get("WS_USUARIO", "INT.DIALOG"))
    WS_SENHA   = os.environ.get("WS_SENHA",   st.secrets.get("WS_SENHA",   "INT@123456789"))
    CD_PAS     = int(os.environ.get("CD_PAS",     st.secrets.get("CD_PAS",     61027)))
    CD_CLIENTE = int(os.environ.get("CD_CLIENTE", st.secrets.get("CD_CLIENTE", 2673186)))
except Exception:
    WS_URL = os.environ.get("WS_URL", "https://ws.opentechgr.com.br/sgrOpentech/sgropentech.asmx")
    WS_DOMINIO = os.environ.get("WS_DOMINIO", "Transportadoras")
    WS_USUARIO = os.environ.get("WS_USUARIO", "INT.DIALOG")
    WS_SENHA   = os.environ.get("WS_SENHA",   "INT@123456789")
    CD_PAS     = int(os.environ.get("CD_PAS",     61027))
    CD_CLIENTE = int(os.environ.get("CD_CLIENTE", 2673186))

# --- Mapeamento de Status OpenTech ---
# 1: Recomendado/Validado
# 2: Não Recomendado
# 5: Em Pesquisa
# 8: Sem Pesquisa/Expirado
STATUS_MAP = {
    "1": "Validado",
    "2": "Validado",
    "5": "Em Pesquisa",
    "8": "Sem Pesquisa",
    "0": "Liberado"
}

def get_status_label(codigo):
    return STATUS_MAP.get(str(codigo), f"Status {codigo}")
