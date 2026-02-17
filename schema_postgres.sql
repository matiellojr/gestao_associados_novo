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

INSERT INTO login (username, nome, senha_hash, ativo)
VALUES (
    'admin',
    'Administrador',
    '$2b$12$78DTTvYLYXqjbw2T.PCRn.p7KLcghBdjUwP6ZvMOJu.TvNpsShqhC',
    TRUE
)
ON CONFLICT (username) DO NOTHING;


-- Tabela para solicitações de troca de senha
CREATE TABLE IF NOT EXISTS solicitacoes_troca_senha (
    id SERIAL PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES login(id),
    data_solicitacao TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    status VARCHAR(20) NOT NULL DEFAULT 'pendente', -- pendente, aprovado, rejeitado
    data_resposta TIMESTAMP,
    admin_id INTEGER REFERENCES login(id),
    observacao TEXT
);
