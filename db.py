import os
import re
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import sql


def get_connection():
    """Retorna uma conexão com o PostgreSQL usando variáveis de ambiente.

    Configure as variáveis de ambiente antes de rodar o app:
    - DB_HOST (default: localhost)
    - DB_PORT (default: 5432)
    - DB_NAME (default: gestao_associado_novo)
    - DB_USER (default: postgres)
    - DB_PASSWORD (default: postgres)
    """

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    dbname = os.getenv("DB_NAME", "gestao_associado_novo")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")

    return psycopg2.connect(
        host=host,
        port=port,
        dbname=dbname,
        user=user,
        password=password,
        cursor_factory=RealDictCursor,
    )


def carregar_credenciais() -> Dict[str, Dict[str, Dict[str, str]]]:
    """Carrega usuários ativos da tabela login e monta o dict de credenciais
    esperado pelo streamlit-authenticator.
    Estrutura retornada:
    {
        "usernames": {
            "admin": {"name": "Administrador", "password": "<hash>"},
            ...
        }
    }
    """

    credentials = {"usernames": {}}

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT username, nome, senha_hash, ativo FROM login WHERE ativo = TRUE"
            )
            for row in cur.fetchall():
                username = row["username"]
                nome = row["nome"]
                senha_hash = row["senha_hash"]
                base_entry = {
                    "name": nome,
                    "password": senha_hash,
                }

                # Username exatamente como está no banco (sem máscara)
                credentials["usernames"][username] = base_entry

                # Se for um CPF com 11 dígitos, também aceita o formato 000.000.000-00
                if re.fullmatch(r"\d{11}", username):
                    cpf_formatado = (
                        f"{username[:3]}.{username[3:6]}.{username[6:9]}-"
                        f"{username[9:]}"
                    )
                    # Não sobrescreve se por acaso já existir uma entrada com máscara
                    credentials["usernames"].setdefault(cpf_formatado, base_entry)

    return credentials


def inserir_usuario(username: str, nome: str, senha_hash: str) -> None:
    """Insere um novo usuário na tabela login.

    Não faz hash da senha: recebe o hash pronto.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Verifica se já existe usuário com esse username
            cur.execute(
                "SELECT 1 FROM login WHERE username = %s",
                (username,),
            )
            if cur.fetchone():
                raise ValueError("Usuário já existe")

            cur.execute(
                """
                INSERT INTO login (username, nome, senha_hash, ativo)
                VALUES (%s, %s, %s, TRUE)
                """,
                (username, nome, senha_hash),
            )
            conn.commit()


def obter_login_id(username: str) -> Optional[int]:
    """Retorna o ID do login a partir do username, ou None se não existir."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM login WHERE username = %s", (username,))
            row = cur.fetchone()
            return row["id"] if row else None


def verificar_usuario_existe(username: str) -> bool:
    """Verifica se existe um usuário com o username informado.
    
    Args:
        username: O username (tipicamente CPF sem formatação) a ser verificado
        
    Returns:
        True se o usuário existe, False caso contrário
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM login WHERE username = %s", (username,))
            return cur.fetchone() is not None


def atualizar_senha_usuario(username: str, nova_senha_hash: str) -> None:
    """Atualiza a senha de um usuário existente.
    
    Args:
        username: O username do usuário
        nova_senha_hash: O hash da nova senha (já criptografado)
        
    Raises:
        ValueError: Se o usuário não existir
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Verifica se o usuário existe
            cur.execute("SELECT id FROM login WHERE username = %s", (username,))
            if not cur.fetchone():
                raise ValueError("Usuário não encontrado")
            
            # Atualiza a senha
            cur.execute(
                "UPDATE login SET senha_hash = %s WHERE username = %s",
                (nova_senha_hash, username)
            )
            conn.commit()


def inserir_associado(
    login_id: int,
    cpf: str,
    nome_completo: str,
    data_nascimento,
    email: str,
    telefone: str,
    endereco: str,
    cidade: str,
    estado_uf: str,
    situacao_trabalho: str,
    tipo_sanguineo: str,
    quantidade_filhos: int,
    identidade: str,
    foto_bytes: Optional[bytes],
) -> None:
    """Insere um novo associado vinculado a um login existente.

    Valida duplicidade de CPF.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Verifica se já existe associado com esse CPF
            cur.execute("SELECT 1 FROM associado WHERE cpf = %s", (cpf,))
            if cur.fetchone():
                raise ValueError("CPF já cadastrado")

            cur.execute(
                """
                INSERT INTO associado (
                    login_id,
                    cpf,
                    foto,
                    nome_completo,
                    data_nascimento,
                    email,
                    telefone,
                    endereco,
                    cidade,
                    estado_uf,
                    situacao_trabalho,
                    tipo_sanguineo,
                    quantidade_filhos,
                    identidade
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    login_id,
                    cpf,
                    foto_bytes,
                    nome_completo,
                    data_nascimento,
                    email,
                    telefone,
                    endereco,
                    cidade,
                    estado_uf,
                    situacao_trabalho,
                    tipo_sanguineo,
                    quantidade_filhos,
                    identidade,
                ),
            )
            conn.commit()


def obter_associado_por_login_id(login_id: int) -> Optional[Dict[str, Any]]:
    """Retorna os dados do associado a partir do login_id, ou None se não existir."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM associado WHERE login_id = %s", (login_id,))
            row = cur.fetchone()
            return row


def listar_associados() -> List[Dict[str, Any]]:
    """Retorna a lista de associados com informações básicas e dados de login."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    a.id,
                    a.login_id,
                    a.cpf,
                    a.nome_completo,
                    a.data_nascimento,
                    a.email,
                    a.telefone,
                    a.endereco,
                    a.cidade,
                    a.estado_uf,
                    a.situacao_trabalho,
                    a.tipo_sanguineo,
                    a.quantidade_filhos,
                    a.identidade,
                    a.data_inicio,
                    a.data_desligamento,
                    a.motivo_desligamento,
                    a.situacao_associado,
                    a.tipo_associado,
                    a.ciclo_cobranca,
                    l.username,
                    l.nome AS nome_login
                FROM associado a
                JOIN login l ON a.login_id = l.id
                ORDER BY a.nome_completo
                """
            )
            return cur.fetchall()


def atualizar_associado_completo(
    associado_id: int,
    login_id: int,
    cpf: str,
    nome_completo: str,
    data_nascimento,
    email: str,
    telefone: str,
    endereco: str,
    cidade: str,
    estado_uf: str,
    situacao_trabalho: str,
    tipo_sanguineo: str,
    quantidade_filhos: int,
    identidade: str,
    data_inicio=None,
    data_desligamento=None,
    motivo_desligamento=None,
    situacao_associado=1,
    tipo_associado=2,
    ciclo_cobranca=1,
) -> None:
    """Atualiza todos os dados do associado e mantém username (login) consistente com o CPF.

    - Garante unicidade de CPF na tabela associado.
    - Atualiza o username na tabela login para os dígitos do CPF informado.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Verifica duplicidade de CPF em outros associados
            cur.execute(
                "SELECT id FROM associado WHERE cpf = %s AND id <> %s",
                (cpf, associado_id),
            )
            if cur.fetchone():
                raise ValueError("CPF já cadastrado")

            # Atualiza dados do associado
            cur.execute(
                """
                UPDATE associado
                SET
                    cpf = %s,
                    nome_completo = %s,
                    data_nascimento = %s,
                    email = %s,
                    telefone = %s,
                    endereco = %s,
                    cidade = %s,
                    estado_uf = %s,
                    situacao_trabalho = %s,
                    tipo_sanguineo = %s,
                    quantidade_filhos = %s,
                    identidade = %s,
                    data_inicio = %s,
                    data_desligamento = %s,
                    motivo_desligamento = %s,
                    situacao_associado = %s,
                    tipo_associado = %s,
                    ciclo_cobranca = %s
                WHERE id = %s
                """,
                (
                    cpf,
                    nome_completo,
                    data_nascimento,
                    email,
                    telefone,
                    endereco,
                    cidade,
                    estado_uf,
                    situacao_trabalho,
                    tipo_sanguineo,
                    quantidade_filhos,
                    identidade,
                    data_inicio,
                    data_desligamento,
                    motivo_desligamento,
                    situacao_associado,
                    tipo_associado,
                    ciclo_cobranca,
                    associado_id,
                ),
            )

            # Atualiza username e nome na tabela login, mantendo CPF (somente dígitos)
            cpf_digits = re.sub(r"\D", "", cpf or "")
            if len(cpf_digits) != 11:
                raise ValueError("CPF deve conter 11 dígitos.")

            cur.execute(
                """
                UPDATE login
                SET username = %s,
                    nome = %s
                WHERE id = %s
                """,
                (cpf_digits, nome_completo, login_id),
            )

            conn.commit()


def init_db() -> None:
    """Garante que o banco gestao_associado_novo e a tabela login existam.

    Executa apenas comandos idempotentes (CREATE IF NOT EXISTS / ON CONFLICT DO NOTHING).
    """

    host = os.getenv("DB_HOST", "localhost")
    port = int(os.getenv("DB_PORT", "5432"))
    dbname = os.getenv("DB_NAME", "gestao_associado_novo")
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "postgres")

    # 1) Conecta ao banco "postgres" para criar o banco de dados, se não existir
    with psycopg2.connect(
        host=host,
        port=port,
        dbname="postgres",
        user=user,
        password=password,
    ) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,))
            exists = cur.fetchone() is not None
            if not exists:
                cur.execute(
                    sql.SQL("CREATE DATABASE {}" ).format(sql.Identifier(dbname))
                )
            conn.commit()

    # 2) Conecta ao banco de aplicação e cria as tabelas necessárias, se não existirem
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS login (
                    id SERIAL PRIMARY KEY,
                    username   VARCHAR(50) UNIQUE NOT NULL,
                    nome       VARCHAR(100)      NOT NULL,
                    senha_hash VARCHAR(255)      NOT NULL,
                    ativo      BOOLEAN           NOT NULL DEFAULT TRUE
                )
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS associado (
                    id SERIAL PRIMARY KEY,
                    login_id INTEGER NOT NULL REFERENCES login(id) ON DELETE CASCADE,
                    cpf VARCHAR(14) UNIQUE NOT NULL,
                    foto BYTEA,
                    nome_completo VARCHAR(150) NOT NULL,
                    data_nascimento DATE,
                    email VARCHAR(150),
                    telefone VARCHAR(20),
                    endereco TEXT,
                    cidade VARCHAR(100),
                    estado_uf VARCHAR(10),
                    situacao_trabalho VARCHAR(100),
                    tipo_sanguineo VARCHAR(3),
                    quantidade_filhos INTEGER,
                    identidade VARCHAR(30) NOT NULL
                )
                """
            )

            # Garante colunas para bancos já existentes e remove campo combinado antigo
            cur.execute(
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS cidade VARCHAR(100)"
            )
            cur.execute(
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS estado_uf VARCHAR(10)"
            )
            cur.execute(
                "ALTER TABLE associado DROP COLUMN IF EXISTS cidade_uf"
            )
            
            # Adiciona novos campos para gestão de associados (administrador only)
            cur.execute(
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS data_inicio DATE"
            )
            cur.execute(
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS data_desligamento DATE"
            )
            cur.execute(
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS motivo_desligamento TEXT"
            )
            cur.execute(
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS situacao_associado INTEGER DEFAULT 1"
            )
            cur.execute(
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS tipo_associado INTEGER DEFAULT 2"
            )
            cur.execute(
                "ALTER TABLE associado ADD COLUMN IF NOT EXISTS ciclo_cobranca INTEGER DEFAULT 1"
            )

            # Tabelas auxiliares de status
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS status_mensalidade (
                    id SERIAL PRIMARY KEY,
                    descricao VARCHAR(80) UNIQUE NOT NULL
                )
                """
            )
            
            cur.execute(
                """
                INSERT INTO status_mensalidade (id, descricao) VALUES
                (1, 'Não Pago'),
                (2, 'Ainda Falta Pagar!'),
                (3, 'Pago')
                ON CONFLICT (id) DO NOTHING
                """
            )

            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS status_pagamento (
                    id SERIAL PRIMARY KEY,
                    descricao VARCHAR(80) UNIQUE NOT NULL
                )
                """
            )
            
            cur.execute(
                """
                INSERT INTO status_pagamento (id, descricao) VALUES
                (1, 'Pago'),
                (2, 'Não Pago')
                ON CONFLICT (id) DO NOTHING
                """
            )

            # Tabela de pagamento
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS pagamento (
                    id SERIAL PRIMARY KEY,
                    data_pagamento DATE,
                    valor_pagamento NUMERIC(10, 2),
                    status_pagamento_id INTEGER NOT NULL REFERENCES status_pagamento(id),
                    comprovante BYTEA
                )
                """
            )

            # Garante coluna valor_pagamento em bancos já existentes
            cur.execute(
                "ALTER TABLE pagamento ADD COLUMN IF NOT EXISTS valor_pagamento NUMERIC(10, 2)"
            )
            
            # Remove constraint NOT NULL de data_pagamento em bancos já existentes
            cur.execute(
                "ALTER TABLE pagamento ALTER COLUMN data_pagamento DROP NOT NULL"
            )

            # Tabela de mensalidade
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS mensalidade (
                    id SERIAL PRIMARY KEY,
                    associado_id INTEGER NOT NULL REFERENCES associado(id) ON DELETE CASCADE,
                    valor NUMERIC(10, 2) NOT NULL,
                    data_emissao DATE NOT NULL,
                    data_vencimento DATE NOT NULL,
                    status_mensalidade_id INTEGER NOT NULL REFERENCES status_mensalidade(id),
                    pagamento_id INTEGER REFERENCES pagamento(id)
                )
                """
            )

            # Garante que a coluna id de associado tenha default baseado em sequence
            cur.execute(
                "CREATE SEQUENCE IF NOT EXISTS associado_id_seq OWNED BY associado.id"
            )
            cur.execute(
                "ALTER TABLE associado ALTER COLUMN id SET DEFAULT nextval('associado_id_seq')"
            )

            # Usuário admin padrão (senha: 1234) - só insere se não existir
            cur.execute(
                """
                INSERT INTO login (username, nome, senha_hash, ativo)
                VALUES (
                    'admin',
                    'Administrador',
                    '$2b$12$78DTTvYLYXqjbw2T.PCRn.p7KLcghBdjUwP6ZvMOJu.TvNpsShqhC',
                    TRUE
                )
                ON CONFLICT (username) DO NOTHING
                """
            )
            conn.commit()


def listar_associados_contribuintes_habilitados() -> List[Dict[str, Any]]:
    """Retorna lista de associados que são CONTRIBUINTES e estão HABILITADOS."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, cpf, nome_completo
                FROM associado
                WHERE tipo_associado = 2 AND situacao_associado = 1
                ORDER BY nome_completo
                """
            )
            return cur.fetchall()


def inserir_mensalidade(
    associado_id: int,
    valor: float,
    data_vencimento,
    status_mensalidade_id: int = 1,
) -> int:
    """Insere uma nova mensalidade. Data de emissão é sempre a data atual."""
    from datetime import date
    
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Evita duplicidade de mensalidade para o mesmo associado
            # no mesmo mês/ano de vencimento (independente do dia)
            cur.execute(
                """
                SELECT 1
                FROM mensalidade
                WHERE associado_id = %s
                  AND date_trunc('month', data_vencimento) = date_trunc('month', %s::date)
                """,
                (associado_id, data_vencimento),
            )
            if cur.fetchone():
                raise ValueError(
                    "Já existe uma mensalidade para este associado neste mês."
                )

            cur.execute(
                """
                INSERT INTO mensalidade (
                    associado_id,
                    valor,
                    data_emissao,
                    data_vencimento,
                    status_mensalidade_id
                )
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (associado_id, valor, date.today(), data_vencimento, status_mensalidade_id),
            )
            mensalidade_id = cur.fetchone()["id"]
            conn.commit()
            return mensalidade_id


def listar_mensalidades(associado_id: int = None) -> List[Dict[str, Any]]:
    """Retorna lista de mensalidades, opcionalmente filtrada por associado."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            if associado_id:
                cur.execute(
                    """
                    SELECT
                        m.id,
                        m.associado_id,
                        a.nome_completo,
                        m.valor,
                        m.data_emissao,
                        m.data_vencimento,
                        m.status_mensalidade_id,
                        sm.descricao as status_mensalidade,
                        m.pagamento_id,
                        p.data_pagamento,
                        p.status_pagamento_id,
                        sp.descricao as status_pagamento
                    FROM mensalidade m
                    JOIN associado a ON m.associado_id = a.id
                    JOIN status_mensalidade sm ON m.status_mensalidade_id = sm.id
                    LEFT JOIN pagamento p ON m.pagamento_id = p.id
                    LEFT JOIN status_pagamento sp ON p.status_pagamento_id = sp.id
                    WHERE m.associado_id = %s
                    ORDER BY m.data_vencimento DESC
                    """,
                    (associado_id,),
                )
            else:
                cur.execute(
                    """
                    SELECT
                        m.id,
                        m.associado_id,
                        a.nome_completo,
                        m.valor,
                        m.data_emissao,
                        m.data_vencimento,
                        m.status_mensalidade_id,
                        sm.descricao as status_mensalidade,
                        m.pagamento_id,
                        p.data_pagamento,
                        p.status_pagamento_id,
                        sp.descricao as status_pagamento
                    FROM mensalidade m
                    JOIN associado a ON m.associado_id = a.id
                    JOIN status_mensalidade sm ON m.status_mensalidade_id = sm.id
                    LEFT JOIN pagamento p ON m.pagamento_id = p.id
                    LEFT JOIN status_pagamento sp ON p.status_pagamento_id = sp.id
                    ORDER BY m.data_vencimento DESC
                    """
                )
            return cur.fetchall()


def inserir_pagamento(
    data_pagamento,
    status_pagamento_id: int,
    mensalidade_id: int,
    valor_pagamento: Optional[float] = None,
    comprovante_bytes: Optional[bytes] = None,
) -> int:
    """Insere um pagamento e vincula à mensalidade."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Insere pagamento
            cur.execute(
                """
                INSERT INTO pagamento (
                    valor_pagamento,
                    data_pagamento,
                    status_pagamento_id,
                    comprovante
                )
                VALUES (%s, %s, %s, %s)
                RETURNING id
                """,
                (valor_pagamento, data_pagamento, status_pagamento_id, comprovante_bytes),
            )
            pagamento_id = cur.fetchone()["id"]
            
            # Vincula pagamento à mensalidade (sem alterar status)
            cur.execute(
                """
                UPDATE mensalidade
                SET pagamento_id = %s
                WHERE id = %s
                """,
                (pagamento_id, mensalidade_id),
            )
            
            conn.commit()
            return pagamento_id


def atualizar_status_mensalidade(mensalidade_id: int, status_mensalidade_id: int) -> None:
    """Atualiza o status de uma mensalidade."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE mensalidade
                SET status_mensalidade_id = %s
                WHERE id = %s
                """,
                (status_mensalidade_id, mensalidade_id),
            )
            conn.commit()


def inserir_pagamento_inicial(mensalidade_id: int, valor_pagamento: float) -> int:
    """Insere um pagamento inicial com status 'Não Pago' e vincula à mensalidade sem alterar seu status."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Insere pagamento com status "Não Pago" (id=2)
            cur.execute(
                """
                INSERT INTO pagamento (
                    valor_pagamento,
                    data_pagamento,
                    status_pagamento_id,
                    comprovante
                )
                VALUES (%s, NULL, %s, NULL)
                RETURNING id
                """,
                (valor_pagamento, 2),
            )
            pagamento_id = cur.fetchone()["id"]
            
            # Vincula pagamento à mensalidade SEM alterar status
            cur.execute(
                """
                UPDATE mensalidade
                SET pagamento_id = %s
                WHERE id = %s
                """,
                (pagamento_id, mensalidade_id),
            )
            
            conn.commit()
            return pagamento_id


def atualizar_mensalidade(
    mensalidade_id: int,
    valor: float,
    data_vencimento,
) -> None:
    """Atualiza dados básicos de uma mensalidade (valor e vencimento)."""

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE mensalidade
                SET valor = %s,
                    data_vencimento = %s
                WHERE id = %s
                """,
                (valor, data_vencimento, mensalidade_id),
            )
            conn.commit()


def excluir_mensalidade(mensalidade_id: int) -> None:
    """Exclui uma mensalidade pelo ID.

    Caso exista pagamento vinculado, a restrição de integridade referencial
    do banco de dados determinará se a exclusão é permitida.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM mensalidade WHERE id = %s",
                (mensalidade_id,),
            )
            conn.commit()


def atualizar_pagamento(
    pagamento_id: int,
    mensalidade_id: int,
    data_pagamento,
    status_pagamento_id: int,
    valor_pagamento: Optional[float] = None,
    comprovante_bytes: Optional[bytes] = None,
) -> None:
    """Atualiza um registro de pagamento e garante vínculo com a mensalidade.
    
    Atualiza apenas a tabela de pagamento, sem alterar o status da mensalidade.
    """

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Atualiza a tabela pagamento
            cur.execute(
                """
                UPDATE pagamento
                SET data_pagamento = %s,
                    valor_pagamento = %s,
                    status_pagamento_id = %s,
                    comprovante = %s
                WHERE id = %s
                """,
                (data_pagamento, valor_pagamento, status_pagamento_id, comprovante_bytes, pagamento_id),
            )

            # Garante que a mensalidade aponte para este pagamento (sem alterar status)
            cur.execute(
                """
                UPDATE mensalidade
                SET pagamento_id = COALESCE(pagamento_id, %s)
                WHERE id = %s
                """,
                (pagamento_id, mensalidade_id),
            )

            conn.commit()


def buscar_comprovante_pagamento(pagamento_id: int) -> Optional[bytes]:
    """Busca o comprovante (bytes) de um pagamento específico."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT comprovante
                FROM pagamento
                WHERE id = %s
                """,
                (pagamento_id,),
            )
            resultado = cur.fetchone()
            if resultado and resultado["comprovante"]:
                return bytes(resultado["comprovante"])
            return None
