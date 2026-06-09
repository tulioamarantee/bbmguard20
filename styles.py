import streamlit as st
import os

def apply_custom_branding(user=None):
    """
    Aplica o tema Dark/Premium profissional para o BBM Risk.
    """
    # Adicionar as fontes modernas do Google Fonts
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@500;800;900&family=Plus+Jakarta+Sans:wght@300;400;600;700&display=swap');
        
        /* Modificar fonte padrão do Streamlit */
        html, body, [class*="css"], .stMarkdown {
            font-family: 'Plus Jakarta Sans', sans-serif !important;
        }

        /* Estilo dos Botões - Gradiente Premium com Efeito de Hover e Sombra */
        div.stButton > button:first-child {
            background: linear-gradient(135deg, #0052d4, #4364f7) !important;
            color: #FFFFFF !important;
            border-radius: 8px !important;
            border: none !important;
            padding: 8px 20px !important;
            font-weight: 600 !important;
            font-size: 0.95rem !important;
            letter-spacing: 0.5px !important;
            box-shadow: 0 4px 12px rgba(0, 82, 212, 0.3) !important;
            transition: all 0.3s ease !important;
            width: 100%;
        }
        
        div.stButton > button:hover {
            background: linear-gradient(135deg, #4364f7, #6fb1fc) !important;
            transform: translateY(-2px) !important;
            box-shadow: 0 6px 20px rgba(67, 100, 247, 0.4) !important;
        }

        div.stButton > button:active {
            transform: translateY(1px) !important;
        }

        /* Expander Customizado com Efeito de Card Premium */
        .streamlit-expanderHeader {
            background-color: rgba(255, 255, 255, 0.05) !important;
            border-radius: 8px !important;
            border: 1px solid rgba(255, 255, 255, 0.08) !important;
            transition: all 0.2s ease !important;
            margin-bottom: 5px !important;
        }
        
        .streamlit-expanderHeader:hover {
            background-color: rgba(255, 255, 255, 0.09) !important;
            border-color: rgba(67, 100, 247, 0.4) !important;
        }

        /* Badges de Status Modernos */
        .badge {
            padding: 5px 12px;
            border-radius: 20px;
            font-weight: 700;
            font-size: 0.75rem;
            letter-spacing: 0.8px;
            display: inline-block;
            text-align: center;
            text-transform: uppercase;
            box-shadow: 0 2px 6px rgba(0,0,0,0.15);
        }
        
        .badge-sucesso { 
            background: linear-gradient(135deg, #11998e, #38ef7d); 
            color: #FFFFFF; 
        }
        .badge-perigo { 
            background: linear-gradient(135deg, #ff416c, #ff4b2b); 
            color: #FFFFFF; 
        }
        .badge-atencao { 
            background: linear-gradient(135deg, #f12711, #f5af19); 
            color: #FFFFFF; 
        }

        /* Estilização para as caixas de Status SIL */
        .status-box {
            background: rgba(255, 255, 255, 0.03); 
            padding: 12px 18px; 
            border-radius: 10px; 
            margin-top: 10px;
            border-left: 4px solid #4364f7;
            box-shadow: 0 4px 10px rgba(0,0,0,0.1);
        }

        /* Input Fields e Selectors */
        input, select, textarea {
            border-radius: 8px !important;
        }

        </style>
    """, unsafe_allow_html=True)

def render_header(user=None):
    """
    Cabeçalho Premium do BBM Risk.
    """
    st.markdown("""
        <div style="background: var(--secondary-background-color); 
                    padding: 22px 28px; 
                    border-radius: 14px; 
                    margin-bottom: 22px; 
                    border: 1px solid rgba(128, 128, 128, 0.2);
                    box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1); 
                    display: flex; 
                    align-items: center; 
                    gap: 20px;">
            <div style="font-size: 2.8rem; 
                        background: rgba(128, 128, 128, 0.1); 
                        padding: 10px 15px; 
                        border-radius: 10px;
                        border: 1px solid rgba(128,128,128,0.2);">
                ⚡
            </div>
            <div>
                <h1 style="color: var(--text-color) !important; 
                           margin: 0; 
                           font-family: 'Orbitron', sans-serif; 
                           font-weight: 900; 
                           letter-spacing: 1.5px; 
                           font-size: 2.1rem;">
                    BBM RISK
                </h1>
                <p style="color: var(--text-color) !important; 
                          margin: 4px 0 0 0; 
                          font-size: 0.95rem; 
                          font-weight: 500; 
                          letter-spacing: 0.3px;
                          opacity: 0.7;">
                    Controle de Acessos & Gerenciador de Autorizações Opentech
                </p>
            </div>
        </div>
    """, unsafe_allow_html=True)

def render_sil_status(status, data_consulta):
    """
    Exibição de status SIL adaptado para o novo branding.
    """
    status_norm = str(status).strip().lower()
    
    # Mapeamento de cores
    if status_norm in ["validado", "liberado"]:
        color = "#38ef7d" # verde brilhante
        border_color = "#11998e"
    elif status_norm in ["bloqueado", "não recomendado", "vencido"]:
        color = "#ff4b2b" # vermelho vibrante
        border_color = "#ff416c"
    else:
        color = "#ffb300" # laranja
        border_color = "#f5af19"
        
    st.markdown(f"""
        <div style="background: rgba(255, 255, 255, 0.02); 
                    padding: 12px 18px; 
                    border-radius: 8px; 
                    margin-top: 10px;
                    border-left: 4px solid {border_color};
                    box-shadow: 0 4px 10px rgba(0,0,0,0.15);">
            <b style="color: #cfd8dc;">Status SIL Opentech:</b> 
            <span style='color: {color}; font-weight: 800; font-size: 1rem; letter-spacing: 0.5px; margin-left: 5px;'>{status}</span>
            <br><span style="color: #90a4ae; font-size: 0.75rem;">Consulta realizada em: {data_consulta}</span>
        </div>
    """, unsafe_allow_html=True)

def render_driver_badge(status_interno, recentes=0):
    """
    Badges estilizados para Portaria do BBM Risk.
    """
    if status_interno == 'Ativo':
        st.markdown('<span class="badge badge-sucesso">✔ LIBERADO</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="badge badge-perigo">✖ {status_interno.upper()}</span>', unsafe_allow_html=True)
