import streamlit as st
import logging
import os
import sqlite3
from datetime import datetime, timedelta
import hashlib
import pandas as pd
import fitz
import re
from concurrent.futures import ThreadPoolExecutor
from database import get_connection
import soap_client

# Configuração de Logs
LOG_DIR = "logs"
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

sil_logger = logging.getLogger("SIL_Opentech")
sil_handler = logging.FileHandler(os.path.join(LOG_DIR, "consultas_portaria.log"), encoding='utf-8')
sil_handler.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
sil_logger.addHandler(sil_handler)
sil_logger.setLevel(logging.INFO)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def validar_cpf(cpf):
    """
    Valida CPF seguindo o algoritmo oficial. 
    Permite CPFs de 3 dígitos (123, 456) apenas para fins de teste/homologação.
    """
    # Remove caracteres não numéricos
    cpf = ''.join(filter(str.isdigit, cpf))

    # BYPASS PARA TESTE
    if len(cpf) == 3:
        return True

    if len(cpf) != 11:
        return False

    # Impede CPFs com todos os dígitos iguais (Ex: 111.111.111-11)
    if cpf == cpf[0] * 11:
        return False

    # Cálculo do primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito_1 = (soma * 10 % 11) % 10

    # Cálculo do segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito_2 = (soma * 10 % 11) % 10

    return int(cpf[9]) == digito_1 and int(cpf[10]) == digito_2

def autenticar_usuario(login, senha):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.*, e.nome as empresa_nome, e.logo_url, e.cor_primaria, e.cor_secundaria, u.role
        FROM usuarios u
        JOIN empresas e ON u.empresa_id = e.id
        WHERE u.login = %s AND u.senha = %s
    ''', (login, hash_password(senha)))
    user = cursor.fetchone()
    conn.close()
    return user

# --- INTEGRAÇÃO MOCK SIL OPENTECH ---
def formatar_data_validade(data_expira_str):
    """
    Calcula o tempo restante para expiração e retorna uma string formatada.
    """
    if not data_expira_str or data_expira_str == "N/I":
        return "Validade: N/I"
    try:
        # Tenta converter a data (Opentech costuma enviar ISO 8601)
        # Ex: 2027-05-13T13:44:12-03:00
        data_limpa = data_expira_str.split('T')[0]
        dt_exp = datetime.strptime(data_limpa, "%Y-%m-%d")
        hoje = datetime.now()
        
        delta = dt_exp - hoje
        data_formatada = dt_exp.strftime("%d/%m/%Y")
        
        if delta.days < 0:
            return f"❌ Vencido em {data_formatada} (há {-delta.days} dias)"
        elif delta.days < 30:
            return f"⚠️ Vence em {data_formatada} ({delta.days} dias)"
        else:
            meses = delta.days // 30
            return f"✅ Vence em {data_formatada} ({meses} meses)"
    except Exception:
        return f"Validade: {data_expira_str}"

def consultar_opentech(cpf, token_empresa, usuario_nome="Sistema"):
    """
    Integração real com a API SIL Opentech.
    """
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    sil_logger.info(f"REQ | Usuário: {usuario_nome} | CPF: {cpf_limpo}")
    
    try:
        resultado = soap_client.consultar_motorista(cpf_limpo)
        if "error" in resultado:
            return {"nome": "Erro", "status": f"Erro: {resultado['error']}", "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M"), "validade": "N/I"}

        return {
            "nome": resultado.get("nome", "Não Identificado"),
            "cnh": resultado.get("cnh", "N/I"),
            "categoria": resultado.get("categoria", "N/I"),
            "status": resultado.get("status_label", "Sem Informação"),
            "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "validade": resultado.get("data_expiracao", "N/I")
        }
    except Exception as e:
        sil_logger.exception(f"FATAL | Erro ao consultar Opentech para CPF {cpf_limpo}")
        return {"nome": "Erro Fatal", "status": f"Erro de Conexão: {str(e)}", "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M"), "validade": "N/I"}

# --- GESTÃO DE MOTORISTAS ---
@st.cache_data(ttl=60, show_spinner=False)
def listar_motoristas(empresa_id, busca=""):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT m.*, MAX(r.data_hora) as ultima_consulta 
        FROM motoristas m 
        LEFT JOIN registros_acesso r ON m.id = r.motorista_id AND r.empresa_id = m.empresa_id
        WHERE m.empresa_id = %s
    """
    params = [empresa_id]
    
    if busca:
        query += " AND (m.nome LIKE %s OR m.cpf LIKE %s)"
        params.extend([f"%{busca}%", f"%{busca}%"])
        
    query += " GROUP BY m.id ORDER BY COALESCE(MAX(r.data_hora), '') DESC, m.id DESC"
    
    try:
        cursor.execute(query, params)
    except Exception as e:
        import streamlit as st
        st.error(f"Erro real do Postgres: {str(e)}\n\nQuery: {query}")
        st.stop()
    motoristas = cursor.fetchall()
    conn.close()
    return motoristas

def verificar_validade_existente(cpf, empresa_id):
    """
    Verifica se o motorista já existe e se a consulta SIL ainda é válida.
    Retorna (existe, valida, data_expiracao, nome, status_sil, data_consulta_sil)
    """
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT data_expiracao, nome, status_sil, data_consulta_sil FROM motoristas 
        WHERE cpf = %s AND empresa_id = %s
    ''', (cpf_limpo, empresa_id))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        data_exp = res['data_expiracao']
        status_sil = res['status_sil']
        data_consulta_sil = res['data_consulta_sil']
        if not data_exp or data_exp == "N/I":
            return True, False, "N/I", res['nome'], status_sil, data_consulta_sil
        
        try:
            data_limpa = data_exp.split('T')[0]
            dt_exp = datetime.strptime(data_limpa, "%Y-%m-%d")
            if dt_exp > datetime.now():
                return True, True, dt_exp.strftime("%d/%m/%Y"), res['nome'], status_sil, data_consulta_sil
        except:
            pass
        return True, False, data_exp, res['nome'], status_sil, data_consulta_sil
    
    return False, False, None, None, None, None

def cadastrar_motorista(dados, empresa_id):
    listar_motoristas.clear()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO motoristas (nome, cpf, cnh, categoria, status_sil, data_consulta_sil, data_expiracao, empresa_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (cpf, empresa_id) DO UPDATE SET
                nome = EXCLUDED.nome,
                cnh = EXCLUDED.cnh,
                categoria = EXCLUDED.categoria,
                status_sil = EXCLUDED.status_sil,
                data_consulta_sil = EXCLUDED.data_consulta_sil,
                data_expiracao = EXCLUDED.data_expiracao
        ''', (dados['nome'], dados['cpf'], dados['cnh'], dados['categoria'], 
              dados['status_sil'], dados['data_consulta_sil'], dados.get('validade', 'N/I'), empresa_id))
        conn.commit()
        return True, f"Motorista {dados['nome']} atualizado/cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro: {str(e)}"
    finally:
        conn.close()

def cadastrar_usuario(nome, login, senha, cpf, data_nascimento, email, empresa_id, role='Portaria'):
    """
    Cadastra um novo usuário na tabela `usuarios`.
    Recebe os dados do formulário de configuração.
    Retorna (True, mensagem) em caso de sucesso ou (False, mensagem de erro).
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        hashed = hash_password(senha)
        cursor.execute('''
            INSERT INTO usuarios (nome, login, senha, cpf, data_nascimento, email, empresa_id, role)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (nome, login, hashed, cpf, data_nascimento, email, empresa_id, role))
        conn.commit()
        return True, f"Usuário {nome} criado com sucesso."
    except sqlite3.IntegrityError as e:
        return False, "Erro: login já existe ou CPF duplicado."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def listar_usuarios(empresa_id):
    """
    Lista todos os usuários da empresa.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, nome, login, cpf, data_nascimento, email, role
        FROM usuarios
        WHERE empresa_id = %s
        ORDER BY nome
    ''', (empresa_id,))
    usuarios = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return usuarios

def get_produtividade_usuarios(empresa_id):
    """
    Retorna um DataFrame com a quantidade de consultas (SIL) e AEs criadas por cada usuário.
    """
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT 
            u.nome AS "Usuário", 
            u.login AS "Login",
            COUNT(DISTINCT r.id) AS "Consultas SIL (Motorista/Veículo)",
            COUNT(DISTINCT v.id) AS "AEs Criadas"
        FROM usuarios u
        LEFT JOIN registros_acesso r ON u.id = r.usuario_id AND r.empresa_id = u.empresa_id
        LEFT JOIN viagens v ON u.id = v.usuario_id AND v.empresa_id = v.empresa_id
        WHERE u.empresa_id = %s
        GROUP BY u.id
        ORDER BY "AEs Criadas" DESC, "Consultas SIL (Motorista/Veículo)" DESC
    """
    try:
        cursor.execute(query, [empresa_id])
        rows = cursor.fetchall()
        import pandas as pd
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame([dict(r) for r in rows])
    except Exception as e:
        import streamlit as st
        st.error(f"Erro ao buscar produtividade: {e}")
        return None
    finally:
        conn.close()

def atualizar_usuario(usuario_id, nome, email, role, nova_senha=None):
    """
    Atualiza os dados de um usuário existente.
    Se nova_senha for informada, também atualiza a senha.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        if nova_senha:
            hashed = hash_password(nova_senha)
            cursor.execute('''
                UPDATE usuarios
                SET nome = %s, email = %s, role = %s, senha = %s
                WHERE id = %s
            ''', (nome, email, role, hashed, usuario_id))
        else:
            cursor.execute('''
                UPDATE usuarios
                SET nome = %s, email = %s, role = %s
                WHERE id = %s
            ''', (nome, email, role, usuario_id))
        conn.commit()
        return True, f"Usuário {nome} atualizado com sucesso."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def excluir_usuario(usuario_id):
    """
    Exclui um usuário pelo ID.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM usuarios WHERE id = %s', (usuario_id,))
        conn.commit()
        return True, "Usuário excluído com sucesso."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def importar_motoristas_excel(file, empresa_id, usuario_nome):
    """
    Processa arquivo Excel, consulta SIL e cadastra motoristas.
    """
    try:
        df = pd.read_excel(file)
        # Tenta achar a coluna de CPF
        col_cpf = None
        for col in df.columns:
            if 'cpf' in str(col).lower():
                col_cpf = col
                break
        
        if not col_cpf:
            return False, "Erro: Coluna 'CPF' não encontrada no arquivo Excel."
        
        cpfs = df[col_cpf].dropna().astype(str).unique()
        importados = 0
        erros = 0
        duplicados = 0
        validados = 0
        bloqueados = 0
        vencidos = 0
        detalhes_processamento = []
        
        hoje = datetime.now()
        
        # Filtrar e limpar todos os CPFs válidos
        cpfs_limpos = []
        for cpf in cpfs:
            cpf_base = str(cpf).split('.')[0]
            cpf_limpo = ''.join(filter(str.isdigit, cpf_base)).zfill(11)
            if len(cpf_limpo) == 11 and cpf_limpo not in cpfs_limpos:
                cpfs_limpos.append(cpf_limpo)
                
        if not cpfs_limpos:
            return False, "Nenhum CPF válido encontrado no Excel."
            
        # Consultar Opentech em paralelo usando ThreadPoolExecutor
        resultados_opentech = {}
        def consultar_paralelo(c):
            return c, consultar_opentech(c, "TOKEN", usuario_nome)
            
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(consultar_paralelo, c) for c in cpfs_limpos]
            for future in futures:
                c, res = future.result()
                resultados_opentech[c] = res
                
        # Gravar no Banco de Dados SQLite sequencialmente
        for cpf_limpo in cpfs_limpos:
            res = resultados_opentech[cpf_limpo]
            if "Erro" not in res['status']:
                status_sil = res['status']
                status_norm = str(status_sil).strip().lower()
                
                # Status SIL
                if status_norm == "validado":
                    validados += 1
                    status_emoji = "✅"
                else:
                    bloqueados += 1
                    status_emoji = "❌"
                
                # Validade
                validade = res['validade']
                validade_status = "N/I"
                if validade and validade != "N/I":
                    try:
                        data_limpa = validade.split('T')[0]
                        dt_exp = datetime.strptime(data_limpa, "%Y-%m-%d")
                        if dt_exp < hoje:
                            vencidos += 1
                            validade_status = "❌ Vencido"
                        else:
                            validade_status = f"📅 Vence em {dt_exp.strftime('%d/%m/%Y')}"
                    except Exception:
                        validade_status = validade
                        
                dados = {
                    'nome': res['nome'], 'cpf': cpf_limpo, 'cnh': res['cnh'], 
                    'categoria': res['categoria'],
                    'status_sil': res['status'],
                    'data_consulta_sil': res['data_consulta'],
                    'validade': res['validade']
                }
                # Tenta cadastrar.
                sucesso, _ = cadastrar_motorista(dados, empresa_id)
                
                tipo_import = "Novo"
                if sucesso:
                    importados += 1
                else:
                    erros += 1
                    tipo_import = "Falha"
                        
                detalhes_processamento.append(
                    f"- **{res['nome']}** ({cpf_limpo}) | SIL: {status_emoji} {res['status']} | Validade: {validade_status} | ({tipo_import})"
                )
            else:
                erros += 1
                detalhes_processamento.append(f"- CPF **{cpf_limpo}** | ❌ Erro Opentech: {res['status']}")
        
        detalhes_str = "\n".join(detalhes_processamento)
        msg = (
            f"Importação de Excel concluída com sucesso!\n\n"
            f"📊 **Resumo do Processamento:**\n"
            f"- **Total de CPFs na Planilha:** {len(cpfs_limpos)}\n"
            f"- **Novos cadastrados:** {importados}\n"
            f"- **Falhas no processamento:** {erros}\n\n"
            f"🔍 **Status SIL Opentech:**\n"
            f"- ✅ **Validados:** {validados}\n"
            f"- ❌ **Bloqueados/Outros:** {bloqueados}\n"
            f"- 📅 **Vencidos:** {vencidos}\n\n"
            f"📋 **Lista de Motoristas Processados:**\n"
            f"{detalhes_str}"
        )
        return True, msg
    except Exception as e:
        return False, f"Erro ao processar Excel: {e}"

def importar_motoristas_pdf(file, empresa_id, usuario_nome):
    """
    Processa arquivo PDF, busca CPFs via Regex, consulta SIL e cadastra motoristas.
    """
    try:
        # Lê o PDF usando fitz (PyMuPDF)
        doc = fitz.open(stream=file.read(), filetype="pdf")
        texto = ""
        for page in doc:
            texto += page.get_text()
            
        # Regex para buscar padrões de CPF
        padrao_cpf = re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b')
        cpfs_encontrados = padrao_cpf.findall(texto)
        
        if not cpfs_encontrados:
            return False, "Nenhum CPF encontrado no arquivo PDF."
            
        # Limpar e remover duplicados
        cpfs = []
        for cpf in cpfs_encontrados:
            cpf_limpo = ''.join(filter(str.isdigit, cpf)).zfill(11)
            if len(cpf_limpo) == 11 and cpf_limpo not in cpfs:
                cpfs.append(cpf_limpo)
                
        importados = 0
        erros = 0
        validados = 0
        bloqueados = 0
        vencidos = 0
        detalhes_processamento = []
        
        hoje = datetime.now()
        
        # Consultar Opentech em paralelo usando ThreadPoolExecutor
        resultados_opentech = {}
        def consultar_paralelo(c):
            return c, consultar_opentech(c, "TOKEN", usuario_nome)
            
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(consultar_paralelo, c) for c in cpfs]
            for future in futures:
                c, res = future.result()
                resultados_opentech[c] = res
                
        # Gravar no Banco de Dados SQLite sequencialmente
        for cpf_limpo in cpfs:
            res = resultados_opentech[cpf_limpo]
            if "Erro" not in res['status']:
                status_sil = res['status']
                status_norm = str(status_sil).strip().lower()
                
                # Status SIL
                if status_norm == "validado":
                    validados += 1
                    status_emoji = "✅"
                else:
                    bloqueados += 1
                    status_emoji = "❌"
                
                # Validade
                validade = res['validade']
                validade_status = "N/I"
                if validade and validade != "N/I":
                    try:
                        data_limpa = validade.split('T')[0]
                        dt_exp = datetime.strptime(data_limpa, "%Y-%m-%d")
                        if dt_exp < hoje:
                            vencidos += 1
                            validade_status = "❌ Vencido"
                        else:
                            validade_status = f"📅 Vence em {dt_exp.strftime('%d/%m/%Y')}"
                    except Exception:
                        validade_status = validade
                        
                dados = {
                    'nome': res['nome'], 'cpf': cpf_limpo, 'cnh': res['cnh'], 
                    'categoria': res['categoria'],
                    'status_sil': res['status'],
                    'data_consulta_sil': res['data_consulta'],
                    'validade': res['validade']
                }
                
                sucesso, _ = cadastrar_motorista(dados, empresa_id)
                
                if sucesso:
                    importados += 1
                else:
                    erros += 1
                        
                detalhes_processamento.append(
                    f"- **{res['nome']}** ({cpf_limpo}) | SIL: {status_emoji} {res['status']} | Validade: {validade_status}"
                )
            else:
                erros += 1
                detalhes_processamento.append(f"- CPF **{cpf_limpo}** | ❌ Erro Opentech: {res['status']}")
        
        detalhes_str = "\n".join(detalhes_processamento)
        msg = (
            f"Importação de PDF concluída com sucesso!\n\n"
            f"📊 **Resumo do Processamento:**\n"
            f"- **Total de CPFs no PDF:** {len(cpfs)}\n"
            f"- **Novos cadastrados:** {importados}\n"
            f"- **Falhas no processamento:** {erros}\n\n"
            f"🔍 **Status SIL Opentech:**\n"
            f"- ✅ **Validados:** {validados}\n"
            f"- ❌ **Bloqueados/Outros:** {bloqueados}\n"
            f"- 📅 **Vencidos:** {vencidos}\n\n"
            f"📋 **Lista de Motoristas Processados:**\n"
            f"{detalhes_str}"
        )
        return True, msg
    except Exception as e:
        return False, f"Erro ao processar PDF: {e}"

def importar_motoristas_txt(file, empresa_id, usuario_nome):
    """
    Processa arquivo TXT, busca CPFs via Regex, consulta SIL e cadastra motoristas.
    """
    try:
        texto = file.read().decode('utf-8', errors='ignore')
        
        # Regex para buscar padrões de CPF
        padrao_cpf = re.compile(r'\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b')
        cpfs_encontrados = padrao_cpf.findall(texto)
        
        if not cpfs_encontrados:
            return False, "Nenhum CPF encontrado no arquivo TXT."
            
        # Limpar e remover duplicados
        cpfs = []
        for cpf in cpfs_encontrados:
            cpf_limpo = ''.join(filter(str.isdigit, cpf)).zfill(11)
            if len(cpf_limpo) == 11 and cpf_limpo not in cpfs:
                cpfs.append(cpf_limpo)
                
        importados = 0
        erros = 0
        validados = 0
        bloqueados = 0
        vencidos = 0
        detalhes_processamento = []
        
        hoje = datetime.now()
        
        # Consultar Opentech em paralelo usando ThreadPoolExecutor
        resultados_opentech = {}
        def consultar_paralelo(c):
            return c, consultar_opentech(c, "TOKEN", usuario_nome)
            
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(consultar_paralelo, c) for c in cpfs]
            for future in futures:
                c, res = future.result()
                resultados_opentech[c] = res
                
        # Gravar no Banco de Dados SQLite sequencialmente
        for cpf_limpo in cpfs:
            res = resultados_opentech[cpf_limpo]
            if "Erro" not in res['status']:
                status_sil = res['status']
                status_norm = str(status_sil).strip().lower()
                
                if status_norm == "validado":
                    validados += 1
                    status_emoji = "✅"
                else:
                    bloqueados += 1
                    status_emoji = "❌"
                
                validade = res['validade']
                validade_status = "N/I"
                if validade and validade != "N/I":
                    try:
                        data_limpa = validade.split('T')[0]
                        dt_exp = datetime.strptime(data_limpa, "%Y-%m-%d")
                        if dt_exp < hoje:
                            vencidos += 1
                            validade_status = "❌ Vencido"
                        else:
                            validade_status = f"📅 Vence em {dt_exp.strftime('%d/%m/%Y')}"
                    except Exception:
                        validade_status = validade
                        
                dados = {
                    'nome': res['nome'], 'cpf': cpf_limpo, 'cnh': res['cnh'], 
                    'categoria': res['categoria'],
                    'status_sil': res['status'],
                    'data_consulta_sil': res['data_consulta'],
                    'validade': res['validade']
                }
                
                sucesso, _ = cadastrar_motorista(dados, empresa_id)
                if sucesso:
                    importados += 1
                else:
                    erros += 1
                        
                detalhes_processamento.append(
                    f"- **{res['nome']}** ({cpf_limpo}) | SIL: {status_emoji} {res['status']} | Validade: {validade_status}"
                )
            else:
                erros += 1
                detalhes_processamento.append(f"- CPF **{cpf_limpo}** | ❌ Erro Opentech: {res['status']}")
        
        detalhes_str = "\n".join(detalhes_processamento)
        msg = (
            f"Importação de TXT concluída com sucesso!\n\n"
            f"📊 **Resumo do Processamento:**\n"
            f"- **Total de CPFs no TXT:** {len(cpfs)}\n"
            f"- **Novos cadastrados:** {importados}\n"
            f"- **Falhas no processamento:** {erros}\n\n"
            f"🔍 **Status SIL Opentech:**\n"
            f"- ✅ **Validados:** {validados}\n"
            f"- ❌ **Bloqueados/Outros:** {bloqueados}\n"
            f"- 📅 **Vencidos:** {vencidos}\n\n"
            f"📋 **Lista de Motoristas Processados:**\n"
            f"{detalhes_str}"
        )
        return True, msg
    except Exception as e:
        return False, f"Erro ao processar TXT: {e}"


def atualizar_sil_motorista(motorista_id, cpf, empresa_id, usuario_nome):
    """
    Força uma nova consulta na Opentech e atualiza o motorista existente.
    """
    res = consultar_opentech(cpf, "FORCE", usuario_nome)
    if "Erro" in res['status']:
        return False, res['status']
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE motoristas 
            SET nome = %s, cnh = %s, categoria = %s, status_sil = %s, 
                data_consulta_sil = %s, data_expiracao = %s
            WHERE id = %s AND empresa_id = %s
        ''', (res['nome'], res['cnh'], res['categoria'], res['status'], 
              res['data_consulta'], res['validade'], motorista_id, empresa_id))
        conn.commit()
        return True, f"SIL Atualizado com sucesso para {res['nome']}!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def editar_motorista(motorista_id, dados, empresa_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE motoristas 
        SET nome = %s, cnh = %s, categoria = %s
        WHERE id = %s AND empresa_id = %s
    ''', (dados['nome'], dados['cnh'], dados['categoria'], motorista_id, empresa_id))
    conn.commit()
    conn.close()
    return "Dados do motorista atualizados."

def deletar_motorista(motorista_id, empresa_id):
    conn = get_connection()
    cursor = conn.cursor()
    # Deletar ocorrências primeiro (Integridade)
    cursor.execute("DELETE FROM ocorrencias WHERE motorista_id = %s AND empresa_id = %s", (motorista_id, empresa_id))
    cursor.execute("DELETE FROM motoristas WHERE id = %s AND empresa_id = %s", (motorista_id, empresa_id))
    conn.commit()
    conn.close()
    return "Motorista e histórico removidos definitivamente."

def editar_ocorrencia(ocorrencia_id, motivo, gravidade, empresa_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        UPDATE ocorrencias 
        SET motivo = %s, gravidade = %s
        WHERE id = %s AND empresa_id = %s
    ''', (motivo, gravidade, ocorrencia_id, empresa_id))
    conn.commit()
    conn.close()
    return "Ocorrência atualizada com sucesso."

# --- MOTOR DE REGRAS E PENALIDADES ---
def registrar_ocorrencia(motorista_id, tipo, motivo, gravidade, data, usuario_id, empresa_id, data_fim_suspensao=None):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Buscar configurações da empresa
    cursor.execute("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
    config = cursor.fetchone()
    
    # 1. Registrar a ocorrência
    cursor.execute('''
        INSERT INTO ocorrencias (tipo, motivo, gravidade, data, usuario_id, motorista_id, empresa_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
    ''', (tipo, motivo, gravidade, data, usuario_id, motorista_id, empresa_id))
    
    feedback = f"Ocorrência de {tipo} registrada."

    # 2. Atualizar status do motorista baseado no tipo
    if tipo == "Suspensão":
        cursor.execute('''
            UPDATE motoristas 
            SET status_interno = 'Suspenso', data_fim_suspensao = %s
            WHERE id = %s
        ''', (data_fim_suspensao, motorista_id))
    
    elif tipo == "Exclusão":
        cursor.execute('''
            UPDATE motoristas 
            SET status_interno = 'Excluído'
            WHERE id = %s
        ''', (motorista_id,))
        
    elif tipo == "Advertência":
        # Lógica de Acúmulo Customizada
        intervalo = config['intervalo_dias_regra']
        limite_adv = config['limite_advertencias']
        limite_susp_exclusao = config['limite_suspensoes_exclusao']
        
        data_limite = (datetime.now() - timedelta(days=intervalo)).strftime("%Y-%m-%d")
        cursor.execute('''
            SELECT COUNT(*) FROM ocorrencias 
            WHERE motorista_id = %s AND tipo = 'Advertência' AND data >= %s
        ''', (motorista_id, data_limite))
        
        total_advertencias = cursor.fetchone()[0]
        
        if total_advertencias >= limite_adv:
            # 1. Verificar quantas suspensões o motorista já teve
            cursor.execute("SELECT COUNT(*) FROM ocorrencias WHERE motorista_id = %s AND tipo = 'Suspensão'", (motorista_id,))
            total_suspensoes = cursor.fetchone()[0]
            
            # 2. Decidir ação: Exclusão ou Suspensão Escalonada
            if total_suspensoes >= limite_susp_exclusao:
                cursor.execute("UPDATE motoristas SET status_interno = 'Excluído' WHERE id = %s", (motorista_id,))
                cursor.execute('''
                    INSERT INTO ocorrencias (tipo, motivo, gravidade, data, usuario_id, motorista_id, empresa_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', ("Exclusão", f"Gatilho: Exclusão Automática por excesso de suspensões (>={limite_susp_exclusao}).", 
                      "Grave", datetime.now().strftime("%Y-%m-%d"), 0, motorista_id, empresa_id))
                feedback += " Crítico: Motorista atingiu limite de suspensões e foi EXCLUÍDO automaticamente."
            else:
                # 3. Definir dias da suspensão baseado no histórico
                dias = config['dias_susp_1'] if total_suspensoes == 0 else config['dias_susp_2']
                data_fim = (datetime.now() + timedelta(days=dias)).strftime("%Y-%m-%d")
                
                cursor.execute('''
                    UPDATE motoristas 
                    SET status_interno = 'Suspenso', data_fim_suspensao = %s
                    WHERE id = %s
                ''', (data_fim, motorista_id))
                
                # Log de Suspensão Automática
                cursor.execute('''
                    INSERT INTO ocorrencias (tipo, motivo, gravidade, data, usuario_id, motorista_id, empresa_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''', ("Suspensão", f"Gatilho: Suspensão Automática ({dias} dias) por excesso de advertências.", 
                      "Grave", datetime.now().strftime("%Y-%m-%d"), 0, motorista_id, empresa_id))
                
                feedback += f" Alerta: Motorista suspenso por {dias} dias (Ocorrência #{total_suspensoes + 1})."

    conn.commit()
    conn.close()
    return feedback

def get_prontuario(motorista_id, empresa_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    # Buscar configurações e CPF do motorista
    cursor.execute("SELECT * FROM empresas WHERE id = %s", (empresa_id,))
    config = cursor.fetchone()
    
    cursor.execute("SELECT * FROM motoristas WHERE id = %s AND empresa_id = %s", (motorista_id, empresa_id))
    motorista = cursor.fetchone()
    cpf = motorista['cpf']
    
    # Histórico de Ocorrências (Auditoria)
    # Se compartilhar_historico for 1, buscar pelo CPF em todas as empresas que também compartilham
    if config['compartilhar_historico']:
        cursor.execute('''
            SELECT o.*, u.nome as usuario_nome, e.nome as empresa_nome
            FROM ocorrencias o
            LEFT JOIN usuarios u ON o.usuario_id = u.id
            JOIN empresas e ON o.empresa_id = e.id
            JOIN motoristas m ON o.motorista_id = m.id
            WHERE m.cpf = %s AND (o.empresa_id = %s OR e.compartilhar_historico = 1)
            ORDER BY o.data DESC, o.id DESC
        ''', (cpf, empresa_id))
    else:
        cursor.execute('''
            SELECT o.*, u.nome as usuario_nome, e.nome as empresa_nome
            FROM ocorrencias o
            LEFT JOIN usuarios u ON o.usuario_id = u.id
            JOIN empresas e ON o.empresa_id = e.id
            WHERE o.motorista_id = %s AND o.empresa_id = %s
            ORDER BY o.data DESC, o.id DESC
        ''', (motorista_id, empresa_id))
        
    ocorrencias = cursor.fetchall()
    
    # Contagem de advertências recentes (usando intervalo dinâmico)
    intervalo = config['intervalo_dias_regra']
    data_limite = (datetime.now() - timedelta(days=intervalo)).strftime("%Y-%m-%d")
    cursor.execute('''
        SELECT COUNT(*) FROM ocorrencias 
        WHERE motorista_id = %s AND tipo = 'Advertência' AND data >= %s
    ''', (motorista_id, data_limite))
    recentes = cursor.fetchone()[0]
    
    conn.close()
    return motorista, ocorrencias, recentes

def get_stats_dashboard(empresa_id):
    """
    Estatísticas focadas em Portaria: Ativos, Vencidos e Liberações do Dia.
    """
    conn = get_connection()
    cursor = conn.cursor()
    hoje_dt = datetime.now()
    hoje_str = hoje_dt.strftime("%Y-%m-%d")
    
    # Consultas hoje (Total de pesquisas na portaria)
    cursor.execute("SELECT COUNT(*) FROM registros_acesso WHERE empresa_id = %s AND data_hora LIKE %s", (empresa_id, f"{hoje_str}%"))
    consultas_hoje = cursor.fetchone()[0]
    
    # Cadastros Ativos (Status Interno Ativo e Data Expiração > Hoje)
    cursor.execute('''
        SELECT COUNT(*) FROM motoristas 
        WHERE empresa_id = %s AND status_interno = 'Ativo' 
        AND (data_expiracao >= %s OR data_expiracao = 'N/I')
    ''', (empresa_id, hoje_str))
    cadastros_ativos = cursor.fetchone()[0]

    # Cadastros Vencidos (Status Interno Ativo mas Data Expiração < Hoje)
    cursor.execute('''
        SELECT COUNT(*) FROM motoristas 
        WHERE empresa_id = %s AND status_interno = 'Ativo' 
        AND data_expiracao < %s AND data_expiracao != 'N/I'
    ''', (empresa_id, hoje_str))
    cadastros_vencidos = cursor.fetchone()[0]
    
    # Liberações Hoje (Consultas que retornaram Validado ou Liberado hoje)
    cursor.execute('''
        SELECT COUNT(*) FROM registros_acesso 
        WHERE empresa_id = %s AND (status_resultado LIKE '%Validado%' OR status_resultado LIKE '%Liberado%')
        AND data_hora LIKE %s
    ''', (empresa_id, f"{hoje_str}%"))
    liberacoes_hoje = cursor.fetchone()[0]
    
    stats = {
        'cadastros_ativos': cadastros_ativos,
        'cadastros_vencidos': cadastros_vencidos,
        'liberacoes_hoje': liberacoes_hoje,
        'consultas_hoje': consultas_hoje
    }
    conn.close()
    return stats

def registrar_consulta_portaria(motorista_id, cpf, status, usuario_id, empresa_id):
    """
    Registra uma consulta no histórico de portaria.
    """
    conn = get_connection()
    cursor = conn.cursor()
    agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO registros_acesso (motorista_id, cpf, status_resultado, data_hora, usuario_id, empresa_id)
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (motorista_id, cpf, status, agora, usuario_id, empresa_id))
    conn.commit()
    conn.close()

def listar_historico_acessos(empresa_id, limite=10):
    """
    Lista as últimas consultas feitas na portaria.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT r.*, m.nome as motorista_nome, u.nome as usuario_nome
        FROM registros_acesso r
        LEFT JOIN motoristas m ON r.motorista_id = m.id
        LEFT JOIN usuarios u ON r.usuario_id = u.id
        WHERE r.empresa_id = %s
        ORDER BY r.data_hora DESC
        LIMIT %s
    ''', (empresa_id, limite))
    acessos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return acessos

# --- GESTÃO DE VEÍCULOS ---

def consultar_opentech_veiculo(placa, token_empresa, usuario_nome="Sistema"):
    """
    Integração com a API SIL Opentech para veículos.
    """
    placa_limpa = placa.upper().replace("-", "").strip()
    sil_logger.info(f"REQ VEICULO | Usuário: {usuario_nome} | Placa: {placa_limpa}")
    try:
        resultado = soap_client.consultar_veiculo(placa_limpa)
        if "error" in resultado:
            return {"placa": placa_limpa, "status": f"Erro: {resultado['error']}", "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M"), "validade": "N/I"}

        return {
            "placa": resultado.get("placa", placa_limpa),
            "tipo_veiculo": resultado.get("tipo_veiculo", "N/I"),
            "status": resultado.get("status_label", "Sem Informação"),
            "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "validade": resultado.get("data_expiracao", "N/I"),
            "ultima_posicao": resultado.get("ultima_posicao", "N/I"),
            "checklist": resultado.get("checklist", "N/I"),
            "rastreadores": resultado.get("rastreadores", "N/I"),
            "segundo_rastreador": resultado.get("segundo_rastreador", "Não possui")
        }
    except Exception as e:
        sil_logger.exception(f"FATAL | Erro ao consultar Opentech para Placa {placa_limpa}")
        return {"placa": placa_limpa, "status": f"Erro de Conexão: {str(e)}", "data_consulta": datetime.now().strftime("%d/%m/%Y %H:%M"), "validade": "N/I"}

@st.cache_data(ttl=60, show_spinner=False)
def listar_veiculos(empresa_id, busca=""):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM veiculos WHERE empresa_id = %s"
    params = [empresa_id]
    
    if busca:
        busca_limpa = busca.upper().replace("-", "").strip()
        query += " AND placa LIKE %s"
        params.append(f"%{busca_limpa}%")
        
    query += " ORDER BY id DESC"
    
    cursor.execute(query, params)
    veiculos = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return veiculos

def buscar_motorista_por_cpf(cpf, empresa_id):
    """Busca um motorista pelo CPF no banco local. Retorna dict ou None."""
    cpf_limpo = ''.join(filter(str.isdigit, cpf))
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM motoristas WHERE cpf = %s AND empresa_id = %s',
        (cpf_limpo, empresa_id)
    )
    mot = cursor.fetchone()
    conn.close()
    return dict(mot) if mot else None

def buscar_veiculo_por_placa(placa, empresa_id):
    """Busca um veículo pela placa no banco local. Retorna dict ou None."""
    placa_limpa = placa.upper().replace('-', '').strip()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        'SELECT * FROM veiculos WHERE placa = %s AND empresa_id = %s',
        (placa_limpa, empresa_id)
    )
    veic = cursor.fetchone()
    conn.close()
    return dict(veic) if veic else None

def verificar_validade_existente_veiculo(placa, empresa_id):

    placa_limpa = placa.upper().replace("-", "").strip()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT validade, status_sil, data_consulta FROM veiculos 
        WHERE placa = %s AND empresa_id = %s
    ''', (placa_limpa, empresa_id))
    res = cursor.fetchone()
    conn.close()
    
    if res:
        return True, res['validade'], res['status_sil'], res['data_consulta']
    return False, None, None, None

def cadastrar_veiculo(dados, empresa_id):
    listar_veiculos.clear()
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO veiculos (placa, tipo_veiculo, status_sil, validade, ultima_posicao, status_checklist, data_consulta, empresa_id, rastreadores, segundo_rastreador)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (placa, empresa_id) DO UPDATE SET
                tipo_veiculo = EXCLUDED.tipo_veiculo,
                status_sil = EXCLUDED.status_sil,
                validade = EXCLUDED.validade,
                ultima_posicao = EXCLUDED.ultima_posicao,
                status_checklist = EXCLUDED.status_checklist,
                data_consulta = EXCLUDED.data_consulta,
                rastreadores = EXCLUDED.rastreadores,
                segundo_rastreador = EXCLUDED.segundo_rastreador
        ''', (dados['placa'], dados['tipo_veiculo'], dados['status'], 
              dados['validade'], dados['ultima_posicao'], dados['checklist'], dados['data_consulta'], empresa_id, dados.get('rastreadores', 'N/I'), dados.get('segundo_rastreador', 'Não possui')))
        conn.commit()
        return True, f"Veículo placa {dados['placa']} atualizado/cadastrado com sucesso!"
    except Exception as e:
        return False, f"Erro ao cadastrar: {str(e)}"
    finally:
        conn.close()

def atualizar_sil_veiculo(veiculo_id, placa, empresa_id, usuario_nome):
    res = consultar_opentech_veiculo(placa, "FORCE", usuario_nome)
    if "Erro" in res['status']:
        return False, res['status']
    
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            UPDATE veiculos 
            SET tipo_veiculo = %s, status_sil = %s, validade = %s, 
                ultima_posicao = %s, status_checklist = %s, data_consulta = %s,
                rastreadores = %s, segundo_rastreador = %s
            WHERE id = %s AND empresa_id = %s
        ''', (res['tipo_veiculo'], res['status'], res['validade'], 
              res['ultima_posicao'], res['checklist'], res['data_consulta'], 
              res.get('rastreadores', 'N/I'), res.get('segundo_rastreador', 'Não possui'), veiculo_id, empresa_id))
        conn.commit()
        return True, f"SIL Atualizado com sucesso para placa {placa}!"
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def importar_veiculos_excel(file, empresa_id, usuario_nome):
    try:
        df = pd.read_excel(file)
        col_placa = None
        for col in df.columns:
            if 'placa' in str(col).lower():
                col_placa = col
                break
        
        if not col_placa:
            # Fallback, extract from entire text of dataframe
            texto = df.to_string()
            padrao_placa = re.compile(r'\b[A-Za-z]{3}-?[0-9][A-Za-z0-9][0-9]{2}\b')
            placas_encontradas = padrao_placa.findall(texto)
        else:
            placas_encontradas = df[col_placa].dropna().astype(str).tolist()
            
        return processar_lote_veiculos(placas_encontradas, empresa_id, usuario_nome, "Excel")
    except Exception as e:
        return False, f"Erro ao processar Excel: {e}"

def importar_veiculos_pdf(file, empresa_id, usuario_nome):
    try:
        doc = fitz.open(stream=file.read(), filetype="pdf")
        texto = ""
        for page in doc:
            texto += page.get_text()
            
        padrao_placa = re.compile(r'\b[A-Za-z]{3}-?[0-9][A-Za-z0-9][0-9]{2}\b')
        placas_encontradas = padrao_placa.findall(texto)
        return processar_lote_veiculos(placas_encontradas, empresa_id, usuario_nome, "PDF")
    except Exception as e:
        return False, f"Erro ao processar PDF: {e}"

def importar_veiculos_txt(file, empresa_id, usuario_nome):
    try:
        texto = file.read().decode('utf-8', errors='ignore')
        padrao_placa = re.compile(r'\b[A-Za-z]{3}-?[0-9][A-Za-z0-9][0-9]{2}\b')
        placas_encontradas = padrao_placa.findall(texto)
        return processar_lote_veiculos(placas_encontradas, empresa_id, usuario_nome, "TXT")
    except Exception as e:
        return False, f"Erro ao processar TXT: {e}"

def processar_lote_veiculos(placas_encontradas, empresa_id, usuario_nome, origem):
    if not placas_encontradas:
        return False, f"Nenhuma placa encontrada no arquivo {origem}."
        
    placas_limpas = []
    for p in placas_encontradas:
        p_limpa = str(p).upper().replace("-", "").strip()
        if len(p_limpa) == 7 and p_limpa not in placas_limpas:
            placas_limpas.append(p_limpa)
            
    if not placas_limpas:
        return False, f"Nenhuma placa válida encontrada no {origem}."
        
    importados = 0
    erros = 0
    duplicados = 0
    validados = 0
    bloqueados = 0
    vencidos = 0
    detalhes_processamento = []
    
    hoje = datetime.now()
    
    resultados_opentech = {}
    def consultar_paralelo(p):
        return p, consultar_opentech_veiculo(p, "TOKEN", usuario_nome)
        
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(consultar_paralelo, p) for p in placas_limpas]
        for future in futures:
            p, res = future.result()
            resultados_opentech[p] = res
            
    for placa in placas_limpas:
        res = resultados_opentech[placa]
        if "Erro" not in res['status']:
            status_sil = res['status']
            status_norm = str(status_sil).strip().lower()
            
            if status_norm == "liberado":
                validados += 1
                status_emoji = "✅"
            else:
                bloqueados += 1
                status_emoji = "❌"
                
            # --- Lógica de Validação da Última Posição (menos de 4 horas) ---
            posicao_bruta = res.get('ultima_posicao', 'N/I')
            posicao_emoji = "⚠️"
            if posicao_bruta and posicao_bruta != "N/I":
                try:
                    # Tenta converter a data da última posição (formato 'dd/mm/aaaa HH:MM:SS')
                    dt_pos = datetime.strptime(posicao_bruta.split('.')[0], "%d/%m/%Y %H:%M:%S")
                    diferenca = datetime.now() - dt_pos
                    if diferenca <= timedelta(hours=4):
                        posicao_emoji = "🟢 OK"
                    else:
                        posicao_emoji = "🔴 Atrasada (>4h)"
                except Exception:
                    pass
            
            # --- Validade do Checklist ---
            checklist_expira = "N/I"
            checklist_bruto = res.get('checklist', 'N/I')
            if "Até" in checklist_bruto:
                match = re.search(r"Até\s+([^)]+)", checklist_bruto)
                if match:
                    checklist_expira = match.group(1).strip()
            else:
                checklist_expira = checklist_bruto

            rastreadores = res.get('rastreadores', 'N/I')
            seg_rastreador = res.get('segundo_rastreador', 'Não possui')
            
            validade = res['validade']
            validade_status = "N/I"
            if validade and validade != "N/I":
                try:
                    # Suporta parsing de datas no formato 'dd/mm/aaaa HH:MM:SS' ou 'YYYY-MM-DD'
                    if '-' in validade:
                        data_limpa = validade.split('T')[0]
                        dt_exp = datetime.strptime(data_limpa, "%Y-%m-%d")
                    else:
                        dt_exp = datetime.strptime(validade.split()[0], "%d/%m/%Y")
                    
                    if dt_exp < hoje:
                        vencidos += 1
                        validade_status = f"❌ Vencida ({dt_exp.strftime('%d/%m/%Y')})"
                    else:
                        validade_status = dt_exp.strftime('%d/%m/%Y')
                except Exception:
                    validade_status = validade
                     
            sucesso, _ = cadastrar_veiculo(res, empresa_id)
            tipo_import = "Novo"
            
            if sucesso:
                importados += 1
            else:
                conn = get_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM veiculos WHERE placa = %s AND empresa_id = %s", (placa, empresa_id))
                veic = cursor.fetchone()
                conn.close()
                
                if veic:
                    ok, _ = atualizar_sil_veiculo(veic[0], placa, empresa_id, usuario_nome)
                    if ok:
                        duplicados += 1
                        tipo_import = "Atualizado"
                    else:
                        erros += 1
                        tipo_import = "Falha"
                else:
                    erros += 1
                    tipo_import = "Falha"
                    
            detalhes_processamento.append(
                f"- **{res['placa']}** ({res['tipo_veiculo']}) | ({tipo_import})\n"
                f"  * **Última Pos:** {posicao_emoji} ({posicao_bruta})\n"
                f"  * **Val. Veículo:** {validade_status}\n"
                f"  * **Val. Checklist:** {checklist_expira}\n"
                f"  * **Rastreador:** {rastreadores}\n"
                f"  * **Secundário:** {seg_rastreador}"
            )
        else:
            erros += 1
            detalhes_processamento.append(f"- Placa **{placa}** | ❌ Erro Opentech: {res['status']}")
            
    return True, msg


# --- GESTÃO DE AUTORIZAÇÃO DE EMBARQUE (AE) EXPRESS ---

def criar_ae_express(dados, empresa_id, usuario_id, modo_simulacao=False):
    """
    Cria uma nova AE na Opentech (ou simulada) a partir das informações mínimas.
    Grava no banco de dados local.
    """
    import random
    
    cpf_motorista = ''.join(filter(str.isdigit, dados["cpf_motorista"]))
    placa_cavalo = dados["placa_cavalo"].upper().replace("-", "").strip()
    placa_carreta = dados.get("placa_carreta", "").upper().replace("-", "").strip()
    origem_nome = dados.get("origem_nome", "Cidade de Origem")
    destino_nome = dados.get("destino_nome", "Cidade de Destino")
    cd_cidade_origem = dados.get("cd_cidade_origem") or 9999
    cd_cidade_destino = dados.get("cd_cidade_destino") or 9999
    valor_carga = dados.get("valor_carga") or 1000.0
    produto = "E-commerce" # Fixado por regra do negócio
    numero_isca = dados.get("numero_isca", "").strip()
    
    previsao_inicio = dados.get("previsao_inicio") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    previsao_fim = dados.get("previsao_fim") or (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    
    # Formatação de datas
    if isinstance(previsao_inicio, str):
        previsao_inicio_dt = datetime.strptime(previsao_inicio, "%Y-%m-%d %H:%M:%S") if len(previsao_inicio) > 10 else datetime.strptime(previsao_inicio, "%Y-%m-%d")
    else:
        previsao_inicio_dt = previsao_inicio
        previsao_inicio = previsao_inicio_dt.strftime("%Y-%m-%d %H:%M:%S")
        
    if isinstance(previsao_fim, str):
        previsao_fim_dt = datetime.strptime(previsao_fim, "%Y-%m-%d %H:%M:%S") if len(previsao_fim) > 10 else datetime.strptime(previsao_fim, "%Y-%m-%d")
    else:
        previsao_fim_dt = previsao_fim
        previsao_fim = previsao_fim_dt.strftime("%Y-%m-%d %H:%M:%S")

    # 1. Obter nome do Motorista
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT nome FROM motoristas WHERE cpf = %s AND empresa_id = %s", (cpf_motorista, empresa_id))
    mot = cursor.fetchone()
    conn.close()
    
    if mot:
        nome_motorista = mot['nome']
    else:
        # Tenta buscar do SIL
        sil_mot = consultar_opentech(cpf_motorista, "TOKEN", "AE_Express")
        if "Erro" not in sil_mot['status']:
            nome_motorista = sil_mot['nome']
        else:
            nome_motorista = "Motorista Não Identificado"

    # 2. Obter dados do Veículo
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT tipo_veiculo FROM veiculos WHERE placa = %s AND empresa_id = %s", (placa_cavalo, empresa_id))
    veic = cursor.fetchone()
    conn.close()
    
    cd_tipo_veiculo = 1 # Padrão: Cavalo Mecânico
    if veic:
        tipo_veic = veic['tipo_veiculo'].lower()
        if "truck" in tipo_veic:
            cd_tipo_veiculo = 2
        elif "carreta" in tipo_veic:
            cd_tipo_veiculo = 3
        elif "bitrem" in tipo_veic:
            cd_tipo_veiculo = 4
    
    # 3. Fluxo de Criação
    if modo_simulacao:
        # Modo de Simulação
        cd_prog = random.randint(87000, 99999)
        cd_viagem = random.randint(552000, 699999)
        
        # Gravar no Banco
        conn = get_connection()
        cursor = conn.cursor()
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor.execute('''
                INSERT INTO viagens (cd_programacao, cd_viagem, cpf_motorista, nome_motorista, placa_cavalo, placa_carreta, 
                                     origem, destino, valor_carga, produto, previsao_inicio, previsao_fim, numero_isca, status, data_criacao, empresa_id, usuario_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (cd_prog, cd_viagem, cpf_motorista, nome_motorista, placa_cavalo, placa_carreta, 
                  f"{origem_nome} ({cd_cidade_origem})", f"{destino_nome} ({cd_cidade_destino})", 
                  valor_carga, produto, previsao_inicio, previsao_fim, numero_isca, 'Ativa (Simulada)', agora, empresa_id, usuario_id))
            conn.commit()
            conn.close()
            return True, f"AE Simulada com sucesso! AE #{cd_viagem} | Programação #{cd_prog} cadastrada."
        except Exception as e:
            conn.close()
            return False, f"Erro ao salvar viagem simulada: {e}"
            
    else:
        # Integração SOAP Real com a Opentech
        # Fase Única: Gerar AE (sgrGerarAEv9)
        import config
        ae_payload = {
            "cdpas": config.CD_PAS,
            "cdcliente": config.CD_CLIENTE,
            "nrplacacavalo": placa_cavalo,
            "nrplacacarreta1": placa_carreta,
            "nrdocmotorista1": cpf_motorista,
            "nomemot1": nome_motorista,
            "dtprevini": previsao_inicio.replace(" ", "T"),
            "dtprevfim": previsao_fim.replace(" ", "T"),
            "cdcidorigem": cd_cidade_origem,
            "cdciddestino": cd_cidade_destino,
            "vlcarga": valor_carga,
            "cdtransp": config.CD_CLIENTE,
            "cdembarcador": config.CD_CLIENTE,
            "cdprod": 22810, # 22810 = E COMMERCE para o cliente Dialogo
            "cdrota": dados.get("cd_rota", -1),
            "nrIsca": numero_isca,
            "nrDoc": numero_isca if numero_isca else f"SGR-{cpf_motorista[-4:]}-{placa_cavalo[-4:]}"
        }
        
        res_ae = soap_client.gerar_ae_v9(ae_payload)
        
        if "error" in res_ae:
            return False, f"Erro ao gerar a AE na Opentech: {res_ae['error']}"
            
        cd_viagem = res_ae["cd_viagem"]
        cd_prog = cd_viagem # Para compatibilidade com o banco
        
        # Gravar no Banco de Dados
        conn = get_connection()
        cursor = conn.cursor()
        agora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            listar_viagens.clear()
            cursor.execute('''
                INSERT INTO viagens (cd_programacao, cd_viagem, cpf_motorista, nome_motorista, placa_cavalo, placa_carreta, 
                                     origem, destino, valor_carga, produto, previsao_inicio, previsao_fim, numero_isca, status, data_criacao, empresa_id, usuario_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''', (cd_prog, cd_viagem, cpf_motorista, nome_motorista, placa_cavalo, placa_carreta, 
                  f"{origem_nome} ({cd_cidade_origem})", f"{destino_nome} ({cd_cidade_destino})", 
                  valor_carga, produto, previsao_inicio, previsao_fim, numero_isca, 'Ativa', agora, empresa_id, usuario_id))
            conn.commit()
            conn.close()
            return True, f"AE Criada com sucesso na Opentech! AE #{cd_viagem} (Programação #{cd_prog})"
        except Exception as e:
            conn.close()
            return True, f"AE criada na Opentech (#{cd_viagem}) mas falhou ao gravar no histórico local: {e}"


@st.cache_data(ttl=60, show_spinner=False)
def listar_viagens(empresa_id, busca=""):
    """
    Lista as viagens/AEs cadastradas no histórico local.
    """
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM viagens WHERE empresa_id = %s"
    params = [empresa_id]
    
    if busca:
        query += " AND (cpf_motorista LIKE %s OR nome_motorista LIKE %s OR placa_cavalo LIKE %s OR placa_carreta LIKE %s OR cd_viagem LIKE %s)"
        params.extend([f"%{busca}%", f"%{busca}%", f"%{busca}%", f"%{busca}%", f"%{busca}%"])
        
    query += " ORDER BY id DESC"
    
    cursor.execute(query, params)
    viagens = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return viagens


def cancelar_viagem_ae(viagem_id, cd_programacao, empresa_id):
    """
    Cancela a viagem na Opentech e atualiza o status na base local.
    """
    # 1. Verificar se a viagem é simulada
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM viagens WHERE id = %s AND empresa_id = %s", (viagem_id, empresa_id))
    res = cursor.fetchone()
    conn.close()
    
    if not res:
        return False, "Viagem não encontrada no sistema."
        
    status_atual = res['status']
    
    if "Simulada" in status_atual:
        # Apenas atualiza local
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE viagens SET status = 'Cancelada (Simulada)' WHERE id = %s", (viagem_id,))
        conn.commit()
        conn.close()
        return True, "Viagem simulada cancelada localmente com sucesso."
        
    else:
        # Tenta cancelar na Opentech
        res_soap = soap_client.cancelar_programacao(cd_programacao)
        if "error" in res_soap:
            # Se der erro mas o usuário quiser forçar o cancelamento local porque a viagem já expirou na Opentech
            # permitimos atualizar localmente avisando do erro
            return False, f"Erro ao cancelar na Opentech: {res_soap['error']}"
            
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE viagens SET status = 'Cancelada' WHERE id = %s", (viagem_id,))
        conn.commit()
        conn.close()
        return True, "Viagem cancelada com sucesso na Opentech e atualizada no histórico."


def baixar_viagem_ae(viagem_id, cd_programacao, empresa_id):
    """
    Finaliza (dá baixa) na viagem na Opentech e atualiza o status na base local.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT status FROM viagens WHERE id = %s AND empresa_id = %s", (viagem_id, empresa_id))
    res = cursor.fetchone()
    conn.close()
    
    if not res:
        return False, "Viagem não encontrada no sistema."
        
    status_atual = res['status']
    
    if "Simulada" in status_atual:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE viagens SET status = 'Baixada (Simulada)' WHERE id = %s", (viagem_id,))
        conn.commit()
        conn.close()
        return True, "Viagem simulada concluída localmente."
        
    else:
        res_soap = soap_client.baixar_programacao(cd_programacao)
        if "error" in res_soap:
            return False, f"Erro ao finalizar viagem na Opentech: {res_soap['error']}"
            
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE viagens SET status = 'Baixada' WHERE id = %s", (viagem_id,))
        conn.commit()
        conn.close()
        return True, "Viagem finalizada (baixa) com sucesso na Opentech!"


def buscar_rotas_opentech():
    """
    Lista todas as Rotas Modelo cadastradas e ativas na Opentech.
    """
    try:
        res = soap_client.obter_rotas_modelo()
        return res
    except Exception as e:
        return {"error": str(e)}


def buscar_rota_especifica(cd_cid_origem, cd_cid_destino):
    """
    Busca todas as rotas modelo disponíveis na Opentech.
    Como os códigos de cidades da rota nem sempre batem com a viagem (ex: Rota Itapeva cobrindo Extrema),
    retornamos todas para que o usuário possa pesquisar na interface.
    """
    try:
        todas = soap_client.obter_rotas_modelo()
        if not isinstance(todas, list):
            return todas

        # Sort the list: exact matches first
        exatas = []
        outras = []
        for r in todas:
            if r.get("cd_cidade_origem") == cd_cid_origem and r.get("cd_cidade_destino") == cd_cid_destino:
                r["ds_rota"] = f"⭐ {r['ds_rota']}"
                exatas.append(r)
            else:
                outras.append(r)
                
        return exatas + outras
    except Exception as e:
        return {"error": str(e)}

def sincronizar_rotas_opentech():
    """
    Sincroniza as rotas da Opentech (sgrRetornaRotasModelo) com um timeout alto (120s)
    e sobrescreve o arquivo rotas_opentech.json localmente.
    """
    import requests, re, json
    import config
    from soap_client import sgr_login
    
    chave = sgr_login()
    if not chave:
        return False, "Falha de autenticação com a Opentech."
        
    body = f"""<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:tem="http://tempuri.org/">
  <soapenv:Header/>
  <soapenv:Body>
    <tem:sgrRetornaRotasModelo>
      <tem:chaveAcesso>{chave}</tem:chaveAcesso>
      <tem:cdpas>{config.CD_PAS}</tem:cdpas>
      <tem:cdcliente>{config.CD_CLIENTE}</tem:cdcliente>
    </tem:sgrRetornaRotasModelo>
  </soapenv:Body>
</soapenv:Envelope>"""

    try:
        r = requests.post(
            config.WS_URL, 
            data=body.encode('utf-8'), 
            headers={"Content-Type": "text/xml;charset=utf-8", "SOAPAction": '"http://tempuri.org/sgrRetornaRotasModelo"'}, 
            timeout=120
        )
        if r.status_code == 200:
            blocks = re.findall(r"<RotaModelo[^>]*>(.*?)</RotaModelo>", r.text, re.DOTALL)
            rotas = []
            for b in blocks:
                cd_rota = re.search(r"<cdRotaModelo>(.*?)</cdRotaModelo>", b)
                ds_rota = re.search(r"<dsRotaModelo>(.*?)</dsRotaModelo>", b)
                cd_orig = re.search(r"<cdCidOrigem>(.*?)</cdCidOrigem>", b)
                cd_dest = re.search(r"<cdCidDestino>(.*?)</cdCidDestino>", b)
                fl_sit = re.search(r"<flSituacao>(.*?)</flSituacao>", b)
                
                # Só importa rotas ativas
                if fl_sit and fl_sit.group(1) == "true" and cd_rota and ds_rota:
                    rotas.append({
                        "cd_rota": int(cd_rota.group(1)),
                        "ds_rota": ds_rota.group(1).strip(),
                        "cd_cidade_origem": int(cd_orig.group(1)) if cd_orig else 0,
                        "cd_cidade_destino": int(cd_dest.group(1)) if cd_dest else 0
                    })
                    
            with open("rotas_opentech.json", "w", encoding="utf-8") as f:
                json.dump(rotas, f, indent=2, ensure_ascii=False)
                
            return True, f"{len(rotas)} rotas atualizadas com sucesso!"
        else:
            return False, f"Erro na Opentech: HTTP {r.status_code}"
    except requests.exceptions.Timeout:
        return False, "A Opentech demorou mais de 2 minutos para responder. Tente novamente mais tarde."
    except Exception as e:
        return False, f"Erro interno: {str(e)}"


def gerar_pdf_ae(cd_viagem, dados_locais=None):
    """
    Gera o PDF da Autorização de Embarque.

    Tenta primeiro buscar os dados atualizados via sgrRetornaAE na Opentech.
    Se falhar (AE simulada ou sem acesso), usa os dados_locais passados como fallback.

    Parâmetros:
        cd_viagem   : int/str — código da viagem/AE na Opentech
        dados_locais: dict   — dados da viagem gravados no banco local (fallback)

    Retorna:
        bytes do PDF gerado, ou None se falhar.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable, PageBreak
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
    import io
    from datetime import datetime

    # ── 1. Tentar buscar dados atualizados da Opentech ──
    dados_api = None
    try:
        res = soap_client.obter_dados_ae(int(cd_viagem))
        if res and "error" not in res:
            dados_api = res
    except Exception:
        pass

    # ── 2. Consolidar dados (API tem prioridade, fallback para local) ──
    loc = dados_locais or {}

    def _val(api_key, local_key=None, default="N/I"):
        v = dados_api.get(api_key) if dados_api else None
        if v:
            return str(v).strip()
        if local_key:
            v2 = loc.get(local_key)
            if v2:
                return str(v2).strip()
        return default

    cd_viagem_str  = str(cd_viagem)
    cd_prog_str    = _val("cd_programacao", "cd_programacao", "—")
    nome_mot       = _val("nome_motorista",  "nome_motorista",  "Não identificado")
    cpf_mot        = _val("cpf_motorista",   "cpf_motorista",   "—")
    placa_cav      = _val("placa_cavalo",    "placa_cavalo",    "—")
    placa_car      = _val("placa_carreta",   "placa_carreta",   "—") or "—"
    origem         = _val("cidade_origem",   "origem",          "—")
    destino        = _val("cidade_destino",  "destino",         "—")
    produto        = _val("produto",         "produto",         "E-commerce")
    nr_isca        = _val("nr_isca",         "numero_isca",     "—")
    ds_rota        = _val("ds_rota",         None,              "—")
    situacao       = _val("ds_situacao",     "status",          "—")
    valor_raw      = _val("valor_carga",     "valor_carga",     "0")
    dt_ini_raw     = _val("dt_prev_ini",     "previsao_inicio", "—")
    dt_fim_raw     = _val("dt_prev_fim",     "previsao_fim",    "—")
    dt_geracao     = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    simulada       = "Simulada" in str(loc.get("status", ""))
    
    trechos_rota   = dados_api.get("trechos_rota", []) if dados_api else loc.get("trechos_rota", [])
    pontos_apoio   = dados_api.get("pontos_apoio", []) if dados_api else loc.get("pontos_apoio", [])

    # Formatar valor
    try:
        valor_fmt = f"R$ {float(valor_raw):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        valor_fmt = valor_raw

    # Formatar datas
    def _fmt_dt(s):
        if not s or s == "—":
            return "—"
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
            try:
                return datetime.strptime(s[:19], fmt).strftime("%d/%m/%Y %H:%M")
            except Exception:
                continue
        return s

    dt_ini_fmt = _fmt_dt(dt_ini_raw)
    dt_fim_fmt = _fmt_dt(dt_fim_raw)

    # ── 3. Montar PDF com reportlab ──
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    styles = getSampleStyleSheet()

    # Paleta de cores
    AZUL_ESCURO  = colors.HexColor("#0D1B2A")
    AZUL_MEDIO   = colors.HexColor("#1A3A5C")
    AZUL_CLARO   = colors.HexColor("#2D6A9F")
    CINZA_CLARO  = colors.HexColor("#F0F4F8")
    CINZA_BORDA  = colors.HexColor("#CBD5E0")
    VERDE        = colors.HexColor("#1A7A4A")
    AMARELO      = colors.HexColor("#D97706")
    BRANCO       = colors.white

    # Estilos customizados
    st_titulo = ParagraphStyle(
        "titulo", parent=styles["Normal"],
        fontSize=14, fontName="Helvetica-Bold",
        textColor=BRANCO, alignment=TA_CENTER, spaceAfter=2
    )
    st_subtitulo = ParagraphStyle(
        "subtitulo", parent=styles["Normal"],
        fontSize=9, fontName="Helvetica",
        textColor=colors.HexColor("#B0C4D8"), alignment=TA_CENTER
    )
    st_sec_header = ParagraphStyle(
        "sec_header", parent=styles["Normal"],
        fontSize=8, fontName="Helvetica-Bold",
        textColor=AZUL_CLARO, spaceBefore=4, spaceAfter=2
    )
    st_label = ParagraphStyle(
        "label", parent=styles["Normal"],
        fontSize=7.5, fontName="Helvetica",
        textColor=colors.HexColor("#718096")
    )
    st_valor = ParagraphStyle(
        "valor", parent=styles["Normal"],
        fontSize=9, fontName="Helvetica-Bold",
        textColor=AZUL_ESCURO
    )
    st_rodape = ParagraphStyle(
        "rodape", parent=styles["Normal"],
        fontSize=7, fontName="Helvetica",
        textColor=colors.HexColor("#A0AEC0"), alignment=TA_CENTER
    )

    elementos = []

    # ────────────────────────────────
    # CABEÇALHO (LOGO BBM + TEXTO)
    # ────────────────────────────────
    import os
    from reportlab.platypus import Image
    
    cor_status_badge = AMARELO if simulada else VERDE
    status_txt = "SIMULADA" if simulada else "ATIVA"
    
    logo_path = os.path.join(os.path.dirname(__file__), "1-removebg-preview.png")
    try:
        logo_flowable = Image(logo_path, width=4*cm, height=1.6*cm)
    except Exception:
        logo_flowable = ""

    st_titulo_header = ParagraphStyle(
        "titulo_header", parent=styles["Normal"],
        fontSize=15, fontName="Helvetica-Bold",
        textColor=AZUL_ESCURO, alignment=TA_CENTER, spaceAfter=2
    )

    header_data = [[
        logo_flowable,
        Paragraph("AUTORIZAÇÃO DE EMBARQUE<br/><font size='10' color='#2D6A9F'>BBM Logística</font>", st_titulo_header),
        Paragraph(f"AE #{cd_viagem_str}", ParagraphStyle(
            "ae_num", parent=styles["Normal"],
            fontSize=16, fontName="Helvetica-Bold",
            textColor=AZUL_ESCURO, alignment=TA_RIGHT
        ))
    ]]
    
    header_table = Table(header_data, colWidths=["30%", "45%", "25%"])
    header_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRANCO),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN",         (0, 0), (0, 0), "LEFT"),
        ("ALIGN",         (1, 0), (1, 0), "CENTER"),
        ("ALIGN",         (2, 0), (2, 0), "RIGHT"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    elementos.append(header_table)

    # Faixa de subtítulo + status (agora com linha abaixo, fundo branco, texto azul claro)
    st_subtitulo_header = ParagraphStyle(
        "subtitulo_header", parent=styles["Normal"],
        fontSize=10, fontName="Helvetica-Bold",
        textColor=AZUL_CLARO, alignment=TA_LEFT
    )
    
    sub_data = [[
        Paragraph("Gestão de Risco e Monitoramento", st_subtitulo_header),
        Paragraph(f"STATUS: {status_txt}", ParagraphStyle(
            "st_badge2", parent=styles["Normal"],
            fontSize=10, fontName="Helvetica-Bold",
            textColor=cor_status_badge, alignment=TA_RIGHT
        ))
    ]]
    sub_table = Table(sub_data, colWidths=["70%", "30%"])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRANCO),
        ("LINEBELOW",  (0, 0), (-1, -1), 1, AZUL_CLARO),
        ("TOPPADDING",    (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    elementos.append(sub_table)
    elementos.append(Spacer(1, 0.4 * cm))

    # ────────────────────────────────
    # IDENTIFICAÇÃO DA AE
    # ────────────────────────────────
    id_data = [
        [
            Paragraph("CÓDIGO DA VIAGEM / AE", st_label),
            Paragraph("Nº PROGRAMAÇÃO", st_label),
            Paragraph("DATA DE GERAÇÃO", st_label),
        ],
        [
            Paragraph(f"#{cd_viagem_str}", st_valor),
            Paragraph(f"#{cd_prog_str}", st_valor),
            Paragraph(dt_geracao, st_valor),
        ],
    ]
    id_table = Table(id_data, colWidths=["33%", "33%", "34%"])
    id_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), CINZA_CLARO),
        ("GRID",          (0, 0), (-1, -1), 0.4, CINZA_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    elementos.append(id_table)
    elementos.append(Spacer(1, 0.35 * cm))

    # ────────────────────────────────
    # SEÇÃO: MOTORISTA
    # ────────────────────────────────
    elementos.append(Paragraph("> MOTORISTA", st_sec_header))
    mot_data = [
        [Paragraph("NOME COMPLETO", st_label), Paragraph("CPF", st_label)],
        [Paragraph(nome_mot.upper(), st_valor), Paragraph(cpf_mot, st_valor)],
    ]
    mot_table = Table(mot_data, colWidths=["65%", "35%"])
    mot_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRANCO),
        ("BOX",           (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.3, CINZA_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.append(mot_table)
    elementos.append(Spacer(1, 0.35 * cm))

    # ────────────────────────────────
    # SEÇÃO: VEÍCULOS
    # ────────────────────────────────
    elementos.append(Paragraph("> VEICULOS", st_sec_header))
    veic_data = [
        [Paragraph("CAVALO MECÂNICO", st_label), Paragraph("CARRETA / REBOQUE", st_label)],
        [Paragraph(placa_cav, st_valor), Paragraph(placa_car, st_valor)],
    ]
    veic_table = Table(veic_data, colWidths=["50%", "50%"])
    veic_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRANCO),
        ("BOX",           (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.3, CINZA_BORDA),
        ("LINEAFTER",     (0, 0), (0, -1),  0.3, CINZA_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.append(veic_table)
    elementos.append(Spacer(1, 0.35 * cm))

    # ────────────────────────────────
    # SEÇÃO: ROTA
    # ────────────────────────────────
    elementos.append(Paragraph("> ROTA DE VIAGEM", st_sec_header))
    rota_data = [
        [
            Paragraph("ORIGEM", st_label),
            Paragraph("", st_label),
            Paragraph("DESTINO", st_label),
        ],
        [
            Paragraph(origem, st_valor),
            Paragraph("  ->  ", ParagraphStyle(
                "seta", parent=styles["Normal"],
                fontSize=16, fontName="Helvetica-Bold", textColor=AZUL_CLARO, alignment=TA_CENTER
            )),
            Paragraph(destino, st_valor),
        ],
    ]
    if ds_rota and ds_rota != "—":
        rota_data.append([
            Paragraph("ROTA MODELO", st_label),
            Paragraph("", st_label),
            Paragraph("", st_label),
        ])
        rota_data.append([
            Paragraph(ds_rota, st_valor),
            Paragraph("", st_valor),
            Paragraph("", st_valor),
        ])

    rota_table = Table(rota_data, colWidths=["44%", "12%", "44%"])
    rota_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRANCO),
        ("BOX",           (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.3, CINZA_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("SPAN",          (0, 2), (2, 2)) if len(rota_data) > 2 else ("VALIGN", (0, 0), (0, 0), "TOP"),
        ("SPAN",          (0, 3), (2, 3)) if len(rota_data) > 3 else ("VALIGN", (0, 0), (0, 0), "TOP"),
    ]))
    elementos.append(rota_table)
    elementos.append(Spacer(1, 0.35 * cm))

    # ────────────────────────────────
    # SEÇÃO: DATAS
    # ────────────────────────────────
    elementos.append(Paragraph("> PREVISAO DE VIAGEM", st_sec_header))
    datas_data = [
        [Paragraph("INÍCIO PREVISTO", st_label), Paragraph("FIM PREVISTO", st_label)],
        [Paragraph(dt_ini_fmt, st_valor), Paragraph(dt_fim_fmt, st_valor)],
    ]
    datas_table = Table(datas_data, colWidths=["50%", "50%"])
    datas_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRANCO),
        ("BOX",           (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.3, CINZA_BORDA),
        ("LINEAFTER",     (0, 0), (0, -1),  0.3, CINZA_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.append(datas_table)
    elementos.append(Spacer(1, 0.35 * cm))

    # ────────────────────────────────
    # SEÇÃO: CARGA E ISCA
    # ────────────────────────────────
    elementos.append(Paragraph("> CARGA E RASTREAMENTO", st_sec_header))
    carga_data = [
        [
            Paragraph("PRODUTO / TIPO DE CARGA", st_label),
            Paragraph("VALOR DA CARGA", st_label),
            Paragraph("NÚMERO DA ISCA", st_label),
        ],
        [
            Paragraph(produto, st_valor),
            Paragraph(valor_fmt, ParagraphStyle(
                "valor_destaque", parent=styles["Normal"],
                fontSize=10, fontName="Helvetica-Bold",
                textColor=VERDE
            )),
            Paragraph(nr_isca if nr_isca != "—" else "Não informada", st_valor),
        ],
    ]
    carga_table = Table(carga_data, colWidths=["35%", "30%", "35%"])
    carga_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), BRANCO),
        ("BOX",           (0, 0), (-1, -1), 0.5, CINZA_BORDA),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.3, CINZA_BORDA),
        ("LINEAFTER",     (0, 0), (0, -1),  0.3, CINZA_BORDA),
        ("LINEAFTER",     (1, 0), (1, -1),  0.3, CINZA_BORDA),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    elementos.append(carga_table)
    elementos.append(Spacer(1, 0.6 * cm))

    # ────────────────────────────────
    # SEÇÃO: TRECHOS DA ROTA E PONTOS DE APOIO
    # ────────────────────────────────
    if trechos_rota or pontos_apoio:
        elementos.append(PageBreak())

    if trechos_rota:
        elementos.append(Paragraph("> TRECHOS DA ROTA", st_sec_header))
        elementos.append(Spacer(1, 0.2 * cm))
        st_bullet = ParagraphStyle(
            "st_bullet",
            parent=st_valor,
            leftIndent=15,
            spaceAfter=4
        )
        for trecho in trechos_rota:
            municipio = trecho.get("Municipio", "")
            ruas = ", ".join(trecho.get("Ruas", []))
            elementos.append(Paragraph(f"• <b>{municipio}:</b> {ruas}", st_bullet))
        
        elementos.append(Spacer(1, 0.6 * cm))

    if pontos_apoio:
        elementos.append(Paragraph("> LOCAIS DE PARADA PERMITIDOS", st_sec_header))
        elementos.append(Spacer(1, 0.2 * cm))
        for ponto in pontos_apoio:
            fantasia = ponto.get("fantasia", "")
            cidade_uf = f"{ponto.get('cidade', '')}/{ponto.get('uf', '')}"
            tipo = ponto.get("tipo", "")
            fone = f"({ponto.get('ddd', '')}) {ponto.get('telefone', '')}" if ponto.get('telefone') else ""
            km = str(ponto.get("km", ""))
            
            ponto_str = f"• <b>{fantasia}</b> - {cidade_uf} - {tipo}"
            if fone:
                ponto_str += f" - Tel: {fone}"
            if km and km != "0" and km != "0.0":
                ponto_str += f" - KM: {km}"
                
            elementos.append(Paragraph(ponto_str, st_bullet))

        elementos.append(Spacer(1, 0.6 * cm))

    # ────────────────────────────────
    # AVISO SIMULAÇÃO (se aplicável)
    # ────────────────────────────────
    if simulada:
        aviso_data = [[
            Paragraph(
                "ATENCAO: Esta AE foi gerada em MODO DE SIMULACAO e nao possui efeito real "
                "no sistema Opentech. Use apenas para fins de teste.",
                ParagraphStyle(
                    "aviso", parent=styles["Normal"],
                    fontSize=8, fontName="Helvetica-Bold",
                    textColor=AMARELO, alignment=TA_CENTER
                )
            )
        ]]
        aviso_table = Table(aviso_data, colWidths=["100%"])
        aviso_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), colors.HexColor("#FFF3CD")),
            ("BOX",           (0, 0), (-1, -1), 0.8, AMARELO),
            ("TOPPADDING",    (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING",   (0, 0), (-1, -1), 12),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
        ]))
        elementos.append(aviso_table)
        elementos.append(Spacer(1, 0.4 * cm))

    # ────────────────────────────────
    # CONTATOS OPENTECH
    # ────────────────────────────────
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=CINZA_BORDA))
    elementos.append(Spacer(1, 0.4 * cm))
    elementos.append(Paragraph("<b>📞 Central Opentech – Plantão 24h</b>", st_valor))
    elementos.append(Paragraph("+55 47 3481-6122", st_valor))
    elementos.append(Spacer(1, 0.2 * cm))
    elementos.append(Paragraph("<b>📞 Outros contatos da Central Opentech</b>", st_valor))
    elementos.append(Paragraph("47 2101-6122", st_valor))
    elementos.append(Paragraph("47 3481-6100", st_valor))
    elementos.append(Spacer(1, 0.6 * cm))

    # ────────────────────────────────
    # RODAPÉ
    # ────────────────────────────────
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=CINZA_BORDA))
    elementos.append(Spacer(1, 0.2 * cm))
    elementos.append(Paragraph(
        f"Autorização de Embarque - Dialogo Logistica  |  {dt_geracao}  |  AE #{cd_viagem_str}",
        st_rodape
    ))
    elementos.append(Paragraph(
        "Este documento é de uso interno. Em caso de dúvidas, contate a equipe de Gestão de Risco.",
        st_rodape
    ))

    # ────────────────────────────────
    # MENSAGEM / POSTER FINAL
    # ────────────────────────────────
    poster_path = os.path.join(os.path.dirname(__file__), "assets", "regras_ouro.jpg")
    if os.path.exists(poster_path):
        try:
            elementos.append(PageBreak())
            poster_img = Image(poster_path, width=17.4*cm, height=25*cm, kind='proportional')
            elementos.append(poster_img)
        except Exception as e:
            logging.getLogger("services").error(f"Erro ao inserir poster na AE #{cd_viagem}: {e}")

    # ── 4. Construir e retornar bytes ──
    try:
        doc.build(elementos)
        buffer.seek(0)
        return buffer.read()
    except Exception as e:
        logging.getLogger("services").error(f"Erro ao gerar PDF da AE #{cd_viagem}: {e}")
        return None



