"""Área do associado - visualização e edição de dados pessoais."""

import re
from datetime import date
from decimal import Decimal
import pandas as pd
import streamlit as st
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from db import (
    obter_login_id,
    obter_associado_por_login_id,
    listar_mensalidades,
    atualizar_associado_completo,
)
from dialogs import dialog_editar_mensalidade


def area_associado(authenticator, username: str) -> None:
    """Área do associado: visualização/edição de dados pessoais."""

    name = st.session_state.get("name") or username

    with st.sidebar:
        st.header("Área do associado")
        st.markdown(f"Usuário: {name}")
        menu = st.radio(
            "Menu",
            ["Dados pessoais", "Mensalidades"],
            key="assoc_menu",
        )
        authenticator.logout("Sair", "sidebar")

    if "msg_sucesso" in st.session_state:
        st.success(st.session_state["msg_sucesso"])
        st.session_state.pop("msg_sucesso")

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

            # Normalizar dados (mesma lógica da área admin)
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
                try:
                    if pd.isna(v):
                        return ""
                except TypeError:
                    pass

                if isinstance(v, str):
                    try:
                        dt = pd.to_datetime(v, errors="coerce")
                        if pd.isna(dt):
                            return v
                        return dt.strftime("%d/%m/%Y")
                    except Exception:
                        return v

                if hasattr(v, "strftime"):
                    try:
                        return v.strftime("%d/%m/%Y")
                    except Exception:
                        return str(v)

                return str(v)

            for col in ["data_emissao", "data_vencimento"]:
                if col in df_mens.columns:
                    df_mens[col] = df_mens[col].apply(_date_to_str)

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

            df_mens["acao"] = "Editar"

            # Configuração da grid AgGrid
            gb_m = GridOptionsBuilder.from_dataframe(df_mens)
            gb_m.configure_column("id", header_name="ID", width=80)
            gb_m.configure_column("data_vencimento", header_name="Vencimento", width=120, sort="asc")
            gb_m.configure_column("status_mensalidade", header_name="Status Mensalidade", width=160)
            gb_m.configure_column("status_pagamento", header_name="Status Pagamento", width=150)

            # Ocultar colunas não necessárias (não mostra nome do associado pois é ele mesmo)
            for col in ["id", "valor", "data_emissao", "nome_completo", "associado_id", "status_mensalidade_id", "pagamento_id", "data_pagamento", "status_pagamento_id"]:
                if col in df_mens.columns:
                    gb_m.configure_column(col, hide=True)

            # Botão Editar
            button_mens_editar = JsCode("""
                class BtnCellRenderer {
                    init(params) {
                        this.eGui = document.createElement('button');
                        this.eGui.innerHTML = 'Editar';
                        this.eGui.style.cssText = 'padding:3px 8px; border:none; background-color:#2c7be5; color:white; border-radius:4px; cursor:pointer;';
                        this.eGui.addEventListener('click', (event) => {
                            event.stopPropagation();
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

            gb_m.configure_selection(
                "single",
                use_checkbox=False,
                rowMultiSelectWithClick=False,
                suppressRowClickSelection=True,
            )

            grid_options_m = gb_m.build()
            grid_mens_counter = st.session_state.get("grid_mens_counter", 0)

            grid_response_m = AgGrid(
                df_mens,
                gridOptions=grid_options_m,
                update_mode=GridUpdateMode.SELECTION_CHANGED,
                fit_columns_on_grid_load=True,
                height=400,
                allow_unsafe_jscode=True,
                key=f"grid_mensalidades_assoc_{grid_mens_counter}",
            )

            selected_rows_m = grid_response_m["selected_rows"]

            # Só abre o diálogo se houver uma NOVA seleção (ignora cliques em células de linhas já selecionadas)
            if selected_rows_m is not None and len(selected_rows_m) > 0:
                row_m_id = selected_rows_m.iloc[0].get("id")
                last_selected_id = st.session_state.get("last_selected_mensalidade_id")
                
                # Só abre diálogo se for uma nova seleção diferente
                if row_m_id != last_selected_id:
                    st.session_state["last_selected_mensalidade_id"] = row_m_id
                    row_m = selected_rows_m.iloc[0].to_dict()
                    dialog_editar_mensalidade(row_m)
            else:
                # Limpa o ID quando não há seleção
                st.session_state.pop("last_selected_mensalidade_id", None)
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
            ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
            index=max(
                0,
                ["", "A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].index(
                    associado.get("tipo_sanguineo") or ""
                ),
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
