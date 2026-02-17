"""Aplicação principal - Gestão de Associados."""

import re
from datetime import date
import streamlit as st
import streamlit_authenticator as stauth

from db import (
    carregar_credenciais,
    inserir_usuario,
    init_db,
    obter_login_id,
    inserir_associado,
    atualizar_senha_usuario,
    verificar_usuario_existe,
    existe_solicitacao_troca_senha_pendente,
)

from area_associado import area_associado
from area_admin import area_admin
from dialogs import dialog_cadastro_sucesso, dialog_usuario_ja_existe
from helpers import esconder_botao_fechar_dialog


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

    # Prepara autenticador
    credentials = carregar_credenciais()
    authenticator = stauth.Authenticate(
        credentials,
        "gestao_associado_cookie",
        "chave_assinatura_segura_1234567890abcdef",
        cookie_expiry_days=30,
    )

    name = st.session_state.get("name")
    authentication_status = st.session_state.get("authentication_status")
    username = st.session_state.get("username")

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
    """Renderiza a aba de recuperação de senha."""
    st.markdown("### Solicitar ou redefinir senha")
    # Limpa campos após rerun, se necessário
    limpar = st.session_state.pop("limpar_campos_esqueceu_senha", False)
    # Inicializa valores default para evitar UnboundLocalError
    cpf_value = ""
    obs_value = "Favor me avisar via WhatsApp quando aprovar."
    nova_senha_value = ""
    conf_senha_value = ""
    if not limpar:
        st.info("Digite seu CPF para solicitar a troca de senha ou redefinir caso já aprovada pelo administrador.")
        cpf_value = st.session_state.get("rec_cpf", "")
        obs_value = st.session_state.get("rec_obs", "Favor me avisar via WhatsApp quando aprovar.")
        nova_senha_value = st.session_state.get("rec_nova_senha", "")
        conf_senha_value = st.session_state.get("rec_conf_senha", "")
    # Não modificar session_state['rec_cpf'] após o widget ser instanciado
    cpf_recuperacao = st.text_input("CPF", help="Digite apenas números", key="rec_cpf", value=cpf_value)
    from db import obter_login_id, inserir_solicitacao_troca_senha

    if cpf_recuperacao:
        cpf_digits = re.sub(r"\D", "", cpf_recuperacao or "")
        if len(cpf_digits) == 11:
            usuario_id = obter_login_id(cpf_digits)
            if not usuario_id:
                st.error("CPF não encontrado no sistema.")
                return
            # Verifica se há solicitação aprovada
            from db import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT status FROM solicitacoes_troca_senha
                        WHERE usuario_id = %s
                        ORDER BY data_solicitacao DESC LIMIT 1
                    """, (usuario_id,))
                    row = cur.fetchone()
            if row and row["status"] == "aprovado":
                if not st.session_state.get("senha_redefinida_sucesso"):
                    if not st.session_state.get("mostrar_dialog_solicitacao_aprovada"):
                        st.session_state["mostrar_dialog_solicitacao_aprovada"] = True
                        from dialogs import dialog_solicitacao_aprovada
                        dialog_solicitacao_aprovada()
                        
                    nova_senha_rec = st.text_input("Nova senha", type="password", key="rec_nova_senha")
                    confirma_senha_rec = st.text_input("Confirmar nova senha", type="password", key="rec_conf_senha")
                    submitted_rec = st.button("Redefinir senha", key="btn_redefinir")
                    if submitted_rec:
                        if not nova_senha_rec or not confirma_senha_rec:
                            st.error("Preencha todos os campos.")
                        elif nova_senha_rec != confirma_senha_rec:
                            st.error("As senhas não conferem.")
                        elif len(nova_senha_rec) < 4:
                            st.error("A senha deve ter no mínimo 4 caracteres.")
                        else:
                            try:
                                senha_hash = stauth.Hasher.hash_list([nova_senha_rec])[0]
                                atualizar_senha_usuario(cpf_digits, senha_hash)
                                # Atualiza status da solicitação para 'finalizado'
                                with get_connection() as conn:
                                    with conn.cursor() as cur:
                                        cur.execute("""
                                            UPDATE solicitacoes_troca_senha
                                            SET status = 'finalizado', data_resposta = CURRENT_TIMESTAMP
                                            WHERE usuario_id = %s AND status = 'aprovado'
                                        """, (usuario_id,))
                                        conn.commit()
                                st.session_state["senha_redefinida_sucesso"] = True
                                st.success("✅ Senha redefinida com sucesso! Faça login com sua nova senha.")
                            except Exception as e:
                                st.error(f"Erro ao redefinir senha: {e}")
                # Não exibe mais o dialog_senha_redefinida automaticamente

            else:
                st.info("Se deseja trocar a senha, solicite ao administrador.")
                observacao = st.text_area(
                    "Observação (opcional)",
                    value=obs_value,
                    key="rec_obs"
                )
                submitted_solic = st.button("Solicitar troca de senha", key="btn_solicitar_troca")
                if submitted_solic:
                    from db import existe_solicitacao_troca_senha_pendente
                    if existe_solicitacao_troca_senha_pendente(usuario_id):
                        st.warning("Já existe uma solicitação de troca de senha pendente para este usuário. Aguarde a aprovação do administrador.")
                    else:
                        try:
                            solicitacao_id = inserir_solicitacao_troca_senha(usuario_id, observacao)
                            from dialogs import dialog_solicitacao_troca_senha
                            dialog_solicitacao_troca_senha()
                            st.session_state["mostrar_dialog_solicitacao_troca_senha"] = True
                        except Exception as e:
                            st.error(f"Erro ao registrar solicitação: {e}")
            # Não limpar session_state diretamente após renderização dos widgets para evitar StreamlitAPIException
            # Toda limpeza é feita apenas via value= nos widgets, controlado pelo flag 'limpar_campos_esqueceu_senha'
        elif len(cpf_digits) > 0:
            if not limpar:
                st.warning("CPF deve conter 11 dígitos.")


if __name__ == "__main__":
    main()
