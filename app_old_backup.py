import re
from datetime import date

import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from db import (
    carregar_credenciais,
    inserir_usuario,
    init_db,
    obter_login_id,
    inserir_associado,
    obter_associado_por_login_id,
    listar_associados,
    atualizar_associado_completo,
    listar_associados_contribuintes_habilitados,
    inserir_mensalidade,
    listar_mensalidades,
    inserir_pagamento,
    atualizar_status_mensalidade,
    atualizar_mensalidade,
    excluir_mensalidade,
    atualizar_pagamento,
)


def _esconder_botao_fechar_dialog() -> None:
    """Esconde o botão "X" de diálogos específicos via CSS.

    Atualmente aplicado ao dialog_sucesso_edicao e ao dialog_erro_pagamento
    (⚠️ Pagamento inválido), usando marcadores internos em cada diálogo.
    """

    st.markdown(
        """
        <style>
        /* Esconde o X do diálogo de sucesso de edição e do diálogo de pagamento inválido */
        div[data-baseweb="modal"]:has(#dialog_sucesso_marker) button[aria-label="Close"],
        div[data-baseweb="modal"]:has(#dialog_pagamento_invalido_marker) button[aria-label="Close"] {
            display: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.dialog("✅ Sucesso!")
def dialog_cadastro_sucesso() -> None:
    st.success("Usuário e associado cadastrados com sucesso!")

    if st.button("OK"):
        # Zera campos de cadastro
        st.session_state["cad_nome"] = ""
        st.session_state["cad_cpf"] = ""
        st.session_state["cad_senha"] = ""
        st.session_state["cad_senha_conf"] = ""
        st.session_state["cad_email"] = ""
        st.session_state["cad_telefone"] = ""
        st.session_state["cad_endereco"] = ""
        st.session_state["cad_cidade"] = ""
        st.session_state["cad_uf"] = ""
        st.session_state["cad_situacao_trabalho"] = ""
        st.session_state["cad_tipo_sanguineo"] = ""
        st.session_state["cad_qtd_filhos"] = 0
        st.session_state["cad_identidade"] = "Surdo"
        st.session_state["cad_data_nascimento"] = date.today()

        # Re-executa a aplicação para refletir os campos limpos
        if hasattr(st, "rerun"):
            st.rerun()
        else:  # compatibilidade com versões mais antigas
            st.experimental_rerun()


@st.dialog("✅ Sucesso!")
def dialog_sucesso_edicao(mensagem: str) -> None:
    """Diálogo genérico de sucesso para edição de associado."""
    # Marcador usado pelo CSS para esconder o botão X apenas neste diálogo
    st.markdown("<div id='dialog_sucesso_marker'></div>", unsafe_allow_html=True)

    st.success(mensagem)

    if st.button("OK"):
        # Remove também a mensagem de banner para não aparecer abaixo da área do administrador
        st.session_state.pop("msg_sucesso", None)
        st.session_state.pop("dialog_sucesso_msg", None)
        st.session_state["mostrar_dialog_sucesso_edicao"] = False
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


@st.dialog("⚠️ Aviso!")
def dialog_usuario_ja_existe() -> None:
    st.error("Usuário já existe.")


@st.dialog("⚠️ Aviso!")
def dialog_mensalidade_duplicada(mensagem: str) -> None:
    """Mostra aviso quando já existe mensalidade no mês para o associado."""

    st.warning(mensagem)

    if st.button("OK"):
        # Apenas fecha o diálogo; nada especial a limpar por enquanto
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


@st.dialog("⚠️ Aviso!")
def dialog_valor_invalido(mensagem: str) -> None:
    """Mostra aviso quando o valor informado é inválido (<= 0)."""

    st.warning(mensagem)

    if st.button("OK"):
        # Apenas fecha o diálogo e força re-renderização da tela atual
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


@st.dialog("⚠️ Pagamento inválido")
def dialog_erro_pagamento(mensagem: str) -> None:
    """Mostra erro de pagamento em um modal separado."""
    # Marcador usado pelo CSS para esconder o botão X apenas neste diálogo
    st.markdown("<div id='dialog_pagamento_invalido_marker'></div>", unsafe_allow_html=True)

    st.error(mensagem)

    if st.button("OK"):
        # Limpa flags e recarrega
        st.session_state.pop("erro_pagamento_msg", None)
        st.session_state.pop("mostrar_dialog_erro_pagamento", None)
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


@st.dialog("Editar Mensalidade")
def dialog_editar_mensalidade(row) -> None:
    """Diálogo de edição de mensalidade com abas para dados e pagamento."""

    from datetime import datetime

    # Cabeçalho combinado, conforme solicitado
    st.markdown(
        f"Associado: {row.get('nome_completo', '')} - Mensalidade Nº {row.get('id')}"
    )

    aba_dados, aba_pagamento = st.tabs(["Dados da Mensalidade", "Pagamento"])

    # ---------------- Aba Dados da Mensalidade -----------------
    with aba_dados:
        # Converte data de vencimento recebida em diferentes formatos
        data_venc_valor = row.get("data_vencimento")
        if isinstance(data_venc_valor, str):
            try:
                data_venc_valor = datetime.strptime(data_venc_valor, "%Y-%m-%d").date()
            except Exception:
                try:
                    data_venc_valor = datetime.fromisoformat(data_venc_valor.split("T")[0]).date()
                except Exception:
                    data_venc_valor = date.today()
        elif hasattr(data_venc_valor, "date"):
            data_venc_valor = data_venc_valor.date()
        elif not isinstance(data_venc_valor, date):
            data_venc_valor = date.today()

        # Apenas o usuário 'admin' pode editar data de vencimento e status
        is_admin_user = (st.session_state.get("username", "").lower() == "admin")

        with st.form("form_editar_mensalidade"):
            # Converte o valor recebido (que pode vir como dict, string, Decimal etc.) para float
            raw_valor = row.get("valor")

            if isinstance(raw_valor, dict):
                # Tenta encontrar um campo numérico comum dentro do dict
                for chave in ("valor", "value", "amount", "numero", "quantia"):
                    if chave in raw_valor and raw_valor[chave] is not None:
                        raw_valor = raw_valor[chave]
                        break

            try:
                valor_inicial = float(raw_valor) if raw_valor is not None else 0.0
            except (TypeError, ValueError):
                valor_inicial = 0.0

            valor = st.number_input(
                "Valor da Mensalidade (R$)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=valor_inicial,
                key=f"edit_mens_valor_{row['id']}",
            )

            data_vencimento = st.date_input(
                "Data de Vencimento",
                value=data_venc_valor,
                format="DD/MM/YYYY",
                key=f"edit_mens_venc_{row['id']}",
                disabled=not is_admin_user,
            )

            # Exibe o status atual da mensalidade (somente leitura)
            status_mens_id_atual = int(row.get("status_mensalidade_id") or 1)
            status_mens_opcoes = [1, 2, 3]
            status_mens_labels = {
                1: "Não Pago",
                2: "Ainda Falta Pagar!",
                3: "Pago",
            }
            st.selectbox(
                "Status da Mensalidade",
                status_mens_opcoes,
                format_func=lambda x: status_mens_labels.get(x, str(x)),
                index=status_mens_opcoes.index(status_mens_id_atual)
                if status_mens_id_atual in status_mens_opcoes
                else 0,
                disabled=not is_admin_user,
                key=f"edit_mens_status_{row['id']}",
                help="Status é atualizado automaticamente conforme o pagamento.",
            )

            col1, col2 = st.columns(2)
            salvar = col1.form_submit_button("Salvar", type="primary", use_container_width=True)
            cancelar = col2.form_submit_button("Cancelar", use_container_width=True)

            if salvar:
                try:
                    if valor <= 0:
                        raise ValueError("Valor deve ser maior que zero.")

                    atualizar_mensalidade(
                        mensalidade_id=int(row["id"]),
                        valor=float(valor),
                        data_vencimento=data_vencimento,
                    )

                    st.session_state["msg_sucesso"] = f"Mensalidade #{row['id']} atualizada com sucesso."
                    # Força recriação da grid de mensalidades para limpar seleção
                    st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
                except ValueError as e:
                    # Mostrar erro de valor em diálogo dedicado
                    if "Valor deve ser maior que zero." in str(e):
                        dialog_valor_invalido(str(e))
                    else:
                        st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao atualizar mensalidade: {e}")
            if cancelar:
                # Ao cancelar, apenas fecha o diálogo e limpa seleção da grid
                st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()

        st.markdown("---")
        st.warning(
            "Cuidado: esta ação excluirá permanentemente a mensalidade selecionada."
        )

        col_exc1, col_exc2 = st.columns([1, 1])
        with col_exc1:
            if st.button(
                "Excluir Mensalidade",
                key=f"btn_excluir_mens_{row['id']}",
                use_container_width=True,
            ):
                try:
                    excluir_mensalidade(int(row["id"]))
                    st.session_state["msg_sucesso"] = (
                        f"Mensalidade #{row['id']} excluída com sucesso."
                    )
                    st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao excluir mensalidade: {e}")

    # ---------------- Aba Pagamento -----------------
    with aba_pagamento:
        pagamento_id = row.get("pagamento_id")

        # Converter data de pagamento
        data_pag_valor = row.get("data_pagamento")
        if isinstance(data_pag_valor, str):
            try:
                data_pag_valor = datetime.strptime(data_pag_valor.split("T")[0], "%Y-%m-%d").date()
            except Exception:
                # Pode vir em outro formato (ex: DD/MM/YYYY)
                try:
                    data_pag_valor = datetime.strptime(data_pag_valor, "%d/%m/%Y").date()
                except Exception:
                    data_pag_valor = date.today()
        elif hasattr(data_pag_valor, "date"):
            data_pag_valor = data_pag_valor.date()
        elif isinstance(data_pag_valor, date):
            pass
        else:
            data_pag_valor = date.today()

        # Determina status inicial do pagamento
        status_desc = (row.get("status_pagamento") or "").strip()
        if status_desc.lower().startswith("pago"):
            status_inicial_id = 1
        elif status_desc:
            status_inicial_id = 2
        else:
            status_inicial_id = 2  # Default: Não Pago

        with st.form(f"form_pag_mensalidade_{row['id']}"):
            # Valor base da mensalidade (para validação)
            raw_valor_mens = row.get("valor")
            try:
                valor_mensalidade_base = float(raw_valor_mens) if raw_valor_mens is not None else 0.0
            except (TypeError, ValueError):
                valor_mensalidade_base = 0.0

            # Campo de valor do pagamento (deve ser igual ao valor da mensalidade)
            try:
                valor_pag_inicial = float(raw_valor_mens) if raw_valor_mens is not None else 0.0
            except (TypeError, ValueError):
                valor_pag_inicial = 0.0

            valor_pagamento = st.number_input(
                "Valor do Pagamento (R$)",
                min_value=0.0,
                step=10.0,
                format="%.2f",
                value=valor_pag_inicial,
                key=f"edit_pag_valor_{row['id']}",
            )

            data_pagamento = st.date_input(
                "Data do Pagamento",
                value=data_pag_valor,
                format="DD/MM/YYYY",
                key=f"edit_pag_data_{row['id']}",
            )

            status_pagamento_id = st.selectbox(
                "Status do Pagamento",
                [1, 2],
                format_func=lambda x: "Pago" if x == 1 else "Não Pago",
                index=0 if status_inicial_id == 1 else 1,
                key=f"edit_pag_status_{row['id']}",
            )

            comprovante_file = st.file_uploader(
                "Anexar comprovante (opcional)",
                key=f"edit_pag_comp_{row['id']}",
            )

            colp1, colp2 = st.columns(2)
            salvar_pag = colp1.form_submit_button(
                "Salvar Pagamento", type="primary", use_container_width=True
            )
            cancelar_pag = colp2.form_submit_button(
                "Cancelar", use_container_width=True
            )

            if salvar_pag:
                try:
                    if not data_pagamento:
                        raise ValueError("Data de pagamento é obrigatória.")

                    # Verifica se o valor do pagamento é igual ao valor da mensalidade
                    if round(float(valor_pagamento), 2) != round(float(valor_mensalidade_base), 2):
                        # Sinaliza para abrir o diálogo de erro fora deste diálogo
                        st.session_state["erro_pagamento_msg"] = (
                            f"Valor do pagamento deve ser igual ao valor da mensalidade (R$ {valor_mensalidade_base:.2f})."
                        )
                        st.session_state["mostrar_dialog_erro_pagamento"] = True

                        # Fecha o diálogo atual, limpa seleção da grid e volta para a tela principal
                        st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                        if hasattr(st, "rerun"):
                            st.rerun()
                        else:
                            st.experimental_rerun()
                        return

                    comprovante_bytes = (
                        comprovante_file.getvalue() if comprovante_file is not None else None
                    )

                    if pagamento_id:
                        atualizar_pagamento(
                            pagamento_id=int(pagamento_id),
                            mensalidade_id=int(row["id"]),
                            data_pagamento=data_pagamento,
                            valor_pagamento=float(valor_pagamento),
                            status_pagamento_id=int(status_pagamento_id),
                            comprovante_bytes=comprovante_bytes,
                        )
                    else:
                        inserir_pagamento(
                            data_pagamento=data_pagamento,
                            status_pagamento_id=int(status_pagamento_id),
                            mensalidade_id=int(row["id"]),
                            valor_pagamento=float(valor_pagamento),
                            comprovante_bytes=comprovante_bytes,
                        )

                    st.session_state["msg_sucesso"] = (
                        f"Pagamento da mensalidade #{row['id']} salvo com sucesso."
                    )
                    st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao salvar pagamento: {e}")
            if cancelar_pag:
                # Fecha o diálogo de pagamento e limpa seleção da grid
                st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()


@st.dialog("Excluir Mensalidade")
def dialog_excluir_mensalidade(row) -> None:
    """Confirmação de exclusão de mensalidade."""

    st.warning(
        f"Tem certeza que deseja excluir a mensalidade #{row.get('id')} do associado "
        f"{row.get('nome_completo', '')}? Esta ação não poderá ser desfeita."
    )

    col1, col2 = st.columns(2)
    excluir = col1.button("Excluir", type="primary", use_container_width=True)
    cancelar = col2.button("Cancelar", use_container_width=True)

    if excluir:
        try:
            excluir_mensalidade(int(row["id"]))
            st.session_state["msg_sucesso"] = f"Mensalidade #{row['id']} excluída com sucesso."
            if hasattr(st, "rerun"):
                st.rerun()
            else:
                st.experimental_rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Erro ao excluir mensalidade: {e}")

    if cancelar:
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


def area_associado(authenticator, username: str) -> None:
    """Área do associado: visualização/edição de dados pessoais."""

    name = st.session_state.get("name") or username

    with st.sidebar:
        st.markdown(f"Usuário: {name}")
        menu = st.radio(
            "Menu",
            ["Dados pessoais", "Mensalidades"],
            key="assoc_menu",
        )
        authenticator.logout("Sair", "sidebar")

    st.header("Área do associado")

    # Exibir mensagem de sucesso se houver
    if "msg_sucesso" in st.session_state:
        st.success(st.session_state["msg_sucesso"])
        st.session_state.pop("msg_sucesso")

    # Garante que buscamos no banco o username somente com dígitos (CPF)
    username_limpo = re.sub(r"\D", "", username or "")
    username_busca = username_limpo if len(username_limpo) == 11 else username

    login_id = obter_login_id(username_busca)
    if login_id is None:
        st.error("Não foi possível localizar o login do associado.")
        return

    associado = obter_associado_por_login_id(login_id)
    if not associado:
        st.warning("Nenhum cadastro de associado encontrado para este usuário.")
        return

    if menu == "Mensalidades":
        st.subheader("Minhas Mensalidades")
        
        try:
            mensalidades = listar_mensalidades(associado_id=associado["id"])
        except Exception as e:  # noqa: BLE001
            st.error(f"Erro ao carregar mensalidades: {e}")
            return
        
        if not mensalidades:
            st.info("Você não possui mensalidades lançadas.")
        else:
            df_mens = pd.DataFrame(mensalidades)
            
            st.dataframe(
                df_mens[[
                    "id",
                    "valor",
                    "data_emissao",
                    "data_vencimento",
                    "status_mensalidade",
                    "status_pagamento",
                ]].rename(columns={
                    "id": "ID",
                    "valor": "Valor (R$)",
                    "data_emissao": "Emissão",
                    "data_vencimento": "Vencimento",
                    "status_mensalidade": "Status",
                    "status_pagamento": "Pagamento",
                }),
                use_container_width=True,
            )
        return

    st.subheader("Dados pessoais")

    identidade_map = {
        "SURDO": "Surdo",
        "SURDOCEGO": "Surdocego",
        "DEFICIENCIA_AUDITIVA": "Deficiência Auditiva (DA)",
        "OUVINTE": "Ouvinte",
    }

    data_nasc_valor = associado.get("data_nascimento") or date(2000, 1, 1)

    with st.form("form_associado_dados"):
        cpf = st.text_input("CPF", value=associado.get("cpf", ""), disabled=True)
        nome_completo = st.text_input(
            "Nome completo",
            value=associado.get("nome_completo", ""),
            key="assoc_nome_completo",
        )
        data_nascimento = st.date_input(
            "Data de nascimento",
            value=data_nasc_valor,
            min_value=date(1920, 1, 1),
            max_value=date.today(),
            format="DD/MM/YYYY",
            key="assoc_data_nascimento",
        )
        email = st.text_input(
            "E-mail",
            value=associado.get("email", ""),
            key="assoc_email",
        )
        telefone = st.text_input(
            "Telefone/WhatsApp",
            value=associado.get("telefone", ""),
            key="assoc_telefone",
        )
        endereco = st.text_area(
            "Endereço",
            value=associado.get("endereco", ""),
            key="assoc_endereco",
        )
        col_uf, col_cidade = st.columns([1, 3])
        with col_uf:
            estado_uf = st.text_input(
                "UF",
                max_chars=2,
                value=associado.get("estado_uf", ""),
                key="assoc_uf",
            )
        with col_cidade:
            cidade = st.text_input(
                "Cidade",
                value=associado.get("cidade", ""),
                key="assoc_cidade",
            )
        situacao_trabalho = st.text_input(
            "Situação de trabalho",
            value=associado.get("situacao_trabalho", ""),
            key="assoc_situacao_trabalho",
        )
        tipo_sanguineo = st.selectbox(
            "Tipo sanguíneo",
            [
                "",
                "A+",
                "A-",
                "B+",
                "B-",
                "AB+",
                "AB-",
                "O+",
                "O-",
            ],
            index=max(
                0,
                [
                    "",
                    "A+",
                    "A-",
                    "B+",
                    "B-",
                    "AB+",
                    "AB-",
                    "O+",
                    "O-",
                ].index(associado.get("tipo_sanguineo") or ""),
            ),
            key="assoc_tipo_sanguineo",
        )

        identidade_codigo_atual = associado.get("identidade") or "SURDO"
        identidade_label_atual = identidade_map.get(identidade_codigo_atual, "Surdo")
        identidade_opcoes = list(identidade_map.values())
        identidade_indice = identidade_opcoes.index(identidade_label_atual)
        identidade_label_sel = st.selectbox(
            "Identidade",
            identidade_opcoes,
            index=identidade_indice,
            key="assoc_identidade",
        )

        quantidade_filhos = st.number_input(
            "Quantidade de filhos",
            min_value=0,
            step=1,
            value=int(associado.get("quantidade_filhos") or 0),
            key="assoc_qtd_filhos",
        )

        submitted = st.form_submit_button("Salvar alterações")

        if submitted:
            try:
                identidade_codigo = None
                for codigo, label in identidade_map.items():
                    if label == identidade_label_sel:
                        identidade_codigo = codigo
                        break
                if identidade_codigo is None:
                    raise ValueError("Identidade inválida selecionada.")

                atualizar_associado_completo(
                    associado_id=associado["id"],
                    login_id=associado["login_id"],
                    cpf=associado["cpf"],
                    nome_completo=nome_completo,
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
                )
                st.session_state["msg_sucesso"] = "Dados atualizados com sucesso."
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao atualizar dados do associado: {e}")




@st.dialog("Editar Associado")
def dialog_editar_associado(row) -> None:
    """Diálogo de edição de associado com abas para dados pessoais e administrativos."""

    # Marcador usado pelo CSS para esconder o botão X apenas neste diálogo
    st.markdown("<div id='dialog_editar_associado_marker'></div>", unsafe_allow_html=True)

    # Marca que o diálogo de associado está aberto para a linha atual
    st.session_state["associado_dialog_active"] = True

    identidade_map = {
        "SURDO": "Surdo",
        "SURDOCEGO": "Surdocego",
        "DEFICIENCIA_AUDITIVA": "Deficiência Auditiva (DA)",
        "OUVINTE": "Ouvinte",
    }

    # Criar abas
    aba_pessoal, aba_admin = st.tabs(["Dados Pessoais", "Dados Administrativos"])
    
    with aba_pessoal:
        # Converter data_nascimento se necessário
        data_nasc_valor = row.get("data_nascimento")
        if data_nasc_valor is None or (isinstance(data_nasc_valor, float) and pd.isna(data_nasc_valor)):
            data_nasc_valor = date(2000, 1, 1)
        elif isinstance(data_nasc_valor, str):
            from datetime import datetime
            try:
                data_nasc_valor = datetime.strptime(data_nasc_valor, "%Y-%m-%d").date()
            except Exception:
                try:
                    data_nasc_valor = datetime.fromisoformat(data_nasc_valor.split("T")[0]).date()
                except Exception:
                    data_nasc_valor = date(2000, 1, 1)
        elif hasattr(data_nasc_valor, "date"):
            data_nasc_valor = data_nasc_valor.date()
        elif not isinstance(data_nasc_valor, date):
            data_nasc_valor = date(2000, 1, 1)

        with st.form("form_dialog_editar_pessoal"):
            cpf = st.text_input(
                "CPF",
                value=str(row.get("cpf", "") or ""),
                key=f"dialog_cpf_{row['id']}",
            )
            nome_completo = st.text_input(
                "Nome completo",
                value=str(row.get("nome_completo", "") or ""),
                key=f"dialog_nome_{row['id']}",
            )
            data_nascimento = st.date_input(
                "Data de nascimento",
                value=data_nasc_valor,
                min_value=date(1920, 1, 1),
                max_value=date.today(),
                format="DD/MM/YYYY",
                key=f"dialog_data_nasc_{row['id']}",
            )
            email = st.text_input(
                "E-mail",
                value=str(row.get("email", "") or ""),
                key=f"dialog_email_{row['id']}",
            )
            telefone = st.text_input(
                "Telefone/WhatsApp",
                value=str(row.get("telefone", "") or ""),
                key=f"dialog_telefone_{row['id']}",
            )
            endereco = st.text_area(
                "Endereço",
                value=str(row.get("endereco", "") or ""),
                key=f"dialog_endereco_{row['id']}",
            )
            col_uf, col_cidade = st.columns([1, 3])
            with col_uf:
                estado_uf = st.text_input(
                    "UF",
                    max_chars=2,
                    value=str(row.get("estado_uf", "") or ""),
                    key=f"dialog_uf_{row['id']}",
                )
            with col_cidade:
                cidade = st.text_input(
                    "Cidade",
                    value=str(row.get("cidade", "") or ""),
                    key=f"dialog_cidade_{row['id']}",
                )
            situacao_trabalho = st.text_input(
                "Situação de trabalho",
                value=str(row.get("situacao_trabalho", "") or ""),
                key=f"dialog_situacao_{row['id']}",
            )
            tipo_sanguineo = st.selectbox(
                "Tipo sanguíneo",
                [
                    "",
                    "A+",
                    "A-",
                    "B+",
                    "B-",
                    "AB+",
                    "AB-",
                    "O+",
                    "O-",
                ],
                index=max(
                    0,
                    [
                        "",
                        "A+",
                        "A-",
                        "B+",
                        "B-",
                        "AB+",
                        "AB-",
                        "O+",
                        "O-",
                    ].index(str(row.get("tipo_sanguineo") or "").strip() if not (isinstance(row.get("tipo_sanguineo"), float) and pd.isna(row.get("tipo_sanguineo"))) else ""),
                ),
                key=f"dialog_tipo_sang_{row['id']}",
            )

            identidade_codigo_atual = row.get("identidade") or "SURDO"
            if isinstance(identidade_codigo_atual, float) and pd.isna(identidade_codigo_atual):
                identidade_codigo_atual = "SURDO"
            identidade_label_atual = identidade_map.get(identidade_codigo_atual, "Surdo")
            identidade_opcoes = list(identidade_map.values())
            identidade_indice = identidade_opcoes.index(identidade_label_atual)
            identidade_label_sel = st.selectbox(
                "Identidade",
                identidade_opcoes,
                index=identidade_indice,
                key=f"dialog_identidade_{row['id']}",
            )

            quantidade_filhos = st.number_input(
                "Quantidade de filhos",
                min_value=0,
                step=1,
                value=int(row.get("quantidade_filhos") or 0) if not (isinstance(row.get("quantidade_filhos"), float) and pd.isna(row.get("quantidade_filhos"))) else 0,
                key=f"dialog_qtd_filhos_{row['id']}",
            )

            col1, col2 = st.columns(2)
            salvar_pessoal = col1.form_submit_button("Salvar", type="primary", use_container_width=True)
            cancelar_pessoal = col2.form_submit_button("Cancelar", use_container_width=True)

            if salvar_pessoal:
                try:
                    identidade_codigo = None
                    for codigo, label in identidade_map.items():
                        if label == identidade_label_sel:
                            identidade_codigo = codigo
                            break
                    if identidade_codigo is None:
                        raise ValueError("Identidade inválida selecionada.")

                    # Converter valores administrativos para tipos Python nativos
                    def safe_convert_date(val):
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            return None
                        if isinstance(val, str):
                            from datetime import datetime
                            try:
                                return datetime.fromisoformat(val.split("T")[0]).date()
                            except:
                                return None
                        if hasattr(val, "date"):
                            return val.date()
                        if isinstance(val, date):
                            return val
                        return None
                    
                    def safe_int(val, default=None):
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            return default
                        return int(val)
                    
                    def safe_str(val):
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            return ""
                        return str(val)

                    atualizar_associado_completo(
                        associado_id=int(row["id"]),
                        login_id=int(row["login_id"]),
                        cpf=cpf,
                        nome_completo=nome_completo,
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
                        data_inicio=safe_convert_date(row.get("data_inicio")),
                        data_desligamento=safe_convert_date(row.get("data_desligamento")),
                        motivo_desligamento=safe_str(row.get("motivo_desligamento")),
                        situacao_associado=safe_int(row.get("situacao_associado"), 1),
                        tipo_associado=safe_int(row.get("tipo_associado"), 2),
                        ciclo_cobranca=safe_int(row.get("ciclo_cobranca"), 1),
                    )
                    mensagem = f"Dados de {row['nome_completo']} atualizados com sucesso."
                    st.session_state["msg_sucesso"] = mensagem
                    st.session_state["dialog_sucesso_msg"] = mensagem
                    st.session_state["mostrar_dialog_sucesso_edicao"] = True
                    st.session_state.pop("last_selected_row_id", None)
                    st.session_state["associado_dialog_active"] = False
                    # Incrementar contador para forçar recriação da grid e limpar seleção
                    st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao atualizar dados pessoais: {e}")

            if cancelar_pessoal:
                st.session_state.pop("last_selected_row_id", None)
                st.session_state["associado_dialog_active"] = False
                st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
                st.rerun()
    
    with aba_admin:
        # Converter datas administrativas
        data_inicio_valor = row.get("data_inicio")
        
        # Tratar casos especiais (dict vazio, NaT, NaN, None)
        if isinstance(data_inicio_valor, dict) or (isinstance(data_inicio_valor, float) and pd.isna(data_inicio_valor)) or pd.isna(data_inicio_valor):
            data_inicio_valor = None
        elif data_inicio_valor is not None and not isinstance(data_inicio_valor, date):
            if isinstance(data_inicio_valor, str):
                from datetime import datetime
                try:
                    data_inicio_valor = datetime.fromisoformat(data_inicio_valor.split("T")[0]).date()
                except:
                    data_inicio_valor = None
            elif hasattr(data_inicio_valor, "date"):
                try:
                    data_inicio_valor = data_inicio_valor.date()
                except:
                    data_inicio_valor = None
        
        data_desligamento_valor = row.get("data_desligamento")
        if isinstance(data_desligamento_valor, dict) or (isinstance(data_desligamento_valor, float) and pd.isna(data_desligamento_valor)) or pd.isna(data_desligamento_valor):
            data_desligamento_valor = None
        elif data_desligamento_valor is not None and not isinstance(data_desligamento_valor, date):
            if isinstance(data_desligamento_valor, str):
                from datetime import datetime
                try:
                    data_desligamento_valor = datetime.fromisoformat(data_desligamento_valor.split("T")[0]).date()
                except:
                    data_desligamento_valor = None
            elif hasattr(data_desligamento_valor, "date"):
                try:
                    data_desligamento_valor = data_desligamento_valor.date()
                except:
                    data_desligamento_valor = None
        
        with st.form("form_dialog_editar_admin"):
            data_inicio = st.date_input(
                "Data de Início",
                value=data_inicio_valor if data_inicio_valor else None,
                format="DD/MM/YYYY",
                key=f"dialog_admin_data_inicio_{row['id']}",
            )
            
            situacao_associado = st.selectbox(
                "Situação do Associado",
                [1, 2],
                format_func=lambda x: "Habilitado" if x == 1 else "Desabilitado",
                index=0 if (row.get("situacao_associado") or 1) == 1 else 1,
                key=f"dialog_admin_situacao_assoc_{row['id']}",
            )
            
            # Data de desligamento obrigatória se situação = DESABILITADO
            data_desligamento = None
            if situacao_associado == 2:
                data_desligamento = st.date_input(
                    "Data de Desligamento *",
                    value=data_desligamento_valor if data_desligamento_valor else date.today(),
                    format="DD/MM/YYYY",
                    key=f"dialog_admin_data_deslig_{row['id']}",
                    help="Obrigatório quando situação = Desabilitado",
                )
            
            motivo_desligamento = st.text_area(
                "Motivo de Desligamento",
                value=str(row.get("motivo_desligamento") or ""),
                key=f"dialog_admin_motivo_deslig_{row['id']}",
            )
            
            tipo_associado = st.selectbox(
                "Tipo de Associado",
                [1, 2, 3],
                format_func=lambda x: {1: "Honorários", 2: "Contribuintes", 3: "Comunitários"}[x],
                index=[1, 2, 3].index(row.get("tipo_associado") or 2),
                key=f"dialog_admin_tipo_assoc_{row['id']}",
            )
            
            ciclo_cobranca = st.selectbox(
                "Ciclo de Cobrança",
                [1, 2],
                format_func=lambda x: "Mensal" if x == 1 else "Anual",
                index=0 if (row.get("ciclo_cobranca") or 1) == 1 else 1,
                key=f"dialog_admin_ciclo_cobr_{row['id']}",
            )
            
            col1, col2 = st.columns(2)
            salvar_admin = col1.form_submit_button("Salvar", type="primary", use_container_width=True)
            cancelar_admin = col2.form_submit_button("Cancelar", use_container_width=True)
            
            if salvar_admin:
                try:
                    # Validação: data de desligamento obrigatória se desabilitado
                    if situacao_associado == 2 and not data_desligamento:
                        raise ValueError("Data de desligamento é obrigatória quando a situação é Desabilitado.")
                    
                    # Converter data_nascimento se necessário
                    data_nasc_valor = row.get("data_nascimento")
                    if data_nasc_valor is None or (isinstance(data_nasc_valor, float) and pd.isna(data_nasc_valor)):
                        data_nasc_final = date(2000, 1, 1)
                    elif isinstance(data_nasc_valor, str):
                        from datetime import datetime
                        try:
                            data_nasc_final = datetime.strptime(data_nasc_valor, "%Y-%m-%d").date()
                        except Exception:
                            try:
                                data_nasc_final = datetime.fromisoformat(data_nasc_valor.split("T")[0]).date()
                            except Exception:
                                data_nasc_final = date(2000, 1, 1)
                    elif hasattr(data_nasc_valor, "date"):
                        data_nasc_final = data_nasc_valor.date()
                    elif isinstance(data_nasc_valor, date):
                        data_nasc_final = data_nasc_valor
                    else:
                        data_nasc_final = date(2000, 1, 1)
                    
                    # Converter valores para tipos Python nativos
                    qtd_filhos = row.get("quantidade_filhos")
                    if qtd_filhos is None or (isinstance(qtd_filhos, float) and pd.isna(qtd_filhos)):
                        qtd_filhos = 0
                    else:
                        qtd_filhos = int(qtd_filhos)
                    
                    # Converter strings que podem ser NaN
                    def safe_str(val):
                        if val is None or (isinstance(val, float) and pd.isna(val)):
                            return ""
                        return str(val)
                    
                    atualizar_associado_completo(
                        associado_id=int(row["id"]),
                        login_id=int(row["login_id"]),
                        cpf=safe_str(row["cpf"]),
                        nome_completo=safe_str(row["nome_completo"]),
                        data_nascimento=data_nasc_final,
                        email=safe_str(row.get("email")),
                        telefone=safe_str(row.get("telefone")),
                        endereco=safe_str(row.get("endereco")),
                        cidade=safe_str(row.get("cidade")),
                        estado_uf=safe_str(row.get("estado_uf")),
                        situacao_trabalho=safe_str(row.get("situacao_trabalho")),
                        tipo_sanguineo=safe_str(row.get("tipo_sanguineo")),
                        quantidade_filhos=qtd_filhos,
                        identidade=safe_str(row.get("identidade")) or "SURDO",
                        data_inicio=data_inicio,
                        data_desligamento=data_desligamento,
                        motivo_desligamento=motivo_desligamento,
                        situacao_associado=situacao_associado,
                        tipo_associado=tipo_associado,
                        ciclo_cobranca=ciclo_cobranca,
                    )
                    mensagem = f"Dados de {row['nome_completo']} atualizados com sucesso."
                    st.session_state["msg_sucesso"] = mensagem
                    st.session_state["dialog_sucesso_msg"] = mensagem
                    st.session_state["mostrar_dialog_sucesso_edicao"] = True
                    st.session_state.pop("last_selected_row_id", None)
                    st.session_state["associado_dialog_active"] = False
                    # Incrementar contador para forçar recriação da grid e limpar seleção
                    st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao atualizar dados administrativos: {e}")
            
            if cancelar_admin:
                st.session_state.pop("last_selected_row_id", None)
                st.session_state["associado_dialog_active"] = False
                st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
                st.rerun()


def area_admin(authenticator) -> None:
    """Área do administrador: listagem e edição completa de associados."""

    name = st.session_state.get("name") or "Administrador"
    username = st.session_state.get("username") or "admin"

    with st.sidebar:
        st.markdown(f"Admin: {name} ({username})")
        menu = st.radio(
            "Menu",
            ["Associados", "Mensalidades"],
            key="admin_menu",
        )
        authenticator.logout("Sair", "sidebar")

    st.header("Área do administrador")

    # Se sair de "Mensalidades", limpa eventuais flags de erro de pagamento
    # para não reabrir o diálogo de Pagamento inválido ao voltar depois.
    if menu != "Mensalidades":
        st.session_state.pop("mostrar_dialog_erro_pagamento", None)
        st.session_state.pop("erro_pagamento_msg", None)

    # Exibir diálogo de sucesso de edição, se configurado
    if st.session_state.get("mostrar_dialog_sucesso_edicao") and st.session_state.get("dialog_sucesso_msg"):
        dialog_sucesso_edicao(st.session_state["dialog_sucesso_msg"])

    # Exibir diálogo de erro de pagamento, se configurado
    # Somente quando o menu atual for "Mensalidades", para não aparecer ao entrar em "Associados"
    if (
        menu == "Mensalidades"
        and st.session_state.get("mostrar_dialog_erro_pagamento")
        and st.session_state.get("erro_pagamento_msg")
    ):
        dialog_erro_pagamento(st.session_state["erro_pagamento_msg"])

    # Exibir mensagem de sucesso em banner se houver
    # (não mostrar enquanto o diálogo de sucesso de edição estiver ativo)
    if "msg_sucesso" in st.session_state and not st.session_state.get("mostrar_dialog_sucesso_edicao"):
        st.success(st.session_state["msg_sucesso"])
        st.session_state.pop("msg_sucesso")

    if menu == "Mensalidades":
        st.subheader("Gestão de Mensalidades")
        
        aba_lancar, aba_listar = st.tabs(["Lançar Mensalidade", "Listar Mensalidades"])
        
        with aba_lancar:
            st.markdown("### Nova Mensalidade")
            
            try:
                associados_disponiveis = listar_associados_contribuintes_habilitados()
            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao carregar associados: {e}")
                return
            
            if not associados_disponiveis:
                st.warning("Nenhum associado CONTRIBUINTE e HABILITADO disponível para lançamento.")
            else:
                opcoes_assoc = {
                    f"{a['nome_completo']} - {a['cpf']}": a["id"] for a in associados_disponiveis
                }
                associado_sel = st.selectbox(
                    "Selecione o associado",
                    list(opcoes_assoc.keys()),
                    key="lancar_mens_associado",
                )
                associado_id = opcoes_assoc[associado_sel]
                
                valor = st.number_input(
                    "Valor da Mensalidade (R$)",
                    min_value=0.0,
                    step=10.0,
                    format="%.2f",
                    key="lancar_mens_valor",
                )
                
                data_vencimento = st.date_input(
                    "Data de Vencimento",
                    format="DD/MM/YYYY",
                    key="lancar_mens_venc",
                )

                # Exibe o status inicial da mensalidade (somente leitura)
                status_mens_inicial = 1  # Não Pago
                status_mens_labels = {
                    1: "Não Pago",
                    2: "Ainda Falta Pagar!",
                    3: "Pago",
                }
                st.selectbox(
                    "Status da Mensalidade",
                    [1, 2, 3],
                    format_func=lambda x: status_mens_labels.get(x, str(x)),
                    index=0,
                    disabled=True,
                    key="lancar_mens_status",
                    help="Novas mensalidades começam como 'Não Pago'.",
                )
                
                if st.button("Lançar Mensalidade", type="primary"):
                    try:
                        if valor <= 0:
                            raise ValueError("Valor deve ser maior que zero.")
                        
                        mensalidade_id = inserir_mensalidade(
                            associado_id=int(associado_id),
                            valor=float(valor),
                            data_vencimento=data_vencimento,
                            status_mensalidade_id=1,  # Não Pago
                        )
                        st.session_state["msg_sucesso"] = f"Mensalidade #{mensalidade_id} lançada com sucesso!"
                        st.rerun()
                    except ValueError as e:
                        msg = str(e)
                        # Mensalidade duplicada → diálogo específico
                        if "Já existe uma mensalidade para este associado neste mês." in msg:
                            dialog_mensalidade_duplicada(msg)
                        # Valor inválido → diálogo próprio
                        elif "Valor deve ser maior que zero." in msg:
                            dialog_valor_invalido(msg)
                        else:
                            st.error(msg)
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Erro ao lançar mensalidade: {e}")
        
        with aba_listar:
            st.markdown("### Mensalidades Lançadas")
            
            try:
                mensalidades = listar_mensalidades()
            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao carregar mensalidades: {e}")
                return
            
            if not mensalidades:
                st.info("Nenhuma mensalidade lançada.")
            else:
                df_mens = pd.DataFrame(mensalidades)

                # Normaliza colunas numéricas e de data para tipos simples (evita [object Object])
                from decimal import Decimal

                def _valor_to_float(v):
                    if v is None:
                        return 0.0
                    if isinstance(v, dict):
                        for chave in ("valor", "value", "amount", "numero", "quantia"):
                            if chave in v and v[chave] is not None:
                                try:
                                    return float(v[chave])
                                except (TypeError, ValueError):
                                    continue
                        # Se não encontrar campo conhecido, tenta converter o dict como string (não ideal, mas evita erro)
                        try:
                            return float(str(v))
                        except (TypeError, ValueError):
                            return 0.0
                    if isinstance(v, Decimal):
                        return float(v)
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return 0.0

                if "valor" in df_mens.columns:
                    df_mens["valor"] = df_mens["valor"].apply(_valor_to_float)

                def _date_to_str(v):
                    if v is None:
                        return ""
                    # Trata NaN/NaT
                    try:
                        if pd.isna(v):
                            return ""
                    except TypeError:
                        pass

                    # Se já for string, tenta converter para data e voltar em DD/MM/YYYY
                    if isinstance(v, str):
                        try:
                            dt = pd.to_datetime(v, errors="coerce")
                            if pd.isna(dt):
                                return v
                            return dt.strftime("%d/%m/%Y")
                        except Exception:
                            return v

                    # Objetos datetime/date com strftime
                    if hasattr(v, "strftime"):
                        try:
                            return v.strftime("%d/%m/%Y")
                        except Exception:
                            return str(v)

                    return str(v)

                for col in ["data_emissao", "data_vencimento"]:
                    if col in df_mens.columns:
                        df_mens[col] = df_mens[col].apply(_date_to_str)

                # Normaliza colunas de status para texto legível
                def _status_to_text(valor):
                    if valor is None:
                        return ""
                    if isinstance(valor, dict):
                        for chave in ("descricao", "descricao_status", "nome", "label", "status"):
                            if chave in valor and valor[chave] is not None:
                                return str(valor[chave])
                        return str(valor)
                    try:
                        if pd.isna(valor):
                            return ""
                    except TypeError:
                        pass
                    return str(valor)

                for col in ["status_mensalidade", "status_pagamento"]:
                    if col in df_mens.columns:
                        df_mens[col] = df_mens[col].apply(_status_to_text)

                # Coluna fictícia para o botão Editar
                df_mens["acao"] = "Editar"

                # Configuração da grid AgGrid para mensalidades
                gb_m = GridOptionsBuilder.from_dataframe(df_mens)

                gb_m.configure_column("id", header_name="ID", width=80)
                gb_m.configure_column("nome_completo", header_name="Associado", flex=1)
                gb_m.configure_column("data_vencimento", header_name="Vencimento", width=120)
                gb_m.configure_column("status_mensalidade", header_name="Status Mensalidade", width=160)
                gb_m.configure_column("status_pagamento", header_name="Status Pagamento", width=150)

                # Ocultar colunas que não devem aparecer na tabela
                for col in [
                    "valor",          # Valor não exibido na tabela
                    "data_emissao",   # Emissão não exibida na tabela
                    "associado_id",
                    "status_mensalidade_id",
                    "pagamento_id",
                    "data_pagamento",
                ]:
                    if col in df_mens.columns:
                        gb_m.configure_column(col, hide=True)

                # Botão Editar na grid
                button_mens_editar = JsCode("""
                    class BtnCellRenderer {
                        init(params) {
                            this.eGui = document.createElement('button');
                            this.eGui.innerHTML = 'Editar';
                            this.eGui.style.cssText = 'padding:3px 8px; border:none; background-color:#2c7be5; color:white; border-radius:4px; cursor:pointer;';
                            this.eGui.addEventListener('click', () => {
                                if (params.api && params.api.deselectAll) {
                                    params.api.deselectAll();
                                }
                                params.node.setSelected(true);
                            });
                        }
                        getGui() {
                            return this.eGui;
                        }
                    }
                """)

                gb_m.configure_column(
                    "acao",
                    header_name="Ação",
                    cellRenderer=button_mens_editar,
                    width=120,
                    suppressMenu=True,
                )

                # Seleção somente via botão Editar
                gb_m.configure_selection(
                    "single",
                    use_checkbox=False,
                    rowMultiSelectWithClick=False,
                    suppressRowClickSelection=True,
                )

                grid_options_m = gb_m.build()

                # Usar contador na key para forçar recriação da grid após salvar/cancelar no diálogo
                grid_mens_counter = st.session_state.get("grid_mens_counter", 0)

                grid_response_m = AgGrid(
                    df_mens,
                    gridOptions=grid_options_m,
                    update_mode=GridUpdateMode.SELECTION_CHANGED,
                    fit_columns_on_grid_load=True,
                    height=400,
                    allow_unsafe_jscode=True,
                    key=f"grid_mensalidades_{grid_mens_counter}",
                )

                selected_rows_m = grid_response_m["selected_rows"]

                # Abre diálogo de edição sempre que houver seleção (comportamento igual à grid de Associados)
                if selected_rows_m is not None and len(selected_rows_m) > 0:
                    row_m = selected_rows_m.iloc[0].to_dict()
                    dialog_editar_mensalidade(row_m)
        return
        return

    st.subheader("Associados")
    
    # Campo de busca
    busca_nome = st.text_input("🔍 Procurar por nome", placeholder="Digite o nome do associado...", key="busca_nome_associado")
    
    try:
        associados = listar_associados()
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro ao carregar associados: {e}")
        return

    if not associados:
        st.info("Nenhum associado cadastrado.")
        return

    # Converter para DataFrame
    df = pd.DataFrame(
        [
            {
                "id": a["id"],
                "login_id": a["login_id"],
                "cpf": a["cpf"],
                "nome_completo": a["nome_completo"],
                "data_nascimento": a.get("data_nascimento"),
                "email": a.get("email") or "",
                "telefone": a.get("telefone") or "",
                "endereco": a.get("endereco") or "",
                "cidade": a.get("cidade") or "",
                "estado_uf": a.get("estado_uf") or "",
                "situacao_trabalho": a.get("situacao_trabalho") or "",
                "tipo_sanguineo": a.get("tipo_sanguineo") or "",
                "quantidade_filhos": a.get("quantidade_filhos") or 0,
                "identidade": a.get("identidade") or "SURDO",
                "data_inicio": pd.to_datetime(a.get("data_inicio")) if a.get("data_inicio") is not None else pd.NaT,
                "data_desligamento": pd.to_datetime(a.get("data_desligamento")) if a.get("data_desligamento") is not None else pd.NaT,
                "motivo_desligamento": a.get("motivo_desligamento") or "",
                "situacao_associado": a.get("situacao_associado") or 1,
                "tipo_associado": a.get("tipo_associado") or 2,
                "ciclo_cobranca": a.get("ciclo_cobranca") or 1,
            }
            for a in associados
        ]
    )

    # Filtrar por nome se houver busca
    if busca_nome:
        df = df[df["nome_completo"].str.contains(busca_nome, case=False, na=False)]
        
    if df.empty:
        st.warning("Nenhum associado encontrado com esse nome.")
        return

    # Coluna fictícia para o botão
    df["acao"] = "Editar"

    # Configurando o AgGrid
    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_column("cpf", header_name="CPF", width=140)
    gb.configure_column("nome_completo", header_name="Nome", flex=1)

    # Ocultar colunas que não aparecem na tabela mas são necessárias para edição
    gb.configure_column("id", header_name="ID", width=80, hide=True)
    gb.configure_column("cidade", header_name="Cidade", width=150, hide=True)
    gb.configure_column("estado_uf", header_name="UF", width=70, hide=True)
    gb.configure_column("telefone", header_name="Telefone", width=140, hide=True)
    gb.configure_column("login_id", hide=True)
    gb.configure_column("data_nascimento", hide=True)
    gb.configure_column("email", hide=True)
    gb.configure_column("endereco", hide=True)
    gb.configure_column("situacao_trabalho", hide=True)
    gb.configure_column("tipo_sanguineo", hide=True)
    gb.configure_column("quantidade_filhos", hide=True)
    gb.configure_column("identidade", hide=True)
    gb.configure_column("data_inicio", hide=True)
    gb.configure_column("data_desligamento", hide=True)
    gb.configure_column("motivo_desligamento", hide=True)
    gb.configure_column("situacao_associado", hide=True)
    gb.configure_column("tipo_associado", hide=True)
    gb.configure_column("ciclo_cobranca", hide=True)

    # Coluna de botão Editar
    button_renderer = JsCode("""
        class BtnCellRenderer {
            init(params) {
                this.eGui = document.createElement('button');
                this.eGui.innerHTML = 'Editar';
                this.eGui.style.cssText = 'padding:3px 8px; border:none; background-color:#2c7be5; color:white; border-radius:4px; cursor:pointer;';
                this.eGui.addEventListener('click', () => {
                    // Garante que sempre haja um evento de mudança de seleção,
                    // mesmo quando a mesma linha já está selecionada.
                    if (params.api && params.api.deselectAll) {
                        params.api.deselectAll();
                    }
                    params.node.setSelected(true);
                });
            }
            getGui() {
                return this.eGui;
            }
        }
    """)

    gb.configure_column(
        "acao",
        header_name="Ação",
        cellRenderer=button_renderer,
        width=120,
        suppressMenu=True,
    )

    # Seleção de linha desabilitada por padrão - só via botão
    gb.configure_selection("single", use_checkbox=False, rowMultiSelectWithClick=False, suppressRowClickSelection=True)
    grid_options = gb.build()

    # Usar contador na key para forçar recriação da grid após salvar
    grid_counter = st.session_state.get("grid_counter", 0)
    
    grid_response = AgGrid(
        df,
        gridOptions=grid_options,
        update_mode=GridUpdateMode.SELECTION_CHANGED,
        fit_columns_on_grid_load=True,
        height=400,
        allow_unsafe_jscode=True,
        key=f"grid_associados_{grid_counter}",
    )

    selected_rows = grid_response["selected_rows"]

    # Sempre que houver uma linha selecionada (via botão Editar), abre o diálogo
    # para aquela linha. O botão Editar foi ajustado para forçar um evento de
    # mudança de seleção mesmo quando a mesma linha já estava selecionada.
    if selected_rows is not None and len(selected_rows) > 0:
        row = selected_rows.iloc[0].to_dict()
        dialog_editar_associado(row)
    else:
        # Limpa a seleção anterior quando não há nenhuma linha selecionada
        if "last_selected_row_id" in st.session_state:
            st.session_state.pop("last_selected_row_id")


def main():
    st.set_page_config(page_title="Login", page_icon="🔐", layout="centered")

    # Esconde o botão "X" dos diálogos (inclui dialog_sucesso_edicao)
    _esconder_botao_fechar_dialog()

    # Garante automaticamente que o banco e a tabela login existam
    # (cria o banco gestao_associado_novo, tabela login e usuário admin padrão se necessário)
    try:
        init_db()
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro ao inicializar o banco de dados: {e}")
        return

    # Prepara autenticador com credenciais do banco
    credentials = carregar_credenciais()
    authenticator = stauth.Authenticate(
        credentials,
        "gestao_associado_cookie",
        "chave_assinatura_mude_isto",
        cookie_expiry_days=30,
    )

    # Se já estiver autenticado (por sessão/cookie), mostra apenas a página de boas-vindas
    name = st.session_state.get("name")
    authentication_status = st.session_state.get("authentication_status")
    username = st.session_state.get("username")

    # Se já estiver autenticado (cookie/sessão), vai direto para a área adequada
    if authentication_status:
        if (username or "").lower() == "admin":
            area_admin(authenticator)
        else:
            area_associado(authenticator, username or "")
        return

    # Se não estiver autenticado, mostra título e as abas Login / Novo usuário
    st.title("Gestão de Associados")
    aba_login, aba_novo = st.tabs(["Login", "Cadastrar novo associado"])

    # --- ABA LOGIN ---
    with aba_login:
        # Renderiza o formulário de login.
        # Para location='main', a função não retorna tupla; ela apenas
        # atualiza st.session_state['name'], ['authentication_status'] e ['username'].
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
            # Redireciona imediatamente para a área correta após login
            if (username or "").lower() == "admin":
                area_admin(authenticator)
            else:
                area_associado(authenticator, username or "")
        elif authentication_status is False:
            st.error("Usuário ou senha inválidos")

    # --- ABA NOVO USUÁRIO / CADASTRO ---
    with aba_novo:
        st.markdown("### Cadastrar novo associado")


        novo_nome = st.text_input("Nome completo", key="cad_nome")
        cpf_input = st.text_input("CPF", help="Digite apenas números", key="cad_cpf")

        # Usuário (login) é sempre o CPF e não pode ser alterado
        novo_username = st.text_input(
            "Usuário (login)", value=cpf_input, disabled=True
        )
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
            [
                "",
                "A+",
                "A-",
                "B+",
                "B-",
                "AB+",
                "AB-",
                "O+",
                "O-",
            ],
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
                    # Validação e formatação simples de CPF
                    cpf_digits = re.sub(r"\D", "", cpf_input or "")
                    if len(cpf_digits) != 11:
                        raise ValueError("CPF deve conter 11 dígitos.")
                    cpf_formatado = (
                        f"{cpf_digits[:3]}.{cpf_digits[3:6]}.{cpf_digits[6:9]}-"
                        f"{cpf_digits[9:]}"
                    )

                    # Garante que o username usado no login seja exatamente o CPF (somente dígitos)
                    novo_username = cpf_digits

                    # Encontra o código da identidade a partir do texto escolhido
                    identidade_codigo = None
                    for codigo, label in identidade_map.items():
                        if label == identidade_label_sel:
                            identidade_codigo = codigo
                            break
                    if identidade_codigo is None:
                        raise ValueError("Identidade inválida selecionada.")
                    foto_bytes = foto_file.getvalue() if foto_file is not None else None

                    # Gera hash da nova senha usando a mesma biblioteca
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
                    # Erros de regra de negócio
                    if str(e) == "Usuário já existe":
                        dialog_usuario_ja_existe()
                    else:
                        st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao cadastrar usuário: {e}")


if __name__ == "__main__":
    main()
