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

# --- GERENCIAMENTO DE SESSÃO ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = None

def login_screen():
    # Aplicar estilo mesmo no login
    styles.apply_custom_branding()
    
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
            <div style="text-align: center; margin-bottom: 25px; margin-top: 40px;">
                <div style="font-size: 3.5rem; filter: drop-shadow(0 0 10px rgba(67,100,247,0.4)); margin-bottom: 10px;">⚡</div>
                <h1 style="font-family: 'Orbitron', sans-serif; font-weight: 900; letter-spacing: 2px; color: var(--text-color); font-size: 2.3rem; margin: 0;">BBM RISK</h1>
                <span style="color: #90a4ae; font-size: 0.95rem; font-weight: 500;">Controle de Portaria & Gestão de Risco</span>
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
        if role == 'portaria':
            opcoes = ["Controle de Portaria", "Controle de Veículos", "Criar Monitoramento"]
        elif role == 'supervisor':
            opcoes = ["Controle de Portaria", "Controle de Veículos", "Criar Monitoramento", "Configurações"]
        elif role.startswith('admin'):
            opcoes = ["Dashboard", "Controle de Portaria", "Controle de Veículos", "Criar Monitoramento", "Configurações"]
        else:
            opcoes = ["Controle de Portaria", "Controle de Veículos", "Criar Monitoramento"]
        
        menu = st.radio("Navegação", opcoes)
        
        st.divider()
        if st.button("Sair"):
            st.session_state.autenticado = False
            st.rerun()

    # Título da Página
    styles.render_header(user)
    st.divider()

    # --- TELAS ---
    if menu == "Dashboard":
        if (user.get('role') or '').lower() == 'portaria':
            st.warning("⚠️ Acesso ao Dashboard não permitido para o usuário da Portaria.")
        else:
            render_dashboard(user)
    elif menu == "Controle de Portaria":
        render_motoristas(user)
    elif menu == "Controle de Veículos":
        render_veiculos(user)
    elif menu == "Criar Monitoramento":
        render_ae_express(user)
    elif menu == "Configurações":
        render_config(user)

def render_dashboard(user):
    stats = services.get_stats_dashboard(user['empresa_id'])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Cadastros Ativos", stats['cadastros_ativos'])
    col2.metric("Cadastros Vencidos", stats['cadastros_vencidos'], delta_color="inverse")
    col3.metric("Liberações Hoje", stats['liberacoes_hoje'])
    
    st.markdown("---")
    st.subheader("📍 Últimas Consultas na Portaria")
    historico = services.listar_historico_acessos(user['empresa_id'])
    
    if historico:
        import pandas as pd
        df_hist = pd.DataFrame(historico)
        df_hist = df_hist[['data_hora', 'cpf', 'motorista_nome', 'status_resultado']]
        df_hist.columns = ['Data/Hora', 'CPF', 'Motorista', 'Status SIL']
        st.dataframe(df_hist, use_container_width=True, hide_index=True)
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

        # ── Abas: Criar Usuário | Gerenciar Usuários ──
        if role == 'admin':
            tabs = st.tabs(["➕ Novo Usuário", "👥 Gerenciar Usuários"])
            tab_criar = tabs[0]
            tab_gerenciar = tabs[1]
        else:
            tab_criar = None
            tab_gerenciar = None
            st.info("🔒 O gerenciamento e visualização de usuários é restrito ao nível Administrador.")

        # ── ABA 1: Criar novo usuário (Apenas Admin) ──
        if tab_criar:
            with tab_criar:
                with st.form("criar_usuario_form"):
                    st.subheader("Criar novo usuário")
                    nome = st.text_input("Nome completo")
                    cpf_raw = st.text_input("CPF (apenas números)", max_chars=11, placeholder="000.000.000-00")
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

@st.dialog("Novo Cadastro via SIL Opentech")
def render_modal_cadastro_sil(user):
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
    st.subheader("📁 Importação em Massa")
    uploaded_file = st.file_uploader("Arquivo Excel, PDF ou TXT com CPFs", type=["xlsx", "xls", "pdf", "txt"])
    if uploaded_file:
        if st.button("🚀 Iniciar Importação"):
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
    abrir_modal = False
    with col_btn:
        if st.button("➕ Novo Cadastro (SIL)", use_container_width=True):
            abrir_modal = True
            
    if abrir_modal:
        render_modal_cadastro_sil(user)
            
    busca = st.text_input("🔎 Consultar CPF ou Nome do Motorista")
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
    st.header("Controle de Veículos")
    
    col_t, col_btn = st.columns([3, 1])
    abrir_modal = False
    with col_btn:
        if st.button("➕ Novo Cadastro de Veículo", use_container_width=True):
            abrir_modal = True
            
    if abrir_modal:
        render_modal_cadastro_veiculo(user)
            
    busca = st.text_input("🔎 Consultar Placa")
    
    # Se houver busca de placa, atualiza os dados direto do SIL primeiro
    if busca:
        busca_limpa = busca.upper().replace("-", "").strip()
        # Expressão regular simples para validar placa (padrão antigo ABC-1234 ou Mercosul ABC1D23)
        if re.match(r"^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$", busca_limpa):
            # Procura se o veículo já existe cadastrado no banco de dados local
            conn = services.get_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM veiculos WHERE placa = ? AND empresa_id = ?", (busca_limpa, user['empresa_id']))
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

@st.dialog("Novo Cadastro de Veículo (SIL)")
def render_modal_cadastro_veiculo(user):
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
    st.subheader("📁 Importação em Massa (Placas)")
    uploaded_file = st.file_uploader("Arquivo Excel, PDF ou TXT com Placas", type=["xlsx", "xls", "pdf", "txt"], key="upload_veiculos")
    if uploaded_file:
        if st.button("🚀 Iniciar Importação de Veículos"):
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

def render_ae_express(user):
    st.header("⚡ Criar Monitoramento")
    st.caption("Cadastre e ative uma Autorização de Embarque (AE) na Opentech usando o mínimo de dados.")

    # ── Inicializar session_state ──
    for chave, valor_padrao in [
        ("ae_mot_nome", None), ("ae_veic_tipo", None),
        ("ae_buscou_mot", False), ("ae_buscou_veic", False),
    ]:
        if chave not in st.session_state:
            st.session_state[chave] = valor_padrao

    try:
        import json
        with open("cidades_opentech.json", "r", encoding="utf-8") as f:
            CIDADES_CONHECIDAS = json.load(f)
    except:
        CIDADES_CONHECIDAS = {}

    ESTADOS_BR = [
        "AC","AL","AM","AP","BA","CE","DF","ES","GO","MA","MG","MS","MT",
        "PA","PB","PE","PI","PR","RJ","RN","RO","RR","RS","SC","SE","SP","TO"
    ]

    col_form, col_hist = st.columns([1.2, 1.8])

    with col_form:
        st.subheader("📝 Novo Monitoramento")

        # ── CPF do Motorista ──
        st.markdown("**👤 Motorista**")
        col_cpf, col_btn_cpf = st.columns([3, 1])
        with col_cpf:
            cpf_input = st.text_input(
                "CPF (apenas números)", max_chars=11, placeholder="00000000000",
                key="ae_cpf", label_visibility="collapsed"
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
                            # Salva no banco local
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
                "Placa (7 dígitos)", max_chars=7, placeholder="ABC1D23",
                key="ae_placa", label_visibility="collapsed"
            )
        with col_btn_placa:
            st.write("")
            buscar_veic = st.button("🔍 Buscar", key="btn_buscar_veic", use_container_width=True)

        if buscar_veic:
            st.session_state.ae_buscou_veic = True
            placa_digits = (placa_cavalo or "").replace("-", "").strip().upper()
            if len(placa_digits) == 7:
                veic = services.buscar_veiculo_por_placa(placa_cavalo, user['empresa_id'])
                if veic:
                    st.session_state.ae_veic_tipo = veic['tipo_veiculo']
                else:
                    with st.spinner("Buscando veículo no SIL (Opentech)..."):
                        res_sil = services.consultar_opentech_veiculo(placa_digits, "TOKEN", usuario_nome=user['nome'])
                        if res_sil and res_sil.get("status") and "Erro" not in res_sil.get("status"):
                            st.session_state.ae_veic_tipo = res_sil.get("tipo_veiculo", "N/I")
                            # Salva no banco local
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
            else:
                st.warning("⚠️ Digite a placa completa (7 caracteres) antes de buscar.")

        if st.session_state.ae_veic_tipo:
            st.success(f"✅ **{(placa_cavalo or '').upper()}** — {st.session_state.ae_veic_tipo}")
        elif st.session_state.ae_buscou_veic and not st.session_state.ae_veic_tipo:
            st.error("❌ Veículo não encontrado no banco local nem no SIL.")

        placa_carreta = st.text_input(
            "Placa da Carreta (Opcional)", max_chars=7, placeholder="XYZ9A99", key="ae_placa_carreta"
        )

        st.divider()

        # ── Rota ──
        st.markdown("**🗺️ Rota da Viagem**")

        # Origem
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

        # Destino
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

        # Botão para consultar rotas
        btn_buscar_rotas = st.button("🗺️ Buscar Rotas Disponíveis", use_container_width=True)
        if btn_buscar_rotas:
            with st.spinner("Buscando rotas na Opentech..."):
                rotas_encontradas = services.buscar_rota_especifica(cd_cidade_origem, cd_cidade_destino)

                # Se retornou erro (dict) ou lista vazia, busca todas as rotas como fallback
                eh_erro = isinstance(rotas_encontradas, dict) and "error" in rotas_encontradas
                eh_vazio = isinstance(rotas_encontradas, list) and len(rotas_encontradas) == 0

                if eh_erro or eh_vazio:
                    # Fallback: busca todas as rotas modelo ativas da conta
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
        with st.form("ae_express_form", clear_on_submit=False):
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

            # CNPJs removidos da interface (sendo enviados em branco ou padrão internamente)
            cnpj_origem = ""
            cnpj_destino = ""

            valor_carga = st.number_input(
                "Valor da Carga (R$)", min_value=100.0, value=50000.0, step=5000.0, format="%.2f"
            )
            st.caption("ℹ️ **Produto fixado:** E-commerce")
            numero_isca = st.text_input("Número da Isca (Opcional)", placeholder="Ex: ISCA998877")

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

            # Apenas usuários supervisor ou admin podem usar modo simulação
            if user.get('role', '').lower() in ['admin', 'supervisor']:
                modo_simulacao = st.checkbox(
                    "Modo de Simulação (Recomendado para Testes)", value=True,
                    help="Evita chamadas de produção que possam falhar por falta de dados reais cadastrados no webservice da Opentech."
                )
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
                            st.success(msg)
                            # Extrair cd_viagem da mensagem para disponibilizar PDF
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
                            st.session_state.ae_buscou_mot = False
                            st.session_state.ae_buscou_veic = False
                            if "ae_rotas_opcoes" in st.session_state:
                                del st.session_state.ae_rotas_opcoes
                            st.rerun()
                        else:
                            st.error(msg)

    with col_hist:
        st.subheader("📋 Viagens & Monitoramentos Ativos")

        # ── Download PDF da última AE criada ──
        if "ae_ultimo_cd_viagem" in st.session_state and st.session_state.ae_ultimo_cd_viagem:
            cd_v = st.session_state.ae_ultimo_cd_viagem
            st.markdown(f"""<div style='background:linear-gradient(135deg,#0D1B2A,#1A3A5C);
                padding:12px 16px; border-radius:8px; border-left:4px solid #2D6A9F; margin-bottom:12px;'>
                <span style='color:#B0C4D8;font-size:12px;'>✅ AE criada com sucesso</span><br>
                <span style='color:white;font-weight:bold;font-size:15px;'>AE #{cd_v} — Pronta para download</span>
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
                if "Cancelada" in status:
                    status_badge = '<span class="badge badge-perigo">CANCELADA</span>'
                elif "Baixada" in status:
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
                        st.markdown(f"**Previsão de Início:** {v['previsao_inicio']}")
                        st.markdown(f"**Previsão de Fim:** {prev_fim_str}")
                        st.markdown(f"**Código de Programação Opentech:** `{v['cd_programacao']}`")

                    with col_acoes:
                        st.markdown(f"<div style='text-align: center; margin-bottom: 10px;'>{status_badge}</div>", unsafe_allow_html=True)

                        # Botão de PDF sempre disponível
                        if st.button("📄 PDF da AE", key=f"pdf_{v['id']}", use_container_width=True):
                            with st.spinner("Gerando PDF..."):
                                dados_loc = {
                                    "cd_programacao": v.get("cd_programacao"),
                                    "nome_motorista":  v.get("nome_motorista"),
                                    "cpf_motorista":   v.get("cpf_motorista"),
                                    "placa_cavalo":    v.get("placa_cavalo"),
                                    "placa_carreta":   v.get("placa_carreta"),
                                    "origem":          v.get("origem"),
                                    "destino":         v.get("destino"),
                                    "produto":         v.get("produto"),
                                    "valor_carga":     v.get("valor_carga"),
                                    "numero_isca":     v.get("numero_isca"),
                                    "previsao_inicio": v.get("previsao_inicio"),
                                    "previsao_fim":    v.get("previsao_fim"),
                                    "status":          v.get("status"),
                                }
                                pdf_bytes = services.gerar_pdf_ae(v['cd_viagem'], dados_loc)
                            if pdf_bytes:
                                st.download_button(
                                    label=f"⬇️ Baixar AE #{v['cd_viagem']}.pdf",
                                    data=pdf_bytes,
                                    file_name=f"AE_{v['cd_viagem']}_BBMRisk.pdf",
                                    mime="application/pdf",
                                    use_container_width=True,
                                    key=f"dl_{v['id']}"
                                )
                            else:
                                st.error("Falha ao gerar PDF.")

# --- EXECUÇÃO ---
if not st.session_state.autenticado:
    login_screen()
else:
    main_app()
