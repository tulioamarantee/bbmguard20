import sqlite3
import hashlib
import os

DB_NAME = "guard_gr.db"

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    db_exists = os.path.exists(DB_NAME)
    conn = get_connection()
    cursor = conn.cursor()

    # Tabela de Empresas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS empresas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    # Garantir colunas adicionais caso a tabela já exista sem elas
    try:
        cursor.execute('ALTER TABLE usuarios ADD COLUMN cpf TEXT')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE usuarios ADD COLUMN data_nascimento TEXT')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE usuarios ADD COLUMN email TEXT')
    except Exception:
        pass

    # Tabela de Motoristas
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS motoristas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            cpf TEXT NOT NULL,
            cnh TEXT,
            categoria TEXT,
            status_interno TEXT DEFAULT 'Ativo',
            status_sil TEXT DEFAULT 'Não consultado',
            data_consulta_sil TEXT,
            data_fim_suspensao TEXT,
            empresa_id INTEGER,
            UNIQUE(cpf, empresa_id),
            FOREIGN KEY (empresa_id) REFERENCES empresas (id)
        )
    ''')

    try:
        cursor.execute('ALTER TABLE motoristas ADD COLUMN data_expiracao TEXT')
    except Exception:
        pass

    # Tabela de Veículos (DLG Check)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS veiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            placa TEXT NOT NULL,
            tipo_veiculo TEXT,
            status_sil TEXT DEFAULT 'Não consultado',
            validade TEXT,
            ultima_posicao TEXT,
            status_checklist TEXT,
            data_consulta TEXT,
            empresa_id INTEGER,
            UNIQUE(placa, empresa_id),
            FOREIGN KEY (empresa_id) REFERENCES empresas (id)
        )
    ''')

    try:
        cursor.execute('ALTER TABLE motoristas ADD COLUMN data_expiracao TEXT')
    except Exception:
        pass

    # Tabela de Veículos (DLG Check)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS veiculos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    
    try:
        cursor.execute('ALTER TABLE veiculos ADD COLUMN rastreadores TEXT')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE veiculos ADD COLUMN segundo_rastreador TEXT')
    except Exception:
        pass


    # Tabela de Ocorrências (Mantida para Fase 2)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ocorrencias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Tabela de Histórico de Consultas / Portaria (Nova funcionalidade)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS registros_acesso (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    # Tabela de Autorizações de Embarque / Viagens (Nova funcionalidade do Projeto Super GR)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS viagens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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

    try:
        cursor.execute('ALTER TABLE viagens ADD COLUMN previsao_fim TEXT')
    except Exception:
        pass
    try:
        cursor.execute('ALTER TABLE viagens ADD COLUMN numero_isca TEXT')
    except Exception:
        pass

    conn.commit()

    if not db_exists:
        seed_data(conn)
    
    conn.close()

def seed_data(conn):
    cursor = conn.cursor()
    
    # Inserir Empresa DLG
    cursor.execute('''
        INSERT INTO empresas (nome, logo_url, cor_primaria, cor_secundaria)
        VALUES (?, ?, ?, ?)
    ''', ('DLG', '', '#004085', '#FFFFFF'))
    dlg_id = cursor.lastrowid

    # Inserir Usuários para DLG (Senha padrão: admin123)
    senha_hash = hashlib.sha256("admin123".encode()).hexdigest()
    
    cursor.execute('''
        INSERT INTO usuarios (nome, login, senha, empresa_id, role)
        VALUES (?, ?, ?, ?, ?)
    ''', ('Administrador DLG', 'admin', senha_hash, dlg_id, 'Admin'))


    # Inserir uma segunda empresa para testar multi-tenancy
    cursor.execute('''
        INSERT INTO empresas (nome, logo_url, cor_primaria, cor_secundaria)
        VALUES (?, ?, ?, ?)
    ''', ('Logistica Express', 'https://via.placeholder.com/150', '#FF5733', '#FFFFFF'))
    log_exp_id = cursor.lastrowid

    cursor.execute('''
        INSERT INTO usuarios (nome, login, senha, empresa_id, role)
        VALUES (?, ?, ?, ?, ?)
    ''', ('Admin Express', 'admin_exp', senha_hash, log_exp_id, 'Admin'))

    conn.commit()
    print("Banco de dados inicializado e populado com dados de exemplo.")

if __name__ == "__main__":
    init_db()
