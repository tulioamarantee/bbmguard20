import streamlit as st
from datetime import datetime, timedelta
import services
import styles
import re
from database import init_db

# Configuração da página
st.set_page_config(page_title="BBM Risk - Gestão de Risco", layout="wide", page_icon="⚡")

# Inicializar Banco de Dados
init_db()

import contextlib

@contextlib.contextmanager
def custom_spinner(text="Carregando..."):
    placeholder = st.empty()
    gif_url = "https://media.tenor.com/7bZfH9jZ9bYAAAAC/french-bulldog-running.gif"
    html = f"""
    <div style="display: flex; align-items: center; gap: 15px; color: var(--text-color); font-weight: 600; margin-bottom: 15px; padding: 12px; background: rgba(67, 100, 247, 0.05); border-radius: 8px; border-left: 4px solid var(--primary-color); box-shadow: 0 2px 4px rgba(0,0,0,0.05);">
        <img src="{gif_url}" width="45" style="border-radius: 50%; background: transparent; mix-blend-mode: multiply;">
        <span>{text}</span>
    </div>
    """
    placeholder.markdown(html, unsafe_allow_html=True)
    try:
        yield
    finally:
        placeholder.empty()

st.spinner = custom_spinner

# --- GERENCIAMENTO DE SESSÃO ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = None

def login_screen():
    # Aplicar estilo mesmo no login
    styles.apply_custom_branding()
    
    logo_b64 = styles.get_bbm_logo_b64()
    logo_html = f'<img src="data:image/png;base64,{logo_b64}" style="height: 100px; filter: drop-shadow(0 0 10px rgba(0,0,0,0.1)); margin-bottom: 10px;">' if logo_b64 else '<div style="font-size: 3.5rem; filter: drop-shadow(0 0 10px rgba(67,100,247,0.4)); margin-bottom: 10px;">⚡</div>'

    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown(f"""
            <div style="text-align: center; margin-bottom: 25px; margin-top: 40px;">
                {logo_html}
                <h1 style="font-family: 'Orbitron', sans-serif; font-weight: 900; letter-spacing: 2px; color: var(--text-color); font-size: 2.3rem; margin: 0;">BBM RISK</h1>
                <span style="color: #90a4ae; font-size: 0.95rem; font-weight: 500;">Controle de Acesso & Torre de Controle</span>
            </div>
        """, unsafe_allow_html=True)
        
        with st.form("login_form"):
            st.subheader("🔑 Acesso ao Painel")
            login = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Acessar Plataforma")
            
            if submit:
                user = services.autenticar_usuario(login, senha)
                if user:
                    st.session_state.autenticado = True
                    st.session_state.usuario = dict(user)
                    st.success("Acesso autorizado!")
                    st.rerun()
                else:
                    st.error("Credenciais inválidas.")

def set_menu(menu_name):
    st.session_state.current_menu = menu_name

def main_app():
    user = st.session_state.usuario
    styles.apply_custom_branding(user)
    
    # Sidebar
    with st.sidebar:
        st.markdown(f"### Olá, {user['nome']}")
        st.caption(f"🏢 {user['empresa_nome']}")
        st.divider()
        
        # Definir opções de navegação
        role = (user.get('role') or '').lower()
        # Controle de navegação manual via botões da Home
        if "current_menu" not in st.session_state:
            st.session_state.current_menu = "Home"
            
        # Captura parâmetro da URL para roteamento via links HTML dos cards
        qp = st.query_params
        if "menu" in qp:
            st.session_state.current_menu = qp["menu"]
            st.query_params.clear()
            
        menu = st.session_state.current_menu
        
        st.divider()
        if st.button("Sair"):
            st.session_state.clear()
            st.rerun()
            
        st.markdown("<br><br><br>", unsafe_allow_html=True)
        if st.button("v1.2.0", use_container_width=True):
            st.balloons()
            st.markdown("""
                <style>
                @keyframes flyDog {
                    0% { bottom: -150px; transform: translateX(-50%) scale(0.5); opacity: 1; }
                    100% { bottom: 120vh; transform: translateX(-50%) scale(1.5); opacity: 1; }
                }
                .flying-dog {
                    position: fixed;
                    left: 50%;
                    z-index: 999999;
                    animation: flyDog 4s ease-out forwards;
                    pointer-events: none;
                }
                </style>
                <img src="https://media.tenor.com/7bZfH9jZ9bYAAAAC/french-bulldog-running.gif" class="flying-dog" width="150">
            """, unsafe_allow_html=True)
            st.success("Woof woof! 🐶 O Bulldog decolou!")

    # Título da Página
    styles.render_header(user)
    st.divider()

    if menu != "Home":
        if st.button("🔙 Voltar para a Home", key="btn_voltar_home"):
            set_menu("Home")
            st.rerun()

    # --- TELAS ---
    if menu == "Home":
        render_home(user)
    elif menu == "Cadastro e Consulta":
        render_cadastro_consulta(user)
    elif menu == "Solicitação de Monitoramento":
        render_ae_express(user)
    elif menu == "Torre de Controle":
        render_torre_controle(user)
    elif menu == "Dashboard":
        if (user.get('role') or '').lower() == 'portaria':
            st.warning("⚠️ Acesso ao Dashboard não permitido para o usuário da Portaria.")
        else:
            render_dashboard(user)
    elif menu == "Configurações":
        render_config(user)

def render_home(user):
    st.markdown("""
    <style>
    /* Ocultar a sidebar completamente na tela inicial */
    [data-testid="stSidebar"] { display: none !important; }
    [data-testid="collapsedControl"] { display: none !important; }
    
    .home-container {
        padding: 2rem 0 0 0;
        text-align: center;
        animation: fadeIn 0.8s ease-out;
    }
    
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .home-title {
        font-size: 3.8rem !important;
        font-weight: 800 !important;
        line-height: 1.1 !important;
        letter-spacing: -0.04em !important;
        color: var(--text-color) !important;
        margin-bottom: 1rem !important;
        font-family: 'Inter', 'Segoe UI', sans-serif !important;
    }
    
    .home-subtitle {
        font-size: 1.25rem;
        color: #666;
        margin-bottom: 4rem;
        font-weight: 400;
        line-height: 1.6;
    }
    
    /* CSS MAGIC para os botoes nativos do Streamlit virarem cards modernos */
    .stApp div.stButton > button {
        background-color: var(--secondary-background-color) !important;
        border-radius: 16px !important;
        padding: 2rem !important;
        height: 180px !important;
        width: 100% !important;
        border: 1px solid rgba(128, 128, 128, 0.2) !important;
        color: var(--text-color) !important;
        box-shadow: 0 4px 15px rgba(0,0,0,0.05) !important;
        transition: all 0.3s cubic-bezier(0.25, 0.8, 0.25, 1) !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: center !important;
        justify-content: center !important;
    }
    
    .stApp div.stButton > button:hover {
        transform: translateY(-8px) !important;
        box-shadow: 0 15px 30px rgba(0,0,0,0.15) !important;
        border-color: var(--primary-color) !important;
    }
    
    .stApp div.stButton > button p {
        font-family: 'Inter', sans-serif !important;
        font-size: 1.3rem !important;
        font-weight: 700 !important;
        color: var(--text-color) !important;
        text-align: center !important;
        margin: 0 !important;
    }
    
    /* Botão Desabilitado */
    .stApp div.stButton > button:disabled {
        opacity: 0.5 !important;
        filter: grayscale(100%) !important;
        transform: none !important;
        box-shadow: none !important;
    }
    </style>
    
    <div class="home-container">
        <h1 class="home-title">BBM RISK</h1>
        <p class="home-subtitle">Torre de Controle & Gestão Integrada</p>
    </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.button(
            "📋\nPORTARIA E CONSULTA",
            key="btn_cadastro",
            use_container_width=True,
            on_click=set_menu,
            args=("Cadastro e Consulta",)
        )
            
    with col2:
        st.button(
            "📝\nSOLICITAR AUTORIZAÇÃO DE EMBARQUE",
            key="btn_monitoramento",
            use_container_width=True,
            on_click=set_menu,
            args=("Solicitação de Monitoramento",)
        )
            
    with col3:
        role = (user.get('role') or '').lower()
        if role == 'portaria':
            st.button(
                "🗺️\nTORRE DE CONTROLE\n(Acesso Restrito)",
                key="btn_torre",
                use_container_width=True,
                disabled=True
            )
        else:
            st.button(
                "🗺️\nTORRE DE CONTROLE",
                key="btn_torre",
                use_container_width=True,
                on_click=set_menu,
                args=("Torre de Controle",)
            )

    role = (user.get('role') or '').lower()
    if role in ['admin', 'admin_ti', 'supervisor']:
        st.markdown("<h3 style='text-align: center; margin-top: 3rem; margin-bottom: 1.5rem; font-family: \"Inter\", sans-serif; font-size: 1.5rem;'>Módulos Gerenciais</h3>", unsafe_allow_html=True)
        col4, col5, col6 = st.columns(3)
        with col4:
            if role.startswith('admin'):
                st.button(
                    "📊\nDASHBOARD",
                    key="btn_dash",
                    use_container_width=True,
                    on_click=set_menu,
                    args=("Dashboard",)
                )
        with col5:
            st.button(
                "⚙️\nCONFIGURAÇÕES",
                key="btn_config",
                use_container_width=True,
                on_click=set_menu,
                args=("Configurações",)
            )
def render_cadastro_consulta(user):
    st.header("📋 Cadastro e Consulta")
    st.caption("Gerenciamento integrado de Motoristas e Veículos.")
    
    escolha = st.radio("Módulo", ["🚦 Portaria (Motoristas)", "🚚 Mapa (Veículos)"], horizontal=True, label_visibility="collapsed")
    st.divider()
    
    if escolha == "🚦 Portaria (Motoristas)":
        render_motoristas(user)
    else:
        render_veiculos(user)

def render_torre_controle(user, fullscreen=False):
    if not fullscreen:
        st.header("🗺️ Torre de Controle")
        st.caption("Visão em tempo real das Viagens (AEs) Ativas da frota.")
        
        # Link de tela cheia
        link = f"/?mapa_fullscreen=1&emp={user['empresa_id']}"
        st.markdown(f'''
        <a href="{link}" target="_blank" style="display: inline-block; padding: 8px 16px; background-color: var(--primary-color); color: white; text-decoration: none; border-radius: 5px; font-weight: bold; margin-bottom: 15px;">
            🖥️ Abrir Mapa em Tela Cheia
        </a>
        ''', unsafe_allow_html=True)
    else:
        st.markdown("<h2 style='text-align: center;'>🗺️ Torre de Controle - Tela Cheia</h2>", unsafe_allow_html=True)
    
    with st.spinner("Sincronizando coordenadas com o SIL..."):
        viagens = services.listar_viagens_ativas_com_coordenadas(user['empresa_id'])
        
    if not viagens:
        st.info("Nenhuma viagem ativa no momento.")
        viagens = []
        
    import pandas as pd
    from datetime import datetime
    import folium
    from streamlit_folium import st_folium
    
    # Processar categorias
    v_andamento = [v for v in viagens if 'ANDAMENTO' in v.get('situacao', '')]
    v_novas = [v for v in viagens if 'NOVA' in v.get('situacao', '')]
    
    v_sem_sinal_amarelo = []
    v_sem_sinal_vermelho = []
    for v in v_andamento:
        data_pos = v.get('data_posicao')
        if data_pos:
            try:
                dt_pos = datetime.fromisoformat(data_pos)
                now_dt = datetime.now(dt_pos.tzinfo)
                diff_seconds = (now_dt - dt_pos).total_seconds()
                if 600 < diff_seconds <= 1800:
                    v_sem_sinal_amarelo.append(v)
                elif diff_seconds > 1800:
                    v_sem_sinal_vermelho.append(v)
            except:
                v_sem_sinal_vermelho.append(v)
        else:
            v_sem_sinal_vermelho.append(v)

    # Filtrar apenas as viagens em andamento que tem lat/lon válidos para o mapa
    v_map = [v for v in v_andamento if v.get('lat') and v.get('lon')]
    
    col1, col2 = st.columns([3, 1])
    
    with col2:
        st.metric("🚀 Em Andamento", len(v_andamento))
        st.metric("🆕 Viagens Novas", len(v_novas))
        st.metric("🟡 Sem Sinal (10 a 30m)", len(v_sem_sinal_amarelo))
        st.metric("🔴 Sem Sinal (>30m)", len(v_sem_sinal_vermelho))
        
        st.divider()
        if st.button("🔄 Atualizar Mapa", use_container_width=True):
            services.listar_viagens_ativas_com_coordenadas.clear()
            st.rerun()
            
    with col1:
        if not v_map:
            # Mapa do Brasil padrão
            center_lat, center_lon = -14.2350, -51.9253
            m = folium.Map(location=[center_lat, center_lon], zoom_start=4)
        else:
            # Calcular o centro do mapa
            lats = [float(v['lat']) for v in v_map]
            lons = [float(v['lon']) for v in v_map]
            center_lat = sum(lats) / len(lats)
            center_lon = sum(lons) / len(lons)
            
            m = folium.Map(location=[center_lat, center_lon], zoom_start=5)
            
            # Adicionar marcadores customizados
            for v in v_map:
                ds_rota = v.get('ds_rota', 'N/I')
                popup_text = f"""
                <div style="font-size: 14px; min-width: 200px; line-height: 1.5;">
                    <b>AE:</b> {v.get('cd_viagem')}<br>
                    <b>Placa:</b> {v.get('placa_cavalo')}<br>
                    <b>Motorista:</b> {v.get('nome_mot_bd')}<br>
                    <b>Rota:</b> {ds_rota}
                </div>
                """
                
                # Definir a cor do caminhãozinho
                cor_icone = 'blue'
                data_pos = v.get('data_posicao')
                if data_pos:
                    try:
                        dt_pos = datetime.fromisoformat(data_pos)
                        now_dt = datetime.now(dt_pos.tzinfo)
                        diff_seconds = (now_dt - dt_pos).total_seconds()
                        if 600 < diff_seconds <= 1800:
                            cor_icone = 'orange'
                        elif diff_seconds > 1800:
                            cor_icone = 'red'
                    except:
                        cor_icone = 'red'
                else:
                    cor_icone = 'red'
                
                icon = folium.Icon(color=cor_icone, icon='truck', prefix='fa')
                
                folium.Marker(
                    [float(v['lat']), float(v['lon'])],
                    popup=popup_text,
                    tooltip=v.get('placa_cavalo'),
                    icon=icon
                ).add_to(m)
                
        # Exibe o mapa. Na tela cheia, podemos deixar mais largo.
        map_height = 800 if fullscreen else 500
        st_folium(m, use_container_width=True, height=map_height, returned_objects=[])

    if not fullscreen:
        st.markdown("### 🚚 Resumo das Viagens")
        if viagens:
            df = pd.DataFrame(viagens)
            # Organizar colunas
            cols = ['cd_viagem', 'situacao', 'placa_cavalo', 'nome_mot_bd', 'origem', 'destino', 'cidade_posicao', 'data_posicao']
            df = df[[c for c in cols if c in df.columns]]
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma viagem para exibir.")
def render_dashboard(user):
    from datetime import datetime, timedelta
    import plotly.express as px
    import pandas as pd
    
    st.subheader("📊 Painel Gerencial")
    
    with st.expander("⚙️ Filtros do Dashboard", expanded=True):
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_periodo = st.selectbox(
                "Período de Análise",
                ["Hoje", "Últimos 7 dias", "Últimos 15 dias", "Últimos 30 dias", "Mês Atual", "Período Específico"],
                index=1
            )
            dt_inicio_obj = datetime.now()
            dt_fim_obj = datetime.now()
            
            if filtro_periodo == "Período Específico":
                datas = st.date_input("Selecione o Período", [datetime.now() - timedelta(days=7), datetime.now()])
                if len(datas) == 2:
                    dt_inicio_obj, dt_fim_obj = datas
                elif len(datas) == 1:
                    dt_inicio_obj = dt_fim_obj = datas[0]
            elif filtro_periodo == "Últimos 7 dias":
                dt_inicio_obj = datetime.now() - timedelta(days=7)
            elif filtro_periodo == "Últimos 15 dias":
                dt_inicio_obj = datetime.now() - timedelta(days=15)
            elif filtro_periodo == "Últimos 30 dias":
                dt_inicio_obj = datetime.now() - timedelta(days=30)
            elif filtro_periodo == "Mês Atual":
                dt_inicio_obj = datetime.now().replace(day=1)
                
            dt_inicio_str = dt_inicio_obj.strftime("%Y-%m-%d")
            dt_fim_str = dt_fim_obj.strftime("%Y-%m-%d")

        with col_f2:
            filtro_venc = st.selectbox(
                "Vencimento de Cadastros",
                ["Já Vencidos", "Vencendo em 7 dias", "Vencendo em 15 dias", "Vencendo em 30 dias"],
                index=0
            )

    dias_venc = 0
    if "7 dias" in filtro_venc: dias_venc = 7
    elif "15 dias" in filtro_venc: dias_venc = 15
    elif "30 dias" in filtro_venc: dias_venc = 30

    stats = services.get_stats_dashboard(user['empresa_id'], dias_venc, dt_inicio_str, dt_fim_str)
    qtd_aes = services.get_aes_criadas_qtd(user['empresa_id'], dt_inicio_str, dt_fim_str)
    qtd_cadastros = services.get_cadastros_criados(user['empresa_id'], dt_inicio_str, dt_fim_str)
    
    st.markdown("### 📈 Indicadores Principais")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("AEs Criadas", qtd_aes, f"{filtro_periodo}")
    col2.metric("Novos Cadastros", qtd_cadastros, f"{filtro_periodo}")
    col3.metric("Consultas SIL", stats['consultas_periodo'], f"{filtro_periodo}")
    col4.metric("Cadastros a Vencer", stats['cadastros_vencidos'], f"{filtro_venc}", delta_color="inverse")
    col5.metric("Liberações", stats['liberacoes_periodo'], f"{filtro_periodo}")
    
    st.markdown("---")
    
    col_graf, col_tab = st.columns([1.6, 1])
    
    with col_graf:
        st.subheader("🏆 Produtividade (AEs por Login)")
        aes_usuario = services.get_aes_por_usuario(user['empresa_id'], dt_inicio_str, dt_fim_str)
        if aes_usuario:
            df_aes = pd.DataFrame(aes_usuario)
            fig = px.pie(df_aes, values='AEs Criadas', names='Usuario', hole=0.3, color_discrete_sequence=px.colors.sequential.Blues_r)
            fig.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhuma AE gerada no período selecionado.")
            
    with col_tab:
        st.subheader("📍 Últimas Consultas")
        historico = services.listar_historico_acessos(user['empresa_id'])
        if historico:
            df_hist = pd.DataFrame(historico)
            df_hist = df_hist[['data_hora', 'cpf', 'status_resultado']]
            df_hist.columns = ['Hora', 'CPF', 'Status']
            df_hist['Hora'] = df_hist['Hora'].apply(lambda x: x.split()[-1][:5] if isinstance(x, str) else x)
            st.dataframe(df_hist.head(8), use_container_width=True, hide_index=True)
        else:
            st.info("Nenhuma consulta registrada hoje.")

def render_config(user):
    st.header("⚙️ Configurações")
    role = (user.get('role') or '').lower()
    if role == 'portaria':
        st.info("As regras automáticas (Fase 2) estão ocultas. Modo Portaria Ativado.")
    else:
        st.subheader("🔗 Integração Opentech")
        st.write("A Opentech possui milhares de rotas ativas. Se uma nova rota modelo foi criada no SIL, você precisa sincronizar o banco local do BBM RISK para que ela apareça na lista de Novo Monitoramento.")
        
        if st.button("🔄 Sincronizar Rotas do SIL", use_container_width=True):
            with st.spinner("Conectando à Opentech e baixando catálogo de rotas (Isso pode levar até 2 minutos)..."):
                ok, msg = services.sincronizar_rotas_opentech()
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
        
        st.divider()
        if 'success_msg' in st.session_state:
            st.success(st.session_state['success_msg'])
            del st.session_state['success_msg']

        # ── Abas: Criar Usuário | Gerenciar Usuários | Produtividade ──
        if role == 'admin':
            tabs = st.tabs(["➕ Novo Usuário", "👥 Gerenciar Usuários", "📊 Produtividade"])
            tab_criar = tabs[0]
            tab_gerenciar = tabs[1]
            tab_prod = tabs[2]
        else:
            tab_criar = None
            tab_gerenciar = None
            tab_prod = None
            st.info("🔒 O gerenciamento e visualização de usuários é restrito ao nível Administrador.")

        # ── ABA 1: Criar novo usuário (Apenas Admin) ──
        if tab_criar:
            with tab_criar:
                with st.form("criar_usuario_form"):
                    st.subheader("Criar novo usuário")
                    nome = st.text_input("Nome completo")
                    cpf_raw = st.text_input("CPF (apenas números)", placeholder="000.000.000-00")
                    cpf = f"{cpf_raw[:3]}.{cpf_raw[3:6]}.{cpf_raw[6:9]}-{cpf_raw[9:]}" if len(cpf_raw) == 11 else cpf_raw
                    data_nasc = st.date_input(
                        "Data de Nascimento",
                        min_value=datetime(1950, 1, 1),
                        max_value=datetime(2026, 12, 31),
                        value=datetime(2000, 1, 1)
                    )
                    email = st.text_input("E‑mail")
                    login = st.text_input("Login (geralmente e‑mail)")
                    senha = st.text_input("Senha", type="password")
                    role_sel = st.selectbox("Nível de acesso", ["Portaria", "Supervisor", "Admin"])
                    submit = st.form_submit_button("Criar usuário")
                    
                    if submit:
                        if not all([nome, cpf, email, login, senha]):
                            st.error("Preencha todos os campos.")
                        else:
                            sucesso, msg = services.cadastrar_usuario(
                                nome=nome,
                                login=login,
                                senha=senha,
                                cpf=cpf,
                                data_nascimento=data_nasc.isoformat(),
                                email=email,
                                empresa_id=user['empresa_id'],
                                role=role_sel.lower()
                            )
                            if sucesso:
                                st.session_state['success_msg'] = msg
                                st.rerun()
                            else:
                                st.error(msg)

        # ── ABA 2: Gerenciar usuários existentes (Apenas Admin) ──
        if tab_gerenciar:
            with tab_gerenciar:
                st.subheader("Usuários cadastrados")
            usuarios = services.listar_usuarios(user['empresa_id'])

            if not usuarios:
                st.info("Nenhum usuário cadastrado ainda.")
            else:
                for u in usuarios:
                    role_label = (u.get('role') or 'Portaria').capitalize()
                    icon = "🔑" if role_label.lower().startswith("admin") else ("🛡️" if role_label.lower() == "supervisor" else "👤")
                    with st.expander(f"{icon} {u['nome']}  —  {role_label}  |  Login: {u['login']}"):
                        col_info, col_acoes = st.columns([2, 1])

                        with col_info:
                            st.markdown(f"**CPF:** {u.get('cpf') or 'N/I'}")
                            st.markdown(f"**E-mail:** {u.get('email') or 'N/I'}")
                            st.markdown(f"**Nascimento:** {u.get('data_nascimento') or 'N/I'}")

                        with col_acoes:
                            st.caption("Nível atual: " + role_label)

                        st.markdown("---")

                        if role == 'admin':
                            # Formulário de edição
                            with st.form(f"editar_usuario_{u['id']}"):
                                st.markdown("##### ✏️ Editar dados")
                                col1, col2 = st.columns(2)
                                with col1:
                                    novo_nome = st.text_input("Nome", value=u['nome'], key=f"nome_{u['id']}")
                                    novo_email = st.text_input("E-mail", value=u.get('email') or '', key=f"email_{u['id']}")
                                with col2:
                                    niveis = ["Portaria", "Supervisor", "Admin"]
                                    idx_atual = 0
                                    for i, n in enumerate(niveis):
                                        if n.lower() == (u.get('role') or 'portaria').lower():
                                            idx_atual = i
                                            break
                                    novo_role = st.selectbox("Nível de acesso", niveis, index=idx_atual, key=f"role_{u['id']}")
                                    nova_senha = st.text_input("Nova senha (deixe vazio para manter)", type="password", key=f"senha_{u['id']}")

                                col_salvar, col_excluir = st.columns([1, 1])
                                with col_salvar:
                                    btn_salvar = st.form_submit_button("💾 Salvar alterações", use_container_width=True)
                                
                                if btn_salvar:
                                    ok, msg = services.atualizar_usuario(
                                        usuario_id=u['id'],
                                        nome=novo_nome,
                                        email=novo_email,
                                        role=novo_role.lower(),
                                        nova_senha=nova_senha if nova_senha else None
                                    )
                                    if ok:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)

                            # Botão de exclusão (fora do form para evitar conflito)
                            if u['id'] != user['id']:
                                if st.button(f"🗑️ Excluir {u['nome']}", key=f"del_{u['id']}", type="secondary"):
                                    ok, msg = services.excluir_usuario(u['id'])
                                    if ok:
                                        st.success(msg)
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            else:
                                st.caption("ℹ️ Você não pode excluir seu próprio usuário.")

        # ── ABA 3: Produtividade (Apenas Admin) ──
        if tab_prod:
            with tab_prod:
                st.subheader("📊 Relatório de Produtividade dos Usuários")
                st.write("Acompanhe a quantidade de consultas e AEs emitidas por cada colaborador da sua empresa.")
                
                df_prod = services.get_produtividade_usuarios(user['empresa_id'])
                if df_prod is not None and not df_prod.empty:
                    st.dataframe(df_prod, use_container_width=True, hide_index=True)
                    
                    csv = df_prod.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Baixar Relatório (CSV / Excel)",
                        data=csv,
                        file_name=f"Produtividade_Usuarios_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                        mime="text/csv",
                        type="primary"
                    )
                else:
                    st.info("Nenhum dado de produtividade encontrado ou ocorreu um erro na busca.")

@st.dialog("Novo Cadastro de Motorista (SIL / Massa)")
def modal_cadastro_sil(user):
    with st.form("cadastro_motorista_modal", clear_on_submit=True):
        cpf = st.text_input("Informe o CPF do Motorista")
        st.caption("Pressione 'Consultar e Cadastrar' para incluir. O campo será limpo para o próximo CPF.")
        submit_sil = st.form_submit_button("Consultar e Cadastrar", use_container_width=True)
        
        if submit_sil:
            if not cpf:
                st.error("O CPF é obrigatório.")
            elif not services.validar_cpf(cpf):
                st.error("❌ CPF Inválido.")
            else:
                existe, valida, data_exp, nome_ex, status_sil, data_consulta_sil = services.verificar_validade_existente(cpf, user['empresa_id'])
                if existe:
                    st.warning(f"⚠️ {nome_ex} já está cadastrado no sistema.")
                    if status_sil and data_consulta_sil:
                        styles.render_sil_status(status_sil, data_consulta_sil)
                else:
                    fazer_consulta_sil(cpf, user)
    
    st.divider()
    st.divider()
    st.subheader("📁 Importação em Massa")
    with st.form("form_import_mass_cpfs", clear_on_submit=True):
        uploaded_file = st.file_uploader("Arquivo Excel, PDF ou TXT com CPFs", type=["xlsx", "xls", "pdf", "txt"])
        submit_import = st.form_submit_button("🚀 Iniciar Importação", use_container_width=True)
        
        if submit_import and uploaded_file:
            with st.spinner("Processando..."):
                ext = uploaded_file.name.split('.')[-1].lower()
                if ext == 'pdf':
                    sucesso, msg = services.importar_motoristas_pdf(uploaded_file, user['empresa_id'], user['nome'])
                elif ext == 'txt':
                    sucesso, msg = services.importar_motoristas_txt(uploaded_file, user['empresa_id'], user['nome'])
                else:
                    sucesso, msg = services.importar_motoristas_excel(uploaded_file, user['empresa_id'], user['nome'])
                    
                if sucesso:
                    st.success("Importação concluída com sucesso!")
                    with st.expander("📋 Ver Detalhes da Importação", expanded=True):
                        st.markdown(msg)
                else: 
                    st.error(msg)
        elif submit_import and not uploaded_file:
            st.warning("Selecione um arquivo antes de iniciar a importação.")
            
    st.divider()
    if st.button("Fechar", key="btn_fechar_modal_mot", use_container_width=True):
        st.session_state.mot_form_open = False
        st.rerun()

def fazer_consulta_sil(cpf, user):
    with st.spinner("Consultando Opentech..."):
        res = services.consultar_opentech(cpf, "TOKEN", usuario_nome=user['nome'])
        if "Erro" in res['status']:
            st.error(f"Erro na Opentech: {res['status']}")
        else:
            st.write(f"**Nome:** {res['nome']} | **CNH:** {res['cnh']}")
            styles.render_sil_status(res['status'], res['data_consulta'])
            
            dados = {
                'nome': res['nome'], 'cpf': cpf, 'cnh': res['cnh'], 
                'categoria': res['categoria'], 'status_sil': res['status'],
                'data_consulta_sil': res['data_consulta'], 'validade': res['validade']
            }
            sucesso, msg = services.cadastrar_motorista(dados, user['empresa_id'])
            if sucesso: 
                st.markdown(f"<small style='color: #666;'>✅ {res['nome']} incluído. Pode digitar o próximo.</small>", unsafe_allow_html=True)
            else: 
                st.error(msg)

def render_motoristas(user):
    st.header("Controle de Portaria")
    
    col_t, col_btn = st.columns([3, 1])
    if "mot_form_open" not in st.session_state:
        st.session_state.mot_form_open = False
        
    with col_btn:
        if st.button("➕ Novo Cadastro (SIL)", use_container_width=True, type="primary"):
            st.session_state.mot_form_open = True
            st.rerun()
            
    if st.session_state.mot_form_open:
        modal_cadastro_sil(user)
            
    busca = st.text_input("🔎 Consultar CPF ou Nome do Motorista")
    
    # Se digitar um CPF completo, consulta SIL caso não exista no banco local
    if busca:
        cpf_limpo_busca = ''.join(filter(str.isdigit, busca))
        if len(cpf_limpo_busca) == 11:
            conn = services.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM motoristas WHERE cpf = %s AND empresa_id = %s", (cpf_limpo_busca, user['empresa_id']))
            mot_local = cursor.fetchone()
            conn.close()
            
            if not mot_local:
                with st.spinner(f"CPF não encontrado localmente. Consultando SIL para {cpf_limpo_busca}..."):
                    res_sil = services.consultar_opentech(cpf_limpo_busca, "TOKEN", usuario_nome=user['nome'])
                    if "Erro" not in res_sil['status']:
                        dados = {
                            'nome': res_sil['nome'], 'cpf': cpf_limpo_busca, 'cnh': res_sil['cnh'], 
                            'categoria': res_sil['categoria'],
                            'status_sil': res_sil['status'],
                            'data_consulta_sil': res_sil['data_consulta'],
                            'validade': res_sil['validade']
                        }
                        services.cadastrar_motorista(dados, user['empresa_id'])
                        
    motoristas = services.listar_motoristas(user['empresa_id'], busca)
    
    if motoristas:
        cpf_limpo_busca = ''.join(filter(str.isdigit, busca))
        if len(cpf_limpo_busca) == 11:
            for mot in motoristas:
                if ''.join(filter(str.isdigit, mot['cpf'])) == cpf_limpo_busca:
                    services.registrar_consulta_portaria(mot['id'], mot['cpf'], mot['status_sil'], user['id'], user['empresa_id'])
                    break

        for mot in motoristas:
            validade_label = services.formatar_data_validade(mot['data_expiracao'])
            with st.expander(f"{mot['nome']} - {mot['cpf']} | {validade_label}"):
                mot_data, historico, recentes = services.get_prontuario(mot['id'], user['empresa_id'])
                
                col_det, col_upd = st.columns([2, 1])
                with col_det:
                    st.subheader("Verificação de Entrada")
                    styles.render_driver_badge(mot['status_interno'], recentes)
                    st.write(f"**CNH:** {mot['cnh']} | **Cat:** {mot['categoria']}")
                    styles.render_sil_status(mot['status_sil'], mot['data_consulta_sil'])
                
                with col_upd:
                    if st.button("🔄 Atualizar SIL", key=f"upd_{mot['id']}", use_container_width=True):
                        with st.spinner("Atualizando..."):
                            ok, msg = services.atualizar_sil_motorista(mot['id'], mot['cpf'], user['empresa_id'], user['nome'])
                            if ok: st.success(msg); st.rerun()
                            else: st.error(msg)
    else:
        if busca: st.warning("Motorista não encontrado.")

def render_veiculos(user):
    st.header("Controle de Mapa")
    
    col_t, col_btn = st.columns([3, 1])
    if "veic_form_open" not in st.session_state:
        st.session_state.veic_form_open = False
        
    with col_btn:
        if st.button("➕ Novo Cadastro de Veículo", use_container_width=True, type="primary"):
            st.session_state.veic_form_open = True
            st.rerun()
            
    if st.session_state.veic_form_open:
        modal_cadastro_veiculo(user)
            
    busca = st.text_input("🔎 Consultar Placa")
    
    # Se houver busca de placa, atualiza os dados direto do SIL primeiro
    if busca:
        busca_limpa = busca.upper().replace("-", "").strip()
        
        if busca_limpa == "DOG0001":
            st.image("https://media.tenor.com/7bZfH9jZ9bYAAAAC/french-bulldog-running.gif", caption="A carga está segura, mestre!")
            st.balloons()
            return
        # Expressão regular simples para validar placa (padrão antigo ABC-1234 ou Mercosul ABC1D23)
        if re.match(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$", busca_limpa):
            # Procura se o veículo já existe cadastrado no banco de dados local
            conn = services.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM veiculos WHERE placa = %s AND empresa_id = %s", (busca_limpa, user['empresa_id']))
            veiculo_local = cursor.fetchone()
            conn.close()
            
            with st.spinner(f"Consultando SIL para placa {busca_limpa}..."):
                if veiculo_local:
                    # Se já existia, atualiza os dados em tempo real na base
                    services.atualizar_sil_veiculo(veiculo_local['id'], busca_limpa, user['empresa_id'], user['nome'])
                else:
                    # Se não existia, consulta o SIL e cadastra o veículo automaticamente
                    res_sil = services.consultar_opentech_veiculo(busca_limpa, "BUSCA_DIRETA", usuario_nome=user['nome'])
                    if "Erro" not in res_sil['status']:
                        services.cadastrar_veiculo(res_sil, user['empresa_id'])
                        
    veiculos = services.listar_veiculos(user['empresa_id'], busca)
    
    if veiculos:
        for v in veiculos:
            # Extrair validade do checklist para exibição no título (Ex: "Aprovado (Até 06/07/2026)" -> "Até 06/07/2026")
            checklist_expira = "N/I"
            checklist_bruto = v.get('status_checklist', 'N/I')
            if "Até" in checklist_bruto:
                match = re.search(r"Até\s+([^)]+)", checklist_bruto)
                if match:
                    checklist_expira = match.group(1).strip()
            
            # Formatar e organizar labels
            validade_veic = services.formatar_data_validade(v['validade'])
            rastreadores_label = v.get('rastreadores', 'N/I')
            seg_rastreador = v.get('segundo_rastreador', 'Não possui')
            
            # Título resumido para a linha do expander
            ultima_pos = v.get('ultima_posicao', 'N/I')
            titulo_linha = (
                f"🚗 {v['placa']} ({v['tipo_veiculo']}) | "
                f"Última Pos: {ultima_pos} | "
                f"Val. Veículo: {validade_veic} | "
                f"Val. Checklist: {checklist_expira} | "
                f"Rastreador: {rastreadores_label} | "
                f"Secundário: {seg_rastreador}"
            )
            
            with st.expander(titulo_linha):
                col_det, col_upd = st.columns([2, 1])
                with col_det:
                    styles.render_sil_status(v['status_sil'], v['data_consulta'])
                    st.markdown(f"**Última Posição:** {v['ultima_posicao']}")
                    st.markdown(f"**Checklist:** {v['status_checklist']}")
                    st.markdown(f"**Rastreadores:** {v.get('rastreadores', 'N/I')}")
                    
                    seg = v.get('segundo_rastreador', 'Não possui')
                    if seg != "Não possui":
                        st.markdown(f"**Tecnologia autorizada p/ rastreador Secundário:** :green[{seg}]")
                    else:
                        st.markdown(f"**Tecnologia autorizada p/ rastreador Secundário:** :red[{seg}]")
                
                with col_upd:
                    if st.button("🔄 Atualizar SIL", key=f"upd_v_{v['id']}", use_container_width=True):
                        with st.spinner("Atualizando..."):
                            ok, msg = services.atualizar_sil_veiculo(v['id'], v['placa'], user['empresa_id'], user['nome'])
                            if ok: st.success(msg); st.rerun()
                            else: st.error(msg)
    else:
        if busca: st.warning("Veículo não encontrado.")

@st.dialog("Novo Cadastro de Veículo (SIL / Massa)")
def modal_cadastro_veiculo(user):
    with st.form("cadastro_veiculo_modal", clear_on_submit=True):
        placa = st.text_input("Informe a Placa do Veículo")
        st.caption("Pressione 'Consultar e Cadastrar' para incluir. O campo será limpo para a próxima placa.")
        submit_sil = st.form_submit_button("Consultar e Cadastrar", use_container_width=True)
        
        if submit_sil:
            if not placa:
                st.error("A placa é obrigatória.")
            else:
                existe, validade, status_sil, data_consulta_sil = services.verificar_validade_existente_veiculo(placa, user['empresa_id'])
                if existe:
                    st.warning(f"⚠️ A placa {placa.upper()} já está cadastrada no sistema.")
                    if status_sil and data_consulta_sil:
                        styles.render_sil_status(status_sil, data_consulta_sil)
                else:
                    with st.spinner("Consultando Opentech..."):
                        res = services.consultar_opentech_veiculo(placa, "TOKEN", usuario_nome=user['nome'])
                        if "Erro" in res['status']:
                            st.error(f"Erro na Opentech: {res['status']}")
                        else:
                            st.write(f"**Tipo:** {res['tipo_veiculo']}")
                            styles.render_sil_status(res['status'], res['data_consulta'])
                            st.markdown(f"**Última Posição:** {res['ultima_posicao']}")
                            st.markdown(f"**Checklist:** {res['checklist']}")
                            
                            sucesso, msg = services.cadastrar_veiculo(res, user['empresa_id'])
                            if sucesso: 
                                st.markdown(f"<small style='color: #666;'>✅ Veículo {res['placa']} incluído.</small>", unsafe_allow_html=True)
                            else: 
                                st.error(msg)
                                
    st.divider()
    st.divider()
    st.subheader("📁 Importação em Massa (Placas)")
    with st.form("form_import_mass_veiculos", clear_on_submit=True):
        uploaded_file = st.file_uploader("Arquivo Excel, PDF ou TXT com Placas", type=["xlsx", "xls", "pdf", "txt"])
        submit_import = st.form_submit_button("🚀 Iniciar Importação de Veículos", use_container_width=True)
        
        if submit_import and uploaded_file:
            with st.spinner("Processando..."):
                ext = uploaded_file.name.split('.')[-1].lower()
                if ext == 'pdf':
                    sucesso, msg = services.importar_veiculos_pdf(uploaded_file, user['empresa_id'], user['nome'])
                elif ext == 'txt':
                    sucesso, msg = services.importar_veiculos_txt(uploaded_file, user['empresa_id'], user['nome'])
                else:
                    sucesso, msg = services.importar_veiculos_excel(uploaded_file, user['empresa_id'], user['nome'])
                    
                if sucesso:
                    st.success("Importação concluída com sucesso!")
                    with st.expander("📋 Ver Detalhes da Importação", expanded=True):
                        st.markdown(msg)
                else: 
                    st.error(msg)
        elif submit_import and not uploaded_file:
            st.warning("Selecione um arquivo antes de iniciar a importação.")
            
    st.divider()
    if st.button("Fechar", key="btn_fechar_modal_veic", use_container_width=True):
        st.session_state.veic_form_open = False
        st.rerun()


@st.cache_data
def load_cidades():
    try:
        import json
        with open("cidades_opentech.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

CIDADES_CONHECIDAS = load_cidades()

ESTADOS_BR = [
    "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
    "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"
]

@st.dialog("Solicitar Autorização de Embarque (AE)", width="large")
def modal_criar_ae(user):
    import services
    st.caption("Cadastre e ative uma Autorização de Embarque (AE) na Opentech usando o mínimo de dados.")

    def _format_cpf():
        val = st.session_state.get("ae_cpf", "")
        limpo = ''.join(filter(str.isdigit, val))
        if len(limpo) == 11:
            st.session_state.ae_cpf = f"{limpo[:3]}.{limpo[3:6]}.{limpo[6:9]}-{limpo[9:]}"
        else:
            st.session_state.ae_cpf = limpo

    def _format_placa():
        val = st.session_state.get("ae_placa", "")
        limpo = val.replace("-", "").strip().upper()
        if len(limpo) == 7:
            st.session_state.ae_placa = f"{limpo[:3]}-{limpo[3:]}"
        else:
            st.session_state.ae_placa = limpo

    def _format_placa_carreta():
        val = st.session_state.get("ae_placa_carreta", "")
        limpo = val.replace("-", "").strip().upper()
        if len(limpo) == 7:
            st.session_state.ae_placa_carreta = f"{limpo[:3]}-{limpo[3:]}"
        else:
            st.session_state.ae_placa_carreta = limpo

    # ── Inicializar session_state ──
    for chave, valor_padrao in [
        ("ae_mot_nome", None), ("ae_veic_tipo", None),
        ("ae_buscou_mot", False), ("ae_buscou_veic", False),
    ]:
        if chave not in st.session_state:
            st.session_state[chave] = valor_padrao

    with st.container(border=True):
        st.markdown("🪄 **Colar Dados Rápidos (WhatsApp)**")
        st.caption("Cole a mensagem do motorista aqui para extrair automaticamente CPF, Placa, Carreta e Isca.")
        texto_colado = st.text_area("Texto livre:", height=100, placeholder="Ex: CPF 123.456.789-00 Placa ABC-1234 Carreta BRA2E19 Isca 12345", label_visibility="collapsed")
        if st.button("Extrair Dados Mágicos ✨", use_container_width=True):
            if texto_colado:
                if "solta o cachorro" in texto_colado.lower():
                    st.balloons()
                    st.success("🐶 Mascote ativado! Um ótimo dia de monitoramento pra você!")
                dados_extraidos = services.extrair_dados_texto(texto_colado)
                
                if dados_extraidos.get('cpf'):
                    st.session_state.ae_cpf = dados_extraidos['cpf']
                if dados_extraidos.get('placa'):
                    st.session_state.ae_placa = dados_extraidos['placa']
                if dados_extraidos.get('placa_carreta'):
                    st.session_state.ae_placa_carreta = dados_extraidos['placa_carreta']
                if dados_extraidos.get('isca'):
                    st.session_state.ae_numero_isca = dados_extraidos['isca']
                
                st.success("✅ Dados extraídos com sucesso!")
                import time
                time.sleep(1)
                st.rerun()

    # ── CPF do Motorista ──
    st.markdown("**👤 Motorista**")
    col_cpf, col_btn_cpf = st.columns([3, 1])
    with col_cpf:
        cpf_input = st.text_input(
            "CPF (apenas números)", placeholder="000.000.000-00",
            key="ae_cpf", on_change=_format_cpf, label_visibility="collapsed"
        )
    with col_btn_cpf:
        st.write("")
        buscar_mot = st.button("🔍 Buscar", key="btn_buscar_mot", use_container_width=True)

    if buscar_mot:
        st.session_state.ae_buscou_mot = True
        cpf_digits = ''.join(filter(str.isdigit, cpf_input or ""))
        if len(cpf_digits) == 11:
            mot = services.buscar_motorista_por_cpf(cpf_input, user['empresa_id'])
            if mot:
                st.session_state.ae_mot_nome = mot['nome']
            else:
                with st.spinner("Buscando motorista no SIL (Opentech)..."):
                    res_sil = services.consultar_opentech(cpf_digits, "TOKEN", usuario_nome=user['nome'])
                    if res_sil and res_sil.get("nome") and res_sil.get("nome") != "Erro" and res_sil.get("nome") != "Erro Fatal" and res_sil.get("nome") != "Não Identificado":
                        st.session_state.ae_mot_nome = res_sil["nome"]
                        dados_salvar = {
                            "nome": res_sil["nome"],
                            "cpf": cpf_digits,
                            "cnh": res_sil.get("cnh", "N/I"),
                            "categoria": res_sil.get("categoria", "N/I"),
                            "status_sil": res_sil.get("status", "Sem Informação"),
                            "data_consulta_sil": res_sil.get("data_consulta"),
                            "validade": res_sil.get("validade", "N/I")
                        }
                        services.cadastrar_motorista(dados_salvar, user['empresa_id'])
                    else:
                        st.session_state.ae_mot_nome = None
                        erro_msg = res_sil.get("status", "") if res_sil else ""
                        st.error(f"⛔ Motorista não encontrado. Detalhe SIL: {erro_msg}")
        else:
            st.warning("⚠️ Digite um CPF válido com 11 dígitos antes de buscar.")

    if st.session_state.ae_mot_nome:
        st.success(f"✅ **{st.session_state.ae_mot_nome}** identificado.")
    elif st.session_state.ae_buscou_mot and not st.session_state.ae_mot_nome:
        st.error("❌ Motorista não encontrado no banco local nem no SIL.")

    st.divider()

    # ── Placa do Cavalo ──
    st.markdown("**🚛 Veículo (Cavalo)**")
    col_placa, col_btn_placa = st.columns([3, 1])
    with col_placa:
        placa_cavalo = st.text_input(
            "Placa (7 dígitos)", placeholder="ABC-1D23",
            key="ae_placa", on_change=_format_placa, label_visibility="collapsed"
        )
    with col_btn_placa:
        st.write("")
        buscar_veic = st.button("🔍 Buscar", key="btn_buscar_veic", use_container_width=True)

    if buscar_veic:
        st.session_state.ae_buscou_veic = True
        placa_digits = (placa_cavalo or "").replace("-", "").strip().upper()
        if len(placa_digits) == 7:
            veic = services.buscar_veiculo_por_placa(placa_cavalo, user['empresa_id'])
            if veic and (veic.get('status_checklist') in ['N/I', None, ''] or veic.get('ultima_posicao') in ['N/I', None, '']):
                veic = None

            if veic:
                st.session_state.ae_veic_tipo = veic.get('tipo_veiculo', 'N/I')
                st.session_state.ae_veic_pos = veic.get('ultima_posicao', 'N/I')
                st.session_state.ae_veic_check = veic.get('status_checklist', 'N/I')
                st.session_state.ae_veic_validade = veic.get('validade', 'N/I')
            else:
                with st.spinner("Buscando veículo no SIL (Opentech)..."):
                    res_sil = services.consultar_opentech_veiculo(placa_digits, "TOKEN", usuario_nome=user['nome'])
                    if res_sil and res_sil.get("status") and "Erro" not in res_sil.get("status"):
                        st.session_state.ae_veic_tipo = res_sil.get("tipo_veiculo", "N/I")
                        st.session_state.ae_veic_pos = res_sil.get("ultima_posicao", "N/I")
                        st.session_state.ae_veic_check = res_sil.get("checklist", "N/I")
                        st.session_state.ae_veic_validade = res_sil.get("validade", "N/I")
                        dados_salvar = {
                            "placa": placa_digits,
                            "tipo_veiculo": res_sil.get("tipo_veiculo", "N/I"),
                            "status": res_sil.get("status", "Sem Informação"),
                            "validade": res_sil.get("validade", "N/I"),
                            "ultima_posicao": res_sil.get("ultima_posicao", "N/I"),
                            "checklist": res_sil.get("checklist", "N/I"),
                            "data_consulta": res_sil.get("data_consulta"),
                            "rastreadores": res_sil.get("rastreadores", "N/I"),
                            "segundo_rastreador": res_sil.get("segundo_rastreador", "Não possui")
                        }
                        services.cadastrar_veiculo(dados_salvar, user['empresa_id'])
                    else:
                        st.session_state.ae_veic_tipo = None
                        st.session_state.ae_veic_pos = None
                        st.session_state.ae_veic_check = None
                        st.session_state.ae_veic_validade = None
        else:
            st.warning("⚠️ Digite a placa completa (7 caracteres) antes de buscar.")

    if st.session_state.get("ae_veic_tipo"):
        st.success(f"✅ **{(placa_cavalo or '').upper()}** — {st.session_state.ae_veic_tipo}")
        st.caption(f"📍 Última Posição: {st.session_state.get('ae_veic_pos', 'N/I')} | 📋 Checklist: {st.session_state.get('ae_veic_check', 'N/I')} | 📅 Validade: {st.session_state.get('ae_veic_validade', 'N/I')}")
    elif st.session_state.get("ae_buscou_veic") and not st.session_state.get("ae_veic_tipo"):
        st.error("❌ Veículo não encontrado no banco local nem no SIL.")

    # ── Placa da Carreta ──
    st.markdown("**🚛 Veículo (Carreta - Opcional)**")
    col_placa_c, col_btn_placa_c = st.columns([3, 1])
    with col_placa_c:
        placa_carreta = st.text_input(
            "Placa da Carreta (7 dígitos)", placeholder="XYZ-9A99",
            key="ae_placa_carreta", on_change=_format_placa_carreta, label_visibility="collapsed"
        )
    with col_btn_placa_c:
        st.write("")
        buscar_carreta = st.button("🔍 Buscar", key="btn_buscar_carreta", use_container_width=True)

    if buscar_carreta:
        st.session_state.ae_buscou_carreta = True
        placa_carreta_digits = (placa_carreta or "").replace("-", "").strip().upper()
        if len(placa_carreta_digits) == 7:
            veic = services.buscar_veiculo_por_placa(placa_carreta, user['empresa_id'])
            if veic and (veic.get('status_checklist') in ['N/I', None, ''] or veic.get('ultima_posicao') in ['N/I', None, '']):
                veic = None

            if veic:
                st.session_state.ae_carreta_tipo = veic.get('tipo_veiculo', 'N/I')
                st.session_state.ae_carreta_pos = veic.get('ultima_posicao', 'N/I')
                st.session_state.ae_carreta_check = veic.get('status_checklist', 'N/I')
                st.session_state.ae_carreta_validade = veic.get('validade', 'N/I')
            else:
                with st.spinner("Buscando carreta no SIL (Opentech)..."):
                    res_sil = services.consultar_opentech_veiculo(placa_carreta_digits, "TOKEN", usuario_nome=user['nome'])
                    if res_sil and res_sil.get("status") and "Erro" not in res_sil.get("status"):
                        st.session_state.ae_carreta_tipo = res_sil.get("tipo_veiculo", "N/I")
                        st.session_state.ae_carreta_pos = res_sil.get("ultima_posicao", "N/I")
                        st.session_state.ae_carreta_check = res_sil.get("checklist", "N/I")
                        st.session_state.ae_carreta_validade = res_sil.get("validade", "N/I")
                        dados_salvar = {
                            "placa": placa_carreta_digits,
                            "tipo_veiculo": res_sil.get("tipo_veiculo", "N/I"),
                            "status": res_sil.get("status", "Sem Informação"),
                            "validade": res_sil.get("validade", "N/I"),
                            "ultima_posicao": res_sil.get("ultima_posicao", "N/I"),
                            "checklist": res_sil.get("checklist", "N/I"),
                            "data_consulta": res_sil.get("data_consulta"),
                            "rastreadores": res_sil.get("rastreadores", "N/I"),
                            "segundo_rastreador": res_sil.get("segundo_rastreador", "Não possui")
                        }
                        services.cadastrar_veiculo(dados_salvar, user['empresa_id'])
                    else:
                        st.session_state.ae_carreta_tipo = None
                        st.session_state.ae_carreta_pos = None
                        st.session_state.ae_carreta_check = None
                        st.session_state.ae_carreta_validade = None
        else:
            st.warning("⚠️ Digite a placa completa (7 caracteres) antes de buscar.")

    if st.session_state.get("ae_carreta_tipo"):
        st.success(f"✅ **{(placa_carreta or '').upper()}** — {st.session_state.ae_carreta_tipo}")
        st.caption(f"📍 Última Posição: {st.session_state.get('ae_carreta_pos', 'N/I')} | 📋 Checklist: {st.session_state.get('ae_carreta_check', 'N/I')} | 📅 Validade: {st.session_state.get('ae_carreta_validade', 'N/I')}")
    elif st.session_state.get("ae_buscou_carreta") and not st.session_state.get("ae_carreta_tipo"):
        st.error("❌ Carreta não encontrada no banco local nem no SIL.")

    st.divider()

    # ── Rota ──
    st.markdown("**🗺️ Rota da Viagem**")

    col_orig_uf, col_orig_cid = st.columns([1, 2])
    with col_orig_uf:
        orig_uf = st.selectbox("UF", ESTADOS_BR, index=ESTADOS_BR.index("PR"), key="ae_orig_uf_sel", label_visibility="visible")
    with col_orig_cid:
        cids_orig = list(CIDADES_CONHECIDAS.get(orig_uf, {}).keys()) + ["Outra cidade..."]
        orig_cid_sel = st.selectbox("Cidade de Origem", cids_orig, index=None, placeholder="Selecione...", key="ae_orig_cid_sel")

    if orig_cid_sel == "Outra cidade...":
        orig_cid_txt = st.text_input("Nome da cidade de origem", key="ae_orig_txt", placeholder="Ex: Pinhais")
        cd_cidade_origem = 9999
        nome_origem = f"{orig_cid_txt}/{orig_uf}" if orig_cid_txt else f"Genérico/{orig_uf}"
    elif orig_cid_sel:
        cd_cidade_origem = CIDADES_CONHECIDAS.get(orig_uf, {}).get(orig_cid_sel, 9999)
        nome_origem = f"{orig_cid_sel}/{orig_uf}"
    else:
        cd_cidade_origem = 9999
        nome_origem = f"Não informada/{orig_uf}"

    col_dest_uf, col_dest_cid = st.columns([1, 2])
    with col_dest_uf:
        dest_uf = st.selectbox("UF", ESTADOS_BR, index=ESTADOS_BR.index("SP"), key="ae_dest_uf_sel", label_visibility="visible")
    with col_dest_cid:
        cids_dest = list(CIDADES_CONHECIDAS.get(dest_uf, {}).keys()) + ["Outra cidade..."]
        dest_cid_sel = st.selectbox("Cidade de Destino", cids_dest, index=None, placeholder="Selecione...", key="ae_dest_cid_sel")

    if dest_cid_sel == "Outra cidade...":
        dest_cid_txt = st.text_input("Nome da cidade de destino", key="ae_dest_txt", placeholder="Ex: Guarujá")
        cd_cidade_destino = 9999
        nome_destino = f"{dest_cid_txt}/{dest_uf}" if dest_cid_txt else f"Genérico/{dest_uf}"
    elif dest_cid_sel:
        cd_cidade_destino = CIDADES_CONHECIDAS.get(dest_uf, {}).get(dest_cid_sel, 9999)
        nome_destino = f"{dest_cid_sel}/{dest_uf}"
    else:
        cd_cidade_destino = 9999
        nome_destino = f"Não informada/{dest_uf}"

    btn_buscar_rotas = st.button("🗺️ Buscar Rotas Disponíveis", use_container_width=True)
    if btn_buscar_rotas:
        with st.spinner("Buscando rotas na Opentech..."):
            rotas_encontradas = services.buscar_rota_especifica(cd_cidade_origem, cd_cidade_destino)
            eh_erro = isinstance(rotas_encontradas, dict) and "error" in rotas_encontradas
            eh_vazio = isinstance(rotas_encontradas, list) and len(rotas_encontradas) == 0

            if eh_erro or eh_vazio:
                todas_rotas = services.buscar_rotas_opentech()
                if todas_rotas and isinstance(todas_rotas, list) and len(todas_rotas) > 0:
                    rotas_encontradas = todas_rotas
                else:
                    rotas_encontradas = []

            if isinstance(rotas_encontradas, list) and len(rotas_encontradas) > 0:
                st.session_state.ae_rotas_opcoes = {f"{r['ds_rota']} (Cód: {r['cd_rota']})": r['cd_rota'] for r in rotas_encontradas}
                total = len(rotas_encontradas)
                if eh_vazio or eh_erro:
                    st.info(f"👉 Exibindo as {total} rotas da Opentech. Pesquise pelo nome ou número.")
                else:
                    st.success(f"✅ Exibindo as {total} rotas da Opentech. Pesquise pelo nome ou número.")
            else:
                st.session_state.ae_rotas_opcoes = {"Rota Padrão / Sem Rota Fixa (Cód: -1)": -1}
                st.warning("⚠️ Nenhuma rota localizada na Opentech. Usando Rota Padrão (Cód: -1).")

    if "ae_rotas_opcoes" not in st.session_state:
        st.session_state.ae_rotas_opcoes = {"Rota Padrão / Sem Rota Fixa (Cód: -1)": -1}

    st.divider()

    # ── Formulário para Carga, Isca, Datas e Submissão ──
    with st.form("ae_express_form", clear_on_submit=False, enter_to_submit=False):
        col_rota_api, col_rota_man = st.columns([2, 1])
        with col_rota_api:
            rota_selecionada = st.selectbox("Selecione a Rota Oficial", list(st.session_state.ae_rotas_opcoes.keys()))
            cd_rota_api = st.session_state.ae_rotas_opcoes[rota_selecionada]
        with col_rota_man:
            cd_rota_manual = st.text_input("Código da Rota Manual", placeholder="Ex: 86147", help="Se a API não achar rotas e o código -1 for rejeitado, digite o código exato aqui.")

        if cd_rota_manual and cd_rota_manual.strip().isdigit() and cd_rota_manual.strip() != "-1":
            cd_rota_final = int(cd_rota_manual.strip())
            st.info(f"Usando código de rota manual: {cd_rota_final}")
        else:
            cd_rota_final = cd_rota_api

        cnpj_origem = ""
        cnpj_destino = ""

        if "ae_valor_carga_str" not in st.session_state:
            st.session_state.ae_valor_carga_str = "50.000,00"

        valor_carga_str = st.text_input("Valor da Carga (R$)", key="ae_valor_carga_str")
        try:
            import re as _re
            v_str = valor_carga_str.replace("R$", "").strip()
            if "," in v_str:
                v_limpo = v_str.replace(".", "").replace(",", ".")
            else:
                if _re.match(r"^\d+\.\d{1,2}$", v_str):
                    v_limpo = v_str
                else:
                    v_limpo = v_str.replace(".", "")
            valor_carga = float(v_limpo)
        except Exception:
            valor_carga = 50000.0

        st.caption("ℹ️ **Produto fixado:** E-commerce")
        numero_isca = st.text_input("Número da Isca (Opcional)", placeholder="Ex: ISCA998877", key="ae_numero_isca")

        col_d_ini, col_h_ini = st.columns(2)
        with col_d_ini:
            data_prev_ini = st.date_input("Previsão de Início", datetime.now().date(), key="d_ini")
        with col_h_ini:
            hora_prev_ini = st.time_input("Hora de Início", datetime.now().time(), key="h_ini")
        previsao_inicio_dt = datetime.combine(data_prev_ini, hora_prev_ini)

        col_d_fim, col_h_fim = st.columns(2)
        with col_d_fim:
            data_prev_fim = st.date_input("Previsão de Fim", datetime.now().date() + timedelta(days=1), key="d_fim")
        with col_h_fim:
            hora_prev_fim = st.time_input("Hora de Fim", datetime.now().time(), key="h_fim")
        previsao_fim_dt = datetime.combine(data_prev_fim, hora_prev_fim)

        if user.get('role', '').lower().startswith('admin'):
            modo_simulacao = st.checkbox("Modo de Simulação (Recomendado para Testes)", value=True)
        else:
            modo_simulacao = False

        submit_ae = st.form_submit_button("🚀 Iniciar Monitoramento de Viagem", use_container_width=True)

        if submit_ae:
            cpf_final  = st.session_state.get("ae_cpf", "")
            placa_final = st.session_state.get("ae_placa", "")
            placa_carreta_final = st.session_state.get("ae_placa_carreta", "")
            cpf_digits  = ''.join(filter(str.isdigit, cpf_final))
            placa_limpa = placa_final.replace("-", "").strip()

            if not cpf_digits or len(cpf_digits) < 3:
                st.error("⚠️ O CPF do motorista é obrigatório.")
            elif len(placa_limpa) != 7:
                st.error("⚠️ A placa do cavalo é obrigatória e deve ter 7 dígitos.")
            elif previsao_fim_dt <= previsao_inicio_dt:
                st.error("❌ A previsão de fim deve ser posterior à previsão de início.")
            else:
                dados_ae = {
                    "cpf_motorista": cpf_final,
                    "placa_cavalo": placa_final,
                    "placa_carreta": placa_carreta_final,
                    "origem_nome": nome_origem,
                    "destino_nome": nome_destino,
                    "cd_cidade_origem": cd_cidade_origem,
                    "cd_cidade_destino": cd_cidade_destino,
                    "cnpj_origem": cnpj_origem,
                    "cnpj_destino": cnpj_destino,
                    "valor_carga": valor_carga,
                    "numero_isca": numero_isca,
                    "previsao_inicio": previsao_inicio_dt,
                    "previsao_fim": previsao_fim_dt,
                    "cd_rota": cd_rota_final
                }
                with st.spinner("Registrando monitoramento..."):
                    sucesso, msg = services.criar_ae_express(dados_ae, user['empresa_id'], user['id'], modo_simulacao)
                    if sucesso:
                        import re as _re
                        _match = _re.search(r'AE\s*#?(\d+)', msg)
                        if _match:
                            st.session_state.ae_ultimo_cd_viagem = int(_match.group(1))
                            st.session_state.ae_ultimo_dados = {
                                "cpf_motorista": cpf_digits,
                                "nome_motorista": st.session_state.get("ae_mot_nome", ""),
                                "placa_cavalo": placa_limpa,
                                "placa_carreta": placa_carreta_final,
                                "origem": nome_origem,
                                "destino": nome_destino,
                                "valor_carga": valor_carga,
                                "produto": "E-commerce",
                                "numero_isca": numero_isca,
                                "previsao_inicio": str(previsao_inicio_dt),
                                "previsao_fim": str(previsao_fim_dt),
                                "status": "Ativa (Simulada)" if modo_simulacao else "Ativa",
                            }
                        st.session_state.ae_mot_nome = None
                        st.session_state.ae_veic_tipo = None
                        st.session_state.ae_carreta_tipo = None
                        st.session_state.ae_buscou_mot = False
                        st.session_state.ae_buscou_veic = False
                        st.session_state.ae_buscou_carreta = False
                        if "ae_rotas_opcoes" in st.session_state:
                            del st.session_state.ae_rotas_opcoes
                        st.session_state.ae_form_open = False
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)

    st.divider()
    if st.button("Fechar / Cancelar", key="btn_fechar_modal_ae", use_container_width=True):
        st.session_state.ae_form_open = False
        st.session_state.ae_mot_nome = None
        st.session_state.ae_veic_tipo = None
        st.session_state.ae_carreta_tipo = None
        st.session_state.ae_buscou_mot = False
        st.session_state.ae_buscou_veic = False
        st.session_state.ae_buscou_carreta = False
        if "ae_rotas_opcoes" in st.session_state:
            del st.session_state.ae_rotas_opcoes
        st.rerun()



def render_ae_express(user):
    import services
    import streamlit as st

    def _callback_relancar(v):
        import re as _re
        st.session_state.ae_cpf = ''.join(filter(str.isdigit, v['cpf_motorista']))
        st.session_state.ae_placa = v['placa_cavalo']
        st.session_state.ae_placa_carreta = v['placa_carreta'] or ""
        st.session_state.ae_mot_nome = v['nome_motorista']
        st.session_state.ae_buscou_mot = True
        st.session_state.ae_buscou_veic = True
        st.session_state.ae_veic_tipo = "Cavalo (Relançado)"
        if v.get('placa_carreta'):
            st.session_state.ae_buscou_carreta = True
            st.session_state.ae_carreta_tipo = "Carreta (Relançado)"
        
        def parse_cid_uf(s):
            m = _re.match(r"^(.*?)/(..)\s*\((\d+)\)$", s)
            if m: return m.group(1), m.group(2)
            return None, None
            
        cid_o, uf_o = parse_cid_uf(v['origem'])
        if uf_o in ESTADOS_BR:
            st.session_state.ae_orig_uf_sel = uf_o
            if cid_o in CIDADES_CONHECIDAS.get(uf_o, {}):
                st.session_state.ae_orig_cid_sel = cid_o
            else:
                st.session_state.ae_orig_cid_sel = "Outra cidade..."
                st.session_state.ae_orig_txt = cid_o
                
        cid_d, uf_d = parse_cid_uf(v['destino'])
        if uf_d in ESTADOS_BR:
            st.session_state.ae_dest_uf_sel = uf_d
            if cid_d in CIDADES_CONHECIDAS.get(uf_d, {}):
                st.session_state.ae_dest_cid_sel = cid_d
            else:
                st.session_state.ae_dest_cid_sel = "Outra cidade..."
                st.session_state.ae_dest_txt = cid_d
                
        if v.get('valor_carga'):
            st.session_state.ae_valor_carga_str = str(v['valor_carga']).replace('.', ',')
        if v.get('numero_isca'):
            st.session_state.ae_numero_isca = v['numero_isca']
            
        st.session_state.ae_form_open = True
    import streamlit as st
    col_topo1, col_topo2 = st.columns([4, 1])
    with col_topo1:
        st.header("📊 Viagens & Monitoramentos Ativos")
        st.caption("Visualize as autorizações de embarque (AE) criadas ou inicie uma nova.")
    with col_topo2:
        st.write("")
        if "ae_form_open" not in st.session_state:
            st.session_state.ae_form_open = False
            
        if st.button("➕ Novo Monitoramento", type="primary", use_container_width=True):
            # Limpar campos para um novo preenchimento limpo
            for k in ["ae_cpf", "ae_placa", "ae_placa_carreta", "ae_numero_isca", 
                      "ae_mot_nome", "ae_veic_tipo", "ae_carreta_tipo",
                      "ae_buscou_mot", "ae_buscou_veic", "ae_buscou_carreta"]:
                st.session_state[k] = None
            if "ae_rotas_opcoes" in st.session_state:
                del st.session_state.ae_rotas_opcoes
            st.session_state.ae_form_open = True
            st.rerun()

    if st.session_state.ae_form_open:
        modal_criar_ae(user)

    # ── Download PDF da última AE criada ──
    if "ae_ultimo_cd_viagem" in st.session_state and st.session_state.ae_ultimo_cd_viagem:
        cd_v = st.session_state.ae_ultimo_cd_viagem
        st.markdown(f"""<div style='background:linear-gradient(135deg,#1B4332,#2D6A4F);
            padding:16px 20px; border-radius:8px; border-left:6px solid #4CAF50; margin-top:16px; margin-bottom:16px;'>
            <span style='color:#D8F3DC;font-size:13px;font-weight:bold;letter-spacing:1px;'>✅ AE CRIADA COM SUCESSO</span><br>
            <span style='color:white;font-weight:bold;font-size:18px;'>AE #{cd_v} — Pronta para download</span>
        </div>""", unsafe_allow_html=True)
        col_dl, col_cl = st.columns([3, 1])
        with col_dl:
            if st.button("📄 Gerar PDF da AE", key="btn_pdf_ae_topo", use_container_width=True, type="primary"):
                with st.spinner("Gerando PDF..."):
                    pdf_bytes = services.gerar_pdf_ae(
                        cd_v, st.session_state.get("ae_ultimo_dados", {})
                    )
                if pdf_bytes:
                    st.download_button(
                        label=f"⬇️ Baixar AE #{cd_v}.pdf",
                        data=pdf_bytes,
                        file_name=f"AE_{cd_v}_BBMRisk.pdf",
                        mime="application/pdf",
                        use_container_width=True,
                        key="dl_pdf_ae_topo"
                    )
                else:
                    st.error("❌ Não foi possível gerar o PDF. Tente novamente.")
        with col_cl:
            if st.button("✖ Fechar", key="btn_fechar_pdf_banner", use_container_width=True):
                del st.session_state.ae_ultimo_cd_viagem
                del st.session_state.ae_ultimo_dados
                st.rerun()

    busca_ae = st.text_input("🔎 Filtrar por CPF, Placa, Isca ou Cód. Viagem")

    viagens = services.listar_viagens(user['empresa_id'], busca_ae)

    if not viagens:
        st.info("Nenhum monitoramento registrado recentemente.")
    else:
        for v in viagens:
            status = v['status']
            if "Cancelada" in status or "CANCELADA" in status.upper():
                status_badge = '<span class="badge badge-perigo">CANCELADA</span>'
            elif "Baixada" in status or "CONCLU" in status.upper() or "Concluída" in status:
                status_badge = '<span class="badge" style="background-color: #6c757d; color: white;">CONCLUÍDA</span>'
            else:
                status_badge = '<span class="badge badge-sucesso">EM MONITORAMENTO</span>'

            titulo_exp = f"🚚 AE #{v['cd_viagem']} | {v['placa_cavalo']} -> {v['destino'].split('(')[0]} | {status}"

            with st.expander(titulo_exp):
                col_det, col_acoes = st.columns([2, 1])

                with col_det:
                    st.markdown(f"**Motorista:** {v['nome_motorista']} ({v['cpf_motorista']})")
                    st.markdown(f"**Veículos:** Cavalo: `{v['placa_cavalo']}`" + (f" | Carreta: `{v['placa_carreta']}`" if v['placa_carreta'] else ""))
                    st.markdown(f"**Rota:** {v['origem']} ➔ {v['destino']}")
                    st.markdown(f"**Produto:** {v['produto']} | **Valor:** R$ {v['valor_carga']:,.2f}")
                    isca_str = f"`{v['numero_isca']}`" if v.get('numero_isca') else "_Não possui_"
                    st.markdown(f"**Número da Isca:** {isca_str}")
                    prev_fim_str = v.get('previsao_fim') or "_Não informada_"
                    st.caption(f"Início: {v['previsao_inicio']} | Fim: {prev_fim_str} | Cadastro: {v['data_criacao']}")
                
                with col_acoes:
                    st.markdown(status_badge, unsafe_allow_html=True)
                    st.write("")
                    if st.button("Baixar PDF", key=f"btn_pdf_hist_{v['cd_viagem']}", use_container_width=True):
                        with st.spinner("Gerando PDF..."):
                            pdf_bytes = services.gerar_pdf_ae(v['cd_viagem'], v)
                        if pdf_bytes:
                            st.download_button(label="⬇️ Salvar", data=pdf_bytes, file_name=f"AE_{v['cd_viagem']}_BBMRisk.pdf", mime="application/pdf", use_container_width=True, key=f"dl_pdf_hist_{v['cd_viagem']}")
                            
                    if st.button("🔄 Relançar AE", key=f"btn_relancar_{v['cd_viagem']}", use_container_width=True, on_click=_callback_relancar, args=(v,)):
                        pass

# --- EXECUÇÃO ---
qp = st.query_params
if qp.get("mapa_fullscreen") == "1":
    emp_id = qp.get("emp", "")
    if emp_id.isdigit():
        user_mock = {"empresa_id": int(emp_id), "role": "admin"}
        # Aplicar estilos básicos para esconder o restolho do streamlit
        st.markdown("""
            <style>
                header[data-testid="stHeader"] {display: none;}
                [data-testid="collapsedControl"] {display: none;}
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                .block-container {padding-top: 1rem; padding-bottom: 0;}
            </style>
        """, unsafe_allow_html=True)
        render_torre_controle(user_mock, fullscreen=True)
    else:
        st.error("Acesso Inválido")
elif not st.session_state.autenticado:
    login_screen()
else:
    main_app()
