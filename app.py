"""Aplicação principal - Gestão de Associados."""

import re
from datetime import date
import streamlit as st
import streamlit_authenticator as stauth
import os

from db import (
    carregar_credenciais,
    inserir_usuario,
    init_db,
    obter_login_id,
    inserir_associado,
    atualizar_senha_usuario,
    verificar_usuario_existe,
)
from db import (
    obter_login_por_email,
    inserir_token_redefinicao,
    obter_token_ativo,
    consumir_token,
)
from area_associado import area_associado
from area_admin import area_admin
from dialogs import dialog_cadastro_sucesso, dialog_usuario_ja_existe
from helpers import esconder_botao_fechar_dialog
from helpers import enviar_email_codigo


# --- Developer hidden panel (access via ?dev=TOKEN) ---------------------------------
def _maybe_render_dev_panel():
    """Renderiza painel de desenvolvedor se query param ?dev=TOKEN corresponder a DEV_KEY."""
    try:
        params = st.experimental_get_query_params()
    except Exception:
        return

    dev_key = os.getenv("DEV_KEY") or (st.secrets.get("DEV_KEY") if hasattr(st, "secrets") else None)
    if not dev_key:
        return

    dev_param = params.get("dev", [None])[0]
    if dev_param != dev_key:
        return

    # Require authenticated developer user
    auth_status = st.session_state.get("authentication_status")
    username = st.session_state.get("username")
    if not auth_status or (username or "").lower() != "developer":
        return

    # Dev panel shown
    st.sidebar.markdown("**Developer mode**")
    with st.sidebar.expander("Dev settings", expanded=True):
        smtp_host = st.text_input("SMTP_HOST", value=os.getenv("SMTP_HOST", ""), key="dev_smtp_host")
        smtp_port = st.text_input("SMTP_PORT", value=os.getenv("SMTP_PORT", "587"), key="dev_smtp_port")
        smtp_user = st.text_input("SMTP_USER", value=os.getenv("SMTP_USER", ""), key="dev_smtp_user")
        smtp_password = st.text_input("SMTP_PASSWORD", value=os.getenv("SMTP_PASSWORD", ""), key="dev_smtp_password")
        email_from = st.text_input("EMAIL_FROM", value=os.getenv("EMAIL_FROM", ""), key="dev_email_from")

        if st.button("Apply to session", key="dev_apply"):
            os.environ["SMTP_HOST"] = smtp_host
            os.environ["SMTP_PORT"] = smtp_port
            os.environ["SMTP_USER"] = smtp_user
            os.environ["SMTP_PASSWORD"] = smtp_password
            os.environ["EMAIL_FROM"] = email_from
            st.success("Credenciais aplicadas à sessão (variáveis de ambiente do processo).")

        if st.button("Test SMTP connection", key="dev_test_smtp"):
            try:
                import smtplib
                server = smtplib.SMTP(smtp_host, int(smtp_port), timeout=10)
                server.starttls()
                server.login(smtp_user, smtp_password)
                server.quit()
                st.success("Conexão SMTP OK")
            except Exception as e:
                st.error(f"Erro conexão SMTP: {e}")

        # DB test
        if st.button("Test DB connection", key="dev_test_db"):
            try:
                from db import get_connection
                with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT 1")
                        _ = cur.fetchone()
                st.success("Conexão com o banco OK")
            except Exception as e:
                st.error(f"Erro conexão DB: {e}")

# Note: _maybe_render_dev_panel() will be called from `main()` after authentication
# -------------------------------------------------------------------------------------


def main():
    st.set_page_config(page_title="Login", page_icon="🔐", layout="centered")

    # Esconde o botão "X" de diálogos específicos
    esconder_botao_fechar_dialog()

    # Inicializa o banco de dados
    try:
        init_db()
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro ao inicializar o banco de dados: {e}")
        return

    # Cria usuário 'developer' automaticamente se DEV_USER_PASSWORD estiver definido
    dev_pwd = os.getenv("DEV_USER_PASSWORD") or os.getenv("DEV_PASSWORD")
    try:
        if dev_pwd and obter_login_id("developer") is None:
            senha_hash = stauth.Hasher.hash_list([dev_pwd])[0]
            inserir_usuario("developer", "Developer", senha_hash)
    except Exception:
        # ignora erro de criação (p.ex. já existe)
        pass

    # Prepara autenticador
    credentials = carregar_credenciais()
    authenticator = stauth.Authenticate(
        credentials,
        "gestao_associado_cookie",
        "chave_assinatura_mude_isto",
        cookie_expiry_days=30,
    )

    name = st.session_state.get("name")
    authentication_status = st.session_state.get("authentication_status")
    username = st.session_state.get("username")

    # Mostrar painel de desenvolvedor se aplicável (requer login como 'developer')
    _maybe_render_dev_panel()

    # Se já autenticado, redireciona para área adequada
    if authentication_status:
        if (username or "").lower() == "admin":
            area_admin(authenticator)
        else:
            area_associado(authenticator, username or "")
        return

    # Se não autenticado, mostra página de login/cadastro
    st.title("Gestão de Associados")
    aba_login, aba_novo, aba_senha = st.tabs(["Login", "Cadastrar novo associado", "Esqueceu a senha?"])

    with aba_login:
        _render_login_tab(authenticator)

    with aba_novo:
        _render_cadastro_tab()
    
    with aba_senha:
        _render_esqueceu_senha_tab()


def _render_login_tab(authenticator):
    """Renderiza a aba de login."""
    authenticator.login(
        "main",
        fields={
            "Form name": "Login",
            "Username": "CPF",
            "Password": "Senha",
            "Login": "Entrar",
        },
        key="Login",
    )

    name = st.session_state.get("name")
    authentication_status = st.session_state.get("authentication_status")
    username = st.session_state.get("username")

    if authentication_status:
        if (username or "").lower() == "admin":
            area_admin(authenticator)
        else:
            area_associado(authenticator, username or "")
    elif authentication_status is False:
        st.error("Usuário ou senha inválidos")


def _render_cadastro_tab():
    """Renderiza a aba de cadastro de novo associado."""
    st.markdown("### Cadastrar novo associado")

    novo_nome = st.text_input("Nome completo", key="cad_nome")
    cpf_input = st.text_input("CPF", help="Digite apenas números", key="cad_cpf")
    novo_username = st.text_input("Usuário (login)", value=cpf_input, disabled=True)
    nova_senha = st.text_input("Senha", type="password", key="cad_senha")
    nova_senha_conf = st.text_input("Confirmar senha", type="password", key="cad_senha_conf")

    st.subheader("Dados do associado")
    foto_file = st.file_uploader("Foto", type=["jpg", "jpeg", "png"])
    data_nascimento = st.date_input(
        "Data de nascimento",
        min_value=date(1920, 1, 1),
        max_value=date.today(),
        format="DD/MM/YYYY",
        key="cad_data_nascimento",
    )
    email = st.text_input("E-mail", key="cad_email")
    telefone = st.text_input("Telefone/WhatsApp", key="cad_telefone")
    endereco = st.text_area("Endereço", key="cad_endereco")
    
    col_uf, col_cidade = st.columns([1, 3])
    with col_uf:
        estado_uf = st.text_input("UF", max_chars=2, key="cad_uf")
    with col_cidade:
        cidade = st.text_input("Cidade", key="cad_cidade")
    
    situacao_trabalho = st.text_input("Situação de trabalho", key="cad_situacao_trabalho")
    tipo_sanguineo = st.selectbox(
        "Tipo sanguíneo",
        ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
        key="cad_tipo_sanguineo",
    )
    quantidade_filhos = st.number_input(
        "Quantidade de filhos", min_value=0, step=1, key="cad_qtd_filhos"
    )

    identidade_map = {
        "SURDO": "Surdo",
        "SURDOCEGO": "Surdocego",
        "DEFICIENCIA_AUDITIVA": "Deficiência Auditiva (DA)",
        "OUVINTE": "Ouvinte",
    }
    identidade_label_sel = st.selectbox(
        "Identidade", list(identidade_map.values()), key="cad_identidade"
    )

    submitted = st.button("Cadastrar")

    if submitted:
        if not novo_nome or not cpf_input or not nova_senha:
            st.error("Preencha os campos de acesso (nome, CPF e senha).")
        elif nova_senha != nova_senha_conf:
            st.error("As senhas não conferem.")
        else:
            try:
                cpf_digits = re.sub(r"\D", "", cpf_input or "")
                if len(cpf_digits) != 11:
                    raise ValueError("CPF deve conter 11 dígitos.")
                cpf_formatado = (
                    f"{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-{cpf_digits[9:]}"
                )

                novo_username = cpf_digits

                identidade_codigo = None
                for codigo, label in identidade_map.items():
                    if label == identidade_label_sel:
                        identidade_codigo = codigo
                        break
                if identidade_codigo is None:
                    raise ValueError("Identidade inválida selecionada.")
                
                foto_bytes = foto_file.getvalue() if foto_file is not None else None

                senha_hash = stauth.Hasher.hash_list([nova_senha])[0]
                inserir_usuario(novo_username, novo_nome, senha_hash)
                login_id = obter_login_id(novo_username)
                if login_id is None:
                    raise ValueError("Falha ao localizar o usuário recém-criado.")

                inserir_associado(
                    login_id=login_id,
                    cpf=cpf_formatado,
                    nome_completo=novo_nome,
                    data_nascimento=data_nascimento,
                    email=email,
                    telefone=telefone,
                    endereco=endereco,
                    cidade=cidade,
                    estado_uf=estado_uf,
                    situacao_trabalho=situacao_trabalho,
                    tipo_sanguineo=tipo_sanguineo,
                    quantidade_filhos=int(quantidade_filhos),
                    identidade=identidade_codigo,
                    foto_bytes=foto_bytes,
                )

                dialog_cadastro_sucesso()
            except ValueError as e:
                if str(e) == "Usuário já existe":
                    dialog_usuario_ja_existe()
                else:
                    st.error(str(e))
            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao cadastrar usuário: {e}")


def _render_esqueceu_senha_tab():
    """Renderiza a aba de recuperação de senha por e-mail com código de 8 dígitos."""
    st.markdown("### Redefinir senha por e‑mail")
    st.info("Digite o e‑mail cadastrado para receber um código de autenticação de 8 dígitos.")

    email = st.text_input("E-mail", key="rec_email")
    enviar_codigo = st.button("Enviar código", key="btn_enviar_codigo")

    if enviar_codigo:
        if not email:
            st.error("Informe o e‑mail cadastrado.")
        else:
            try:
                dados = obter_login_por_email(email)
                if not dados:
                    st.error("E‑mail não encontrado no sistema.")
                else:
                    login_id = dados["id"]
                    username = dados["username"]
                    nome = dados.get("nome") or username
                    token_info = inserir_token_redefinicao(login_id)
                    
                    codigo = token_info["token"]
                    # Envia e‑mail com o código (pode lançar exceção se SMTP não configurado)
                    enviar_email_codigo(email, nome, codigo)
                    st.success("Código enviado! Verifique sua caixa de entrada (e spam). O código expira em 15 minutos.")
                    # Guarda em session_state para a etapa de validação
                    st.session_state["rec_login_id"] = login_id
                    st.session_state["rec_username"] = username
            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao enviar código: {e}")

    # Etapa de verificação do código e troca de senha
    st.markdown("---")
    st.markdown("#### Validar código e redefinir senha")
    codigo_input = st.text_input("Código de autenticação (8 dígitos)", key="rec_codigo")
    nova_senha_rec = st.text_input("Nova senha", type="password", key="rec_nova_senha")
    confirma_senha_rec = st.text_input("Confirmar nova senha", type="password", key="rec_conf_senha")
    submitted_rec = st.button("Confirmar e redefinir", key="btn_confirmar_codigo")

    if submitted_rec:
        if not codigo_input or not nova_senha_rec or not confirma_senha_rec:
            st.error("Preencha todos os campos.")
        elif nova_senha_rec != confirma_senha_rec:
            st.error("As senhas não conferem.")
        elif len(nova_senha_rec) < 4:
            st.error("A senha deve ter no mínimo 4 caracteres.")
        else:
            try:
                login_id = st.session_state.get("rec_login_id")
                username = st.session_state.get("rec_username")
                if not login_id or not username:
                    st.error("Primeiro solicite o código pelo e‑mail cadastrado.")
                    return

                token_row = obter_token_ativo(login_id, codigo_input)
                if not token_row:
                    st.error("Código inválido, expirado ou já utilizado.")
                    return

                # Atualiza a senha do usuário
                senha_hash = stauth.Hasher.hash_list([nova_senha_rec])[0]
                atualizar_senha_usuario(username, senha_hash)
                consumir_token(login_id, codigo_input)
                st.success("✅ Senha redefinida com sucesso! Faça login com sua nova senha.")
                # Limpa state relacionado
                for k in ("rec_login_id", "rec_username", "rec_email", "rec_codigo"):
                    st.session_state.pop(k, None)
            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao redefinir senha: {e}")


if __name__ == "__main__":
    main()
