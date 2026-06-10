import os
import hashlib
import psycopg2
import psycopg2.extras

try:
    import streamlit as st
    SUPABASE_URL = os.environ.get("SUPABASE_URL", st.secrets.get("SUPABASE_URL", ""))
except Exception:
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")

# Fallback para SQLite local caso o Postgres não esteja configurado
# Isso evita o sistema quebrar completamente se o usuário ainda não colocou o SUPABASE_URL
IS_POSTGRES = bool(SUPABASE_URL)

if not IS_POSTGRES:
    import sqlite3

def get_db_pool():
    if not IS_POSTGRES: return None
    try:
        import streamlit as st
        # Utiliza cache_resource para manter a pool viva entre as interações do usuário
        @st.cache_resource
        def _create_pool():
            from psycopg2.pool import ThreadedConnectionPool
            return ThreadedConnectionPool(1, 20, SUPABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        return _create_pool()
    except Exception:
        # Fallback se Streamlit não estiver em contexto ativo
        global _fallback_pool
        if '_fallback_pool' not in globals():
            from psycopg2.pool import ThreadedConnectionPool
            _fallback_pool = ThreadedConnectionPool(1, 20, SUPABASE_URL, cursor_factory=psycopg2.extras.DictCursor)
        return _fallback_pool

def get_connection():
    if IS_POSTGRES:
        pool = get_db_pool()
        conn = pool.getconn()
        return ConnWrapper(conn, pool=pool)
    else:
        conn = sqlite3.connect("guard_gr.db")
        conn.row_factory = sqlite3.Row
        return ConnWrapper(conn)

class DBWrapper:
    """Wrapper para unificar sintaxe do Postgres e SQLite"""
    def __init__(self, cursor):
        self.cursor = cursor

    def execute(self, query, params=None):
        if not IS_POSTGRES:
            # Converte sintaxe Postgres (%s) para SQLite (?)
            if params:
                query = query.replace("%s", "?")
            # Trata o RETURNING id
            is_returning = "RETURNING id" in query
            if is_returning:
                query = query.replace("RETURNING id", "").strip()
            
            self.cursor.execute(query, params or ())
            
            if is_returning:
                self.last_id = self.cursor.lastrowid
        else:
            self.cursor.execute(query, params or ())
            
    def fetchone(self):
        if not IS_POSTGRES and hasattr(self, 'last_id'):
            res = {"id": self.last_id, 0: self.last_id}
            del self.last_id
            return res
        return self.cursor.fetchone()

    def fetchall(self):
        return self.cursor.fetchall()
        
    @property
    def rowcount(self):
        return self.cursor.rowcount

class ConnWrapper:
    """Wrapper para unificar connection do Postgres e SQLite"""
    def __init__(self, conn, pool=None):
        self.conn = conn
        self.pool = pool
        
    def cursor(self):
        return DBWrapper(self.conn.cursor())
        
    def commit(self):
        self.conn.commit()
        
    def close(self):
        if self.pool:
            self.pool.putconn(self.conn)
        else:
            self.conn.close()

def init_db():
    try:
        conn = get_connection()
    except Exception as e:
        import streamlit as st
        st.error(f"ERRO DE CONEXÃO COM O BANCO DE DADOS: {str(e)}")
        st.stop()
    # Usando o wrapper nativo só para a criação
    cursor = conn.cursor()

    # Tipos e restrições dependem do banco
    PKEY = "SERIAL PRIMARY KEY" if IS_POSTGRES else "INTEGER PRIMARY KEY AUTOINCREMENT"

    # Tabela de Empresas
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS empresas (
            id {PKEY},
            nome TEXT NOT NULL,
            logo_url TEXT,
            cor_primaria TEXT DEFAULT '#003366',
            cor_secundaria TEXT DEFAULT '#f0f2f6',
            compartilhar_historico INTEGER DEFAULT 0,
            limite_advertencias INTEGER DEFAULT 3,
            intervalo_dias_regra INTEGER DEFAULT 90,
            limite_suspensoes_exclusao INTEGER DEFAULT 3,
            dias_susp_1 INTEGER DEFAULT 7,
            dias_susp_2 INTEGER DEFAULT 15
        )
    ''')

    # Tabela de Usuários
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS usuarios (
            id {PKEY},
            nome TEXT NOT NULL,
            login TEXT UNIQUE NOT NULL,
            senha TEXT NOT NULL,
            empresa_id INTEGER,
            role TEXT DEFAULT 'Portaria',
            cpf TEXT,
            data_nascimento TEXT,
            email TEXT,
            FOREIGN KEY (empresa_id) REFERENCES empresas (id)
        )
    ''')

    # Tabela de Motoristas
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS motoristas (
            id {PKEY},
            nome TEXT NOT NULL,
            cpf TEXT NOT NULL,
            cnh TEXT,
            categoria TEXT,
            status_interno TEXT DEFAULT 'Ativo',
            status_sil TEXT DEFAULT 'Não consultado',
            data_consulta_sil TEXT,
            data_fim_suspensao TEXT,
            data_expiracao TEXT,
            empresa_id INTEGER,
            UNIQUE(cpf, empresa_id),
            FOREIGN KEY (empresa_id) REFERENCES empresas (id)
        )
    ''')

    # Tabela de Veículos
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS veiculos (
            id {PKEY},
            placa TEXT NOT NULL,
            tipo_veiculo TEXT,
            status_sil TEXT DEFAULT 'Não consultado',
            validade TEXT,
            ultima_posicao TEXT,
            status_checklist TEXT,
            data_consulta TEXT,
            empresa_id INTEGER,
            rastreadores TEXT,
            segundo_rastreador TEXT,
            UNIQUE(placa, empresa_id),
            FOREIGN KEY (empresa_id) REFERENCES empresas (id)
        )
    ''')

    # Tabela de Ocorrências
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS ocorrencias (
            id {PKEY},
            tipo TEXT NOT NULL,
            motivo TEXT,
            gravidade TEXT,
            data TEXT NOT NULL,
            usuario_id INTEGER,
            motorista_id INTEGER,
            empresa_id INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (motorista_id) REFERENCES motoristas (id),
            FOREIGN KEY (empresa_id) REFERENCES empresas (id)
        )
    ''')

    # Histórico de Consultas
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS registros_acesso (
            id {PKEY},
            motorista_id INTEGER,
            cpf TEXT,
            status_resultado TEXT,
            data_hora TEXT,
            usuario_id INTEGER,
            empresa_id INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id),
            FOREIGN KEY (motorista_id) REFERENCES motoristas (id),
            FOREIGN KEY (empresa_id) REFERENCES empresas (id)
        )
    ''')

    # Viagens
    cursor.execute(f'''
        CREATE TABLE IF NOT EXISTS viagens (
            id {PKEY},
            cd_programacao INTEGER,
            cd_viagem INTEGER,
            cpf_motorista TEXT NOT NULL,
            nome_motorista TEXT,
            placa_cavalo TEXT NOT NULL,
            placa_carreta TEXT,
            origem TEXT,
            destino TEXT,
            valor_carga REAL,
            produto TEXT,
            previsao_inicio TEXT,
            previsao_fim TEXT,
            numero_isca TEXT,
            status TEXT DEFAULT 'Ativa',
            data_criacao TEXT,
            empresa_id INTEGER,
            usuario_id INTEGER,
            FOREIGN KEY (empresa_id) REFERENCES empresas (id),
            FOREIGN KEY (usuario_id) REFERENCES usuarios (id)
        )
    ''')

    conn.commit()

    # Verificar se a tabela de empresas está vazia para popular
    cursor.execute('SELECT COUNT(*) FROM empresas')
    count = cursor.fetchone()
    if (isinstance(count, (list, tuple)) and count[0] == 0) or (isinstance(count, dict) and list(count.values())[0] == 0) or (isinstance(count, int) and count == 0):
        seed_data(conn)
    elif count is not None and hasattr(count, '__getitem__') and count[0] == 0:
        seed_data(conn)
    # Auto-migration for missing columns (Streamlit Cloud Postgres update)
    def add_col_if_needed(table, col, dtype):
        try:
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col} {dtype}")
            conn.commit()
        except Exception:
            try:
                conn.conn.rollback()
            except Exception:
                pass

    add_col_if_needed('empresas', 'compartilhar_historico', 'INTEGER DEFAULT 0')
    add_col_if_needed('empresas', 'limite_advertencias', 'INTEGER DEFAULT 3')
    add_col_if_needed('empresas', 'intervalo_dias_regra', 'INTEGER DEFAULT 90')
    add_col_if_needed('empresas', 'limite_suspensoes_exclusao', 'INTEGER DEFAULT 3')
    add_col_if_needed('empresas', 'dias_susp_1', 'INTEGER DEFAULT 7')
    add_col_if_needed('empresas', 'dias_susp_2', 'INTEGER DEFAULT 15')
    
    add_col_if_needed('usuarios', 'cpf', 'TEXT')
    add_col_if_needed('usuarios', 'data_nascimento', 'TEXT')
    add_col_if_needed('usuarios', 'email', 'TEXT')
    
    add_col_if_needed('motoristas', 'status_interno', "TEXT DEFAULT 'Ativo'")
    add_col_if_needed('motoristas', 'status_sil', "TEXT DEFAULT 'Não consultado'")
    add_col_if_needed('motoristas', 'data_consulta_sil', 'TEXT')
    add_col_if_needed('motoristas', 'data_fim_suspensao', 'TEXT')
    add_col_if_needed('motoristas', 'data_expiracao', 'TEXT')
    add_col_if_needed('motoristas', 'empresa_id', 'INTEGER')
    
    add_col_if_needed('registros_acesso', 'empresa_id', 'INTEGER')
    
    add_col_if_needed('veiculos', 'rastreadores', 'TEXT')
    add_col_if_needed('veiculos', 'segundo_rastreador', 'TEXT')
    
    conn.close()

def seed_data(conn):
    cursor = conn.cursor()
    
    # Inserir Empresa DLG
    cursor.execute('''
        INSERT INTO empresas (nome, logo_url, cor_primaria, cor_secundaria)
        VALUES (%s, %s, %s, %s) RETURNING id
    ''', ('DLG', '', '#004085', '#FFFFFF'))
    row = cursor.fetchone()
    dlg_id = row[0] if row else 1

    senha_hash = hashlib.sha256("admin123".encode()).hexdigest()
    
    cursor.execute('''
        INSERT INTO usuarios (nome, login, senha, empresa_id, role)
        VALUES (%s, %s, %s, %s, %s)
    ''', ('Administrador DLG', 'admin', senha_hash, dlg_id, 'Admin'))

    # Logistica Express
    cursor.execute('''
        INSERT INTO empresas (nome, logo_url, cor_primaria, cor_secundaria)
        VALUES (%s, %s, %s, %s) RETURNING id
    ''', ('Logistica Express', 'https://via.placeholder.com/150', '#FF5733', '#FFFFFF'))
    row = cursor.fetchone()
    log_exp_id = row[0] if row else 2

    cursor.execute('''
        INSERT INTO usuarios (nome, login, senha, empresa_id, role)
        VALUES (%s, %s, %s, %s, %s)
    ''', ('Admin Express', 'admin_exp', senha_hash, log_exp_id, 'Admin'))

    conn.commit()
    print("Banco de dados inicializado e populado com dados de exemplo.")

if __name__ == "__main__":
    init_db()
