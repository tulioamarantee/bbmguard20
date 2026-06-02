import streamlit as st
from datetime import datetime, timedelta
import services
import styles
import re
from database import init_db

# Configuração da página
st.set_page_config(page_title="BBM Guard - Controle de Portaria", layout="wide", page_icon="🛡️")

# Inicializar Banco de Dados
init_db()

# --- GERENCIAMENTO DE SESSÃO ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False
    st.session_state.usuario = None

def login_screen():
    import os
    logo_path = "logo_bbm.png"
    
    # Aplicar estilo mesmo no login
    styles.apply_custom_branding()
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if os.path.exists(logo_path):
            st.image(logo_path, use_container_width=True)
        else:
            st.markdown("<h1 style='text-align: center;'>🛡️ BBM Guard</h1>", unsafe_allow_html=True)
            
        with st.form("login_form"):
            st.subheader("Acesso ao Sistema")
            login = st.text_input("Usuário")
            senha = st.text_input("Senha", type="password")
            submit = st.form_submit_button("Entrar")
            
            if submit:
                user = services.autenticar_usuario(login, senha)
                if user:
                    st.session_state.autenticado = True
                    st.session_state.usuario = dict(user)
                    st.success("Login realizado!")
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
        
        # Definir opções de navegação de acordo com o papel do usuário
        role = (user.get('role') or '').lower()
        if role == 'portaria':
            # Portaria: consulta motoristas e veículos
            opcoes = ["Controle de Portaria", "Controle de Veículos"]
        elif role == 'supervisor':
            # Supervisor: portaria + veículos + configurações
            opcoes = ["Controle de Portaria", "Controle de Veículos", "Configurações"]
        elif role.startswith('admin'):
            # Admin: acesso total
            opcoes = ["Dashboard", "Controle de Portaria", "Controle de Veículos", "Configurações"]
        else:
            # Papel desconhecido: portaria
            opcoes = ["Controle de Portaria", "Controle de Veículos"]
        
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
        # Restrição de acesso: usuários da portaria não podem visualizar o Dashboard
        if (user.get('role') or '').lower() == 'portaria':
            st.warning("⚠️ Acesso ao Dashboard não permitido para o usuário da Portaria.")
        else:
            render_dashboard(user)
    elif menu == "Controle de Portaria":
        render_motoristas(user)
    elif menu == "Controle de Veículos":
        render_veiculos(user)
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
        # ── Abas: Criar Usuário | Gerenciar Usuários ──
        tab_criar, tab_gerenciar = st.tabs(["➕ Novo Usuário", "👥 Gerenciar Usuários"])

        # ── ABA 1: Criar novo usuário ──
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
                            st.success(msg)
                            st.rerun()
                        else:
                            st.error(msg)

        # ── ABA 2: Gerenciar usuários existentes ──
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

# --- EXECUÇÃO ---
if not st.session_state.autenticado:
    login_screen()
else:
    main_app()
