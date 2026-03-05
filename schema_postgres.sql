-- Criação do banco de dados (execute conectado ao banco postgres como superusuário)
-- Ajuste o OWNER se necessário
CREATE DATABASE gestao_associado_novo;

-- Depois de criar o banco, conecte-se a ele e crie a tabela login:
-- \c gestao_associado_novo

CREATE TABLE IF NOT EXISTS login (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    nome     VARCHAR(100)      NOT NULL,
    senha_hash VARCHAR(255)    NOT NULL,
    ativo    BOOLEAN           NOT NULL DEFAULT TRUE
);

-- Usuário admin de exemplo (senha: 1234, hash gerado por streamlit-authenticator / bcrypt)
INSERT INTO login (username, nome, senha_hash, ativo)
VALUES (
    'admin',
    'Administrador',
    '$2b$12$78DTTvYLYXqjbw2T.PCRn.p7KLcghBdjUwP6ZvMOJu.TvNpsShqhC',
    TRUE
)
ON CONFLICT (username) DO NOTHING;

-- Tabela para tokens de redefinição de senha por e-mail
CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id SERIAL PRIMARY KEY,
    login_id INTEGER NOT NULL REFERENCES login(id) ON DELETE CASCADE,
    token VARCHAR(16) NOT NULL,
    usado BOOLEAN NOT NULL DEFAULT FALSE,
    criado_em TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expira_em TIMESTAMP WITH TIME ZONE NOT NULL,
    usado_em TIMESTAMP WITH TIME ZONE NULL
);
