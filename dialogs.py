"""Todos os diálogos da aplicação."""

from datetime import date
import pandas as pd
import streamlit as st

from db import (
    atualizar_mensalidade,
    excluir_mensalidade,
    inserir_pagamento,
    atualizar_pagamento,
    atualizar_associado_completo,
    buscar_comprovante_pagamento,
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

        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


@st.dialog("✅ Sucesso!")
def dialog_sucesso_edicao(mensagem: str) -> None:
    """Diálogo genérico de sucesso para edição de associado."""
    st.markdown("<div id='dialog_sucesso_marker'></div>", unsafe_allow_html=True)
    st.success(mensagem)

    if st.button("OK"):
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
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


@st.dialog("⚠️ Aviso!")
def dialog_valor_invalido(mensagem: str) -> None:
    """Mostra aviso quando o valor informado é inválido (<= 0)."""
    st.warning(mensagem)

    if st.button("OK"):
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


@st.dialog("⚠️ Pagamento inválido")
def dialog_erro_pagamento(mensagem: str) -> None:
    """Mostra erro de pagamento em um modal separado."""
    st.markdown("<div id='dialog_pagamento_invalido_marker'></div>", unsafe_allow_html=True)
    st.error(mensagem)

    if st.button("OK"):
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

    st.markdown(
        f"Associado: {row.get('nome_completo', '')}"
    )
    
    # Verificar se está tudo pago (Status Mensalidade = 3 "Pago" E Status Pagamento = 1 "Pago")
    status_mensalidade_id = int(row.get("status_mensalidade_id") or 1)
    status_pagamento_id = row.get("status_pagamento_id")
    tudo_pago = (status_mensalidade_id == 3 and status_pagamento_id == 1)
    
    if tudo_pago:
        st.success("✅ Mensalidade e Pagamento já foram concluídos. Campos em modo somente leitura.")
    
    is_admin_user = (st.session_state.get("username", "").lower() == "admin")

    aba_dados, aba_pagamento = st.tabs(["Dados da Mensalidade", "Pagamento"])

    # ---------------- Aba Dados da Mensalidade -----------------
    with aba_dados:
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

        with st.form("form_editar_mensalidade"):
            raw_valor = row.get("valor")

            if isinstance(raw_valor, dict):
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
                disabled=True,
            )

            data_vencimento = st.date_input(
                "Data de Vencimento",
                value=data_venc_valor,
                format="DD/MM/YYYY",
                key=f"edit_mens_venc_{row['id']}",
                disabled=True,
            )

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
                disabled=True,
                key=f"edit_mens_status_{row['id']}",
                help="Status da mensalidade (somente leitura)." if tudo_pago else "Status é atualizado automaticamente conforme o pagamento.",
            )

            # Se tudo está pago, mostrar apenas botão "Fechar"
            if tudo_pago:
                cancelar = st.form_submit_button("Fechar", use_container_width=True)
                salvar = False
            elif is_admin_user:
                col1, col2 = st.columns(2)
                salvar = col1.form_submit_button("Salvar", type="primary", use_container_width=True)
                cancelar = col2.form_submit_button("Cancelar", use_container_width=True)
            else:
                cancelar = st.form_submit_button("Fechar", use_container_width=True)
                salvar = False

            if salvar:
                try:
                    if valor <= 0:
                        raise ValueError("Valor deve ser maior que zero.")

                    atualizar_mensalidade(
                        mensalidade_id=int(row["id"]),
                        valor=float(valor),
                        data_vencimento=data_vencimento,
                    )

                    st.session_state["msg_sucesso"] = f"Mensalidade atualizada com sucesso."
                    st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                    st.session_state.pop("last_selected_mensalidade_id", None)
                    st.session_state.pop("last_selected_mensalidade_admin_id", None)
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
                except ValueError as e:
                    if "Valor deve ser maior que zero." in str(e):
                        dialog_valor_invalido(str(e))
                    else:
                        st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao atualizar mensalidade: {e}")
            
            if cancelar:
                st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                st.session_state.pop("last_selected_mensalidade_id", None)
                st.session_state.pop("last_selected_mensalidade_admin_id", None)
                if hasattr(st, "rerun"):
                    st.rerun()
                else:
                    st.experimental_rerun()

        if is_admin_user:
            st.markdown("---")
            st.warning("Cuidado: esta ação excluirá permanentemente a mensalidade selecionada.")

            col_exc1, col_exc2 = st.columns([1, 1])
            with col_exc1:
                if st.button(
                    "Excluir Mensalidade",
                    key=f"btn_excluir_mens_{row['id']}",
                    use_container_width=True,
                ):
                    try:
                        excluir_mensalidade(int(row["id"]))
                        st.session_state["msg_sucesso"] = "Mensalidade excluída com sucesso."
                        st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                        st.session_state.pop("last_selected_mensalidade_id", None)
                        st.session_state.pop("last_selected_mensalidade_admin_id", None)
                        if hasattr(st, "rerun"):
                            st.rerun()
                        else:
                            st.experimental_rerun()
                    except Exception as e:  # noqa: BLE001
                        st.error(f"Erro ao excluir mensalidade: {e}")


    # ---------------- Aba Pagamento -----------------
    with aba_pagamento:
        pagamento_id = row.get("pagamento_id")
        
        # Buscar comprovante existente
        comprovante_existente = None
        if pagamento_id:
            try:
                comprovante_existente = buscar_comprovante_pagamento(int(pagamento_id))
            except Exception:
                pass
        
        # Mostrar informação sobre comprovante existente
        if comprovante_existente:
            st.info("📎 Comprovante anexado")
            col_comp1, col_comp2 = st.columns([2, 3])
            with col_comp1:
                st.download_button(
                    label="⬇️ Baixar Comprovante",
                    data=comprovante_existente,
                    file_name=f"comprovante_pagamento_{pagamento_id}.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                )
            with col_comp2:
                st.caption("Você pode fazer upload de um novo comprovante para substituir o atual.")

        data_pag_valor = row.get("data_pagamento")
        if isinstance(data_pag_valor, str):
            try:
                data_pag_valor = datetime.strptime(data_pag_valor.split("T")[0], "%Y-%m-%d").date()
            except Exception:
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

        # Buscar status_pagamento_id diretamente do banco
        status_inicial_id = row.get("status_pagamento_id")
        if status_inicial_id is None or status_inicial_id == 2:
            status_inicial_id = 2  # Não Pago
        else:
            status_inicial_id = 1  # Pago
        
        # Definir regras de desabilitação baseado em status e tipo de usuário
        # Se tudo está pago (mensalidade E pagamento), desabilitar tudo
        if tudo_pago:
            desabilitar_valor_data = True
            desabilitar_status = True
        else:
            esta_pago = (status_inicial_id == 1)
            # Se está pago, desabilitar valor e data para todos
            # Status só é desabilitado para não-admin quando está pago
            desabilitar_valor_data = esta_pago
            desabilitar_status = esta_pago and not is_admin_user

        with st.form(f"form_pag_mensalidade_{row['id']}"):
            raw_valor_mens = row.get("valor")
            try:
                valor_mensalidade_base = float(raw_valor_mens) if raw_valor_mens is not None else 0.0
            except (TypeError, ValueError):
                valor_mensalidade_base = 0.0

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
                disabled=desabilitar_valor_data,
            )

            data_pagamento = st.date_input(
                "Data do Pagamento",
                value=data_pag_valor,
                format="DD/MM/YYYY",
                key=f"edit_pag_data_{row['id']}",
                disabled=desabilitar_valor_data,
            )

            status_pagamento_id = st.selectbox(
                "Status do Pagamento",
                [1, 2],
                format_func=lambda x: "Pago" if x == 1 else "Não Pago",
                index=0 if status_inicial_id == 1 else 1,
                key=f"edit_pag_status_{row['id']}",
                disabled=desabilitar_status,
            )

            comprovante_file = st.file_uploader(
                "Anexar novo comprovante (opcional)" if comprovante_existente else "Anexar comprovante (opcional)",
                key=f"edit_pag_comp_{row['id']}",
                help="Envie um novo arquivo para substituir o comprovante atual" if comprovante_existente else None,
                disabled=tudo_pago,
            )

            # Se tudo está pago, mostrar apenas botão "Fechar"
            if tudo_pago:
                cancelar_pag = st.form_submit_button("Fechar", use_container_width=True)
                salvar_pag = False
            else:
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

                    if round(float(valor_pagamento), 2) != round(float(valor_mensalidade_base), 2):
                        st.session_state["erro_pagamento_msg"] = (
                            f"Valor do pagamento deve ser igual ao valor da mensalidade (R$ {valor_mensalidade_base:.2f})."
                        )
                        st.session_state["mostrar_dialog_erro_pagamento"] = True
                        st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                        st.session_state.pop("last_selected_mensalidade_id", None)
                        st.session_state.pop("last_selected_mensalidade_admin_id", None)
                        if hasattr(st, "rerun"):
                            st.rerun()
                        else:
                            st.experimental_rerun()
                        return

                    # Processar comprovante: usar novo upload ou manter existente
                    if comprovante_file is not None:
                        comprovante_bytes = comprovante_file.getvalue()
                    else:
                        # Se não há upload novo, manter o existente (se houver)
                        comprovante_bytes = comprovante_existente

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

                    st.session_state["msg_sucesso"] = f"Pagamento da mensalidade salvo com sucesso."
                    st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                    st.session_state.pop("last_selected_mensalidade_id", None)
                    st.session_state.pop("last_selected_mensalidade_admin_id", None)
                    if hasattr(st, "rerun"):
                        st.rerun()
                    else:
                        st.experimental_rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao salvar pagamento: {e}")
            if cancelar_pag:
                st.session_state["grid_mens_counter"] = st.session_state.get("grid_mens_counter", 0) + 1
                st.session_state.pop("last_selected_mensalidade_id", None)
                st.session_state.pop("last_selected_mensalidade_admin_id", None)
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
            st.session_state["msg_sucesso"] = "Mensalidade excluída com sucesso."
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


@st.dialog("Editar Associado")
def dialog_editar_associado(row) -> None:
    """Diálogo de edição de associado com abas para dados pessoais e administrativos."""
    st.markdown("<div id='dialog_editar_associado_marker'></div>", unsafe_allow_html=True)
    st.session_state["associado_dialog_active"] = True

    identidade_map = {
        "SURDO": "Surdo",
        "SURDOCEGO": "Surdocego",
        "DEFICIENCIA_AUDITIVA": "Deficiência Auditiva (DA)",
        "OUVINTE": "Ouvinte",
    }

    aba_pessoal, aba_admin = st.tabs(["Dados Pessoais", "Dados Administrativos"])
    
    with aba_pessoal:
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
                ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
                index=max(
                    0,
                    ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].index(
                        str(row.get("tipo_sanguineo") or "").strip() 
                        if not (isinstance(row.get("tipo_sanguineo"), float) and pd.isna(row.get("tipo_sanguineo"))) 
                        else ""
                    ),
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
                value=int(row.get("quantidade_filhos") or 0) 
                    if not (isinstance(row.get("quantidade_filhos"), float) and pd.isna(row.get("quantidade_filhos"))) 
                    else 0,
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
                    st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
                    st.session_state.pop("last_selected_associado_id", None)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao atualizar dados pessoais: {e}")

            if cancelar_pessoal:
                st.session_state.pop("last_selected_row_id", None)
                st.session_state["associado_dialog_active"] = False
                st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
                st.session_state.pop("last_selected_associado_id", None)
                st.rerun()
    
    with aba_admin:
        data_inicio_valor = row.get("data_inicio")
        
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
                    if situacao_associado == 2 and not data_desligamento:
                        raise ValueError("Data de desligamento é obrigatória quando a situação é Desabilitado.")
                    
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
                    
                    qtd_filhos = row.get("quantidade_filhos")
                    if qtd_filhos is None or (isinstance(qtd_filhos, float) and pd.isna(qtd_filhos)):
                        qtd_filhos = 0
                    else:
                        qtd_filhos = int(qtd_filhos)
                    
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
                    st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
                    st.session_state.pop("last_selected_associado_id", None)
                    st.rerun()
                except ValueError as e:
                    st.error(str(e))
                except Exception as e:  # noqa: BLE001
                    st.error(f"Erro ao atualizar dados administrativos: {e}")
            
            if cancelar_admin:
                st.session_state.pop("last_selected_row_id", None)
                st.session_state["associado_dialog_active"] = False
                st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
                st.session_state.pop("last_selected_associado_id", None)
                st.rerun()


"""
    Diálogos relacionados a senha e autenticação
"""
@st.dialog("✅ Senha redefinida!")
def dialog_senha_redefinida() -> None:
    st.success("✅ Senha redefinida com sucesso! Faça login com sua nova senha.")

    if st.button("Fechar"):
        st.session_state["rec_cpf"] = ""
        st.session_state.pop("rec_nova_senha", None)
        st.session_state.pop("rec_conf_senha", None)
        st.session_state.pop("senha_redefinida_sucesso", None)
        # Mudar para a aba Login (índice 0)
        st.session_state["aba_autenticacao"] = 0
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()


@st.dialog("🔓 Solicitação aprovada!")
def dialog_solicitacao_aprovada() -> None:
    st.info("Solicitação aprovada! Redefina sua senha abaixo.")

@st.dialog("🔒 Solicitação enviada!")
def dialog_solicitacao_troca_senha() -> None:
    # Marcador usado pelo CSS para esconder o botão X apenas neste diálogo
    st.markdown("<div id='dialog_solicitacao_troca_senha_marker'></div>", unsafe_allow_html=True)
    st.success("Solicitação registrada! Aguarde a aprovação do administrador para redefinir sua senha.")

    if st.button("Fechar"):
        st.session_state["rec_cpf"] = ""
        st.session_state.pop("rec_nova_senha", None)
        st.session_state.pop("rec_conf_senha", None)
        st.session_state.pop("senha_redefinida_sucesso", None)
        # Mudar para a aba Login (índice 0)
        st.session_state["aba_autenticacao"] = 0
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()

