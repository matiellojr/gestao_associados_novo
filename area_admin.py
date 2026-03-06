"""Área do administrador - gestão de associados e mensalidades."""

from datetime import date
from decimal import Decimal
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, JsCode

from db import (
    listar_associados,
    listar_associados_contribuintes_habilitados,
    inserir_mensalidade,
    inserir_pagamento_inicial,
    listar_mensalidades,
)
from dialogs import (
    dialog_erro_pagamento,
    dialog_mensalidade_duplicada,
    dialog_valor_invalido,
    dialog_editar_mensalidade,
    dialog_editar_associado,
)
from helpers import fechar_sidebar_ao_clicar_menu, solicitar_fechamento_sidebar


def area_admin(authenticator) -> None:
    """Área do administrador: listagem e edição completa de associados."""

    name = st.session_state.get("name") or "Administrador"
    username = st.session_state.get("username") or "admin"

    # Nao fecha dialogo ao clicar fora; apenas botao Cancelar

    with st.sidebar:
        st.header("Área do administrador")
        st.markdown(f"Admin: {name} ({username})")
        # menu dinâmico: adiciona Developer apenas para admin/developer
        menu_items = ["Associados", "Mensalidades"]
        if (username or "").lower() in ("admin", "developer"):
            menu_items.append("Developer")
        menu = st.radio(
            "Menu",
            menu_items,
            key="admin_menu",
            on_change=solicitar_fechamento_sidebar,
        )
        authenticator.logout("Sair", "sidebar")

    fechar_sidebar_ao_clicar_menu()

    # Se sair de "Mensalidades", limpa eventuais flags de erro de pagamento
    if menu != "Mensalidades":
        st.session_state.pop("mostrar_dialog_erro_pagamento", None)
        st.session_state.pop("erro_pagamento_msg", None)

    # Exibir diálogo de erro de pagamento, se configurado
    if (
        menu == "Mensalidades"
        and st.session_state.get("mostrar_dialog_erro_pagamento")
        and st.session_state.get("erro_pagamento_msg")
    ):
        dialog_erro_pagamento(st.session_state["erro_pagamento_msg"])

    # Exibir mensagem de sucesso em banner se houver
    if "msg_sucesso" in st.session_state:
        st.success(st.session_state["msg_sucesso"])
        st.session_state.pop("msg_sucesso")
        st.session_state.pop("dialog_sucesso_msg", None)
        st.session_state.pop("mostrar_dialog_sucesso_edicao", None)

    if menu == "Mensalidades":
        _render_mensalidades_section()
        return

    if menu == "Developer":
        _render_developer_section()
        return

    _render_associados_section()


def _get_query_param(name: str):
    """Lê query param com compatibilidade entre versões do Streamlit."""
    try:
        value = st.query_params.get(name)
        if isinstance(value, list):
            return value[0] if value else None
        return value
    except Exception:
        try:
            value = st.experimental_get_query_params().get(name)
            if isinstance(value, list):
                return value[0] if value else None
            return value
        except Exception:
            return None


def _is_mobile_view() -> bool:
    """Detecta largura de tela para alternar layout no admin."""
    mobile_param = _get_query_param("mobile")
    if str(mobile_param).lower() in ("1", "true"):
        return True
    if str(mobile_param).lower() in ("0", "false"):
        return False

    # Define o modo com base no viewport e recarrega com query param
    components.html(
        """
        <script>
        (function() {
            const isMobile = window.innerWidth <= 768;
            const url = new URL(window.location.href);
            if (!url.searchParams.get('mobile')) {
                url.searchParams.set('mobile', isMobile ? '1' : '0');
                window.location.replace(url.toString());
            }
        })();
        </script>
        """,
        height=0,
        width=0,
    )
    # Fallback: assume desktop until query param is set by JS
    return False


def _render_mensalidades_section():
    """Renderiza a seção de gestão de mensalidades."""
    st.subheader("Gestão de Mensalidades")
    
    aba_lancar, aba_listar = st.tabs(["Lançar Mensalidade", "Listar Mensalidades"])
    
    with aba_lancar:
        _render_lancar_mensalidade()
    
    with aba_listar:
        _render_listar_mensalidades()


def _render_lancar_mensalidade():
    """Renderiza o formulário de lançamento de mensalidade."""
    st.markdown("### Nova Mensalidade")
    
    # Contador para resetar o formulário
    form_counter = st.session_state.get("lancar_mens_form_counter", 0)
    
    try:
        associados_disponiveis = listar_associados_contribuintes_habilitados()
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro ao carregar associados: {e}")
        return
    
    if not associados_disponiveis:
        st.warning("Nenhum associado CONTRIBUINTE e HABILITADO disponível para lançamento.")
    else:
        if _is_mobile_view():
            busca_nome = st.text_input(
                "🔍 Procurar por nome",
                placeholder="Digite o nome do associado...",
                key="busca_nome_assoc_mensalidade_mobile",
            )
        else:
            busca_nome = None

        if busca_nome:
            associados_disponiveis = [
                a for a in associados_disponiveis
                if busca_nome.strip().lower() in str(a.get("nome_completo", "")).lower()
            ]
            if not associados_disponiveis:
                st.warning("Nenhum associado encontrado com esse nome.")
                return

        opcoes_assoc = {
            f"{a['nome_completo']}": a["id"] for a in associados_disponiveis
        }
        opcoes_lista = [""] + list(opcoes_assoc.keys())
        associado_sel = st.selectbox(
            "Selecione o associado",
            opcoes_lista,
            key=f"lancar_mens_associado_{form_counter}",
        )
        
        if not associado_sel:
            st.info("Selecione um associado para continuar.")
            return
            
        associado_id = opcoes_assoc[associado_sel]
        
        valor = st.number_input(
            "Valor da Mensalidade (R$)",
            min_value=0.0,
            value=0.0,
            step=10.0,
            format="%.2f",
            key=f"lancar_mens_valor_{form_counter}",
        )
        
        data_vencimento = st.date_input(
            "Data de Vencimento",
            value=date.today(),
            format="DD/MM/YYYY",
            key=f"lancar_mens_venc_{form_counter}",
        )

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
            key=f"lancar_mens_status_{form_counter}",
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
                    status_mensalidade_id=1,
                )
                
                # Cria pagamento inicial com status "Não Pago"
                inserir_pagamento_inicial(
                    mensalidade_id=mensalidade_id,
                    valor_pagamento=float(valor),
                )
                
                # Extrair nome do associado (antes do " - CPF")
                nome_associado = associado_sel.split(" - ")[0] if " - " in associado_sel else associado_sel
                mes_ano = data_vencimento.strftime("%m/%Y")
                
                st.session_state["msg_sucesso"] = f"Mensalidade lançada para {nome_associado} do mês/ano {mes_ano}!"
                
                # Incrementar contador para resetar o formulário
                st.session_state["lancar_mens_form_counter"] = form_counter + 1
                
                st.rerun()
            except ValueError as e:
                msg = str(e)
                if "Já existe uma mensalidade para este associado neste mês" in msg:
                    dialog_mensalidade_duplicada("Já existe uma mensalidade para este associado neste mês.")
                elif "Valor deve ser maior que zero." in msg:
                    dialog_valor_invalido(msg)
                else:
                    st.error(msg)
            except Exception as e:  # noqa: BLE001
                st.error(f"Erro ao lançar mensalidade: {e}")


def _render_listar_mensalidades():
    """Renderiza a grid de mensalidades lançadas."""
    st.markdown("### Mensalidades Lançadas")
    
    # Campo de busca
    busca = st.text_input(
        "🔍 Buscar por nome ou mês/ano (ex: 01/2026)",
        placeholder="Digite o nome do associado ou mês/ano do vencimento...",
        key="busca_mensalidades"
    )
    
    try:
        mensalidades = listar_mensalidades()
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro ao carregar mensalidades: {e}")
        return
    
    if not mensalidades:
        st.info("Nenhuma mensalidade lançada.")
        return
    
    df_mens = pd.DataFrame(mensalidades)
    mensalidade_by_id = {m.get("id"): m for m in mensalidades if m.get("id") is not None}

    # Normalizar dados
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

    busca_lower = (busca or "").strip().lower()

    def _match_filter(row):
        if not busca_lower:
            return True

        # Buscar no nome
        nome = str(row.get("nome_completo", "")).lower()
        if busca_lower in nome:
            return True

        # Buscar no mes/ano do vencimento (formato MM/AAAA ou M/AAAA)
        data_venc_str = str(row.get("data_vencimento", ""))
        if data_venc_str:
            parts = data_venc_str.split("/")
            if len(parts) == 3:
                mes_ano = f"{parts[1]}/{parts[2]}"
                if busca_lower in mes_ano.lower():
                    return True
            if busca_lower in data_venc_str.lower():
                return True

        return False

    # Aplicar filtro de busca (antes do modo mobile)
    if busca_lower:
        df_mens = df_mens[df_mens.apply(_match_filter, axis=1)]

        if df_mens.empty:
            st.info(f"Nenhuma mensalidade encontrada para: {busca}")
            return

    if _is_mobile_view():
        # Lista simples para celular (evita WebSocket pesado do AgGrid)
        cols_visiveis = [
            col
            for col in ["nome_completo", "data_vencimento", "status_mensalidade"]
            if col in df_mens.columns
        ]
        if cols_visiveis:
            df_mobile = df_mens[cols_visiveis].rename(
                columns={
                    "nome_completo": "Associado",
                    "data_vencimento": "Vencimento",
                    "status_mensalidade": "Status da Mensalidade",
                }
            )
            st.dataframe(df_mobile, use_container_width=True, hide_index=True)

        rows = df_mens.to_dict("records")
        if busca_lower:
            rows = [r for r in rows if _match_filter(r)]
            if not rows:
                st.info(f"Nenhuma mensalidade encontrada para: {busca}")
                return
        row_by_id = {r.get("id"): r for r in rows if r.get("id") is not None}
        if row_by_id:
            ordered_ids = sorted(
                row_by_id.keys(),
                key=lambda _id: str(row_by_id.get(_id, {}).get("nome_completo", "")).lower(),
            )
            def _label_mid(_id):
                r = row_by_id.get(_id, {})
                nome = r.get("nome_completo", "")
                venc = r.get("data_vencimento", "")
                status = r.get("status_mensalidade", "")
                return f"{nome} - {venc} - {status}".strip(" -")

            selected_id = st.selectbox(
                "Selecionar mensalidade para editar",
                ordered_ids,
                format_func=_label_mid,
                key="admin_mensalidade_select",
            )
            if st.button("Editar mensalidade", type="primary"):
                row_raw = mensalidade_by_id.get(selected_id, row_by_id[selected_id])
                dialog_editar_mensalidade(row_raw)
        return

    gb_m = GridOptionsBuilder.from_dataframe(df_mens)
    gb_m.configure_column("nome_completo", header_name="Associado", flex=1)
    gb_m.configure_column("data_vencimento", header_name="Vencimento", width=120, sort="asc")
    gb_m.configure_column("status_mensalidade", header_name="Status Mensalidade", width=160)
    gb_m.configure_column("status_pagamento", header_name="Status Pagamento", width=150)

    for col in ["id", "valor", "data_emissao", "associado_id", "status_mensalidade_id", "pagamento_id", "data_pagamento", "status_pagamento_id"]:
        if col in df_mens.columns:
            gb_m.configure_column(col, hide=True)

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
        key=f"grid_mensalidades_{grid_mens_counter}",
    )

    selected_rows_m = grid_response_m["selected_rows"]

    # Só abre o diálogo se houver uma NOVA seleção
    if selected_rows_m is not None and len(selected_rows_m) > 0:
        row_m_id = selected_rows_m.iloc[0].get("id")
        last_selected_id = st.session_state.get("last_selected_mensalidade_admin_id")

        if row_m_id != last_selected_id:
            st.session_state["last_selected_mensalidade_admin_id"] = row_m_id
            row_m = selected_rows_m.iloc[0].to_dict()
            row_raw = mensalidade_by_id.get(row_m_id, row_m)
            dialog_editar_mensalidade(row_raw)
    else:
        st.session_state.pop("last_selected_mensalidade_admin_id", None)


def _render_associados_section():
    """Renderiza a seção de gestão de associados."""
    st.subheader("Associados")

    # Controla quando o dialog foi solicitado nesta execução
    st.session_state["associado_dialog_requested"] = False

    busca_nome = st.text_input(
        "🔍 Procurar por nome",
        placeholder="Digite o nome do associado...",
        key="busca_nome_associado"
    )

    try:
        associados = listar_associados()
    except Exception as e:  # noqa: BLE001
        st.error(f"Erro ao carregar associados: {e}")
        return

    if not associados:
        st.info("Nenhum associado cadastrado.")
        return

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

    if busca_nome:
        df = df[df["nome_completo"].str.contains(busca_nome, case=False, na=False)]
        
    if df.empty:
        st.warning("Nenhum associado encontrado com esse nome.")
        return

    df["acao"] = "Editar"

    if _is_mobile_view():
        # Somente seletor no celular (sem grid)
        filtered_ids = set(df["id"].tolist()) if "id" in df.columns else set()
        assoc_by_id = {
            a.get("id"): a
            for a in associados
            if a.get("id") is not None and (not filtered_ids or a.get("id") in filtered_ids)
        }
        if assoc_by_id:
            def _label_assoc(_id):
                a = assoc_by_id.get(_id, {})
                nome = a.get("nome_completo", "")
                cpf = a.get("cpf", "")
                return f"{nome} - {cpf}".strip(" -")

            selected_id = st.selectbox(
                "Selecionar associado para editar",
                [None] + list(assoc_by_id.keys()),
                format_func=_label_assoc,
                key="admin_assoc_select",
            )
            if st.button("Editar associado", type="primary"):
                if selected_id is None:
                    st.info("Selecione um associado para editar.")
                else:
                    st.session_state["associado_dialog_requested"] = True
                    dialog_editar_associado(assoc_by_id[selected_id])
        return

    # Se o diálogo foi fechado, força re-render da grid para liberar a seleção
    if not st.session_state.get("associado_dialog_active") and st.session_state.get("last_selected_associado_id") is not None:
        st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
        st.session_state.pop("last_selected_associado_id", None)

    gb = GridOptionsBuilder.from_dataframe(df)
    gb.configure_column("cpf", header_name="CPF", width=140)
    gb.configure_column("nome_completo", header_name="Nome", flex=1)

    # Ocultar colunas
    for col in [
        "id", "cidade", "estado_uf", "telefone", "login_id", "data_nascimento",
        "email", "endereco", "situacao_trabalho", "tipo_sanguineo",
        "quantidade_filhos", "identidade", "data_inicio", "data_desligamento",
        "motivo_desligamento", "situacao_associado", "tipo_associado", "ciclo_cobranca",
    ]:
        gb.configure_column(col, hide=True)

    button_renderer = JsCode("""
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
                    // Forca disparo de selecao mesmo se a linha ja estava selecionada
                    try {
                        params.node.setSelected(false);
                    } catch (e) {}
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

    gb.configure_selection("single", use_checkbox=False, rowMultiSelectWithClick=False, suppressRowClickSelection=True)
    grid_options = gb.build()

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

    # Se o diálogo não está ativo, libera a seleção para reabrir a mesma linha
    if not st.session_state.get("associado_dialog_active"):
        st.session_state.pop("last_selected_associado_id", None)

    # Só abre o diálogo se houver uma NOVA seleção (ignora cliques em células de linhas já selecionadas)
    if selected_rows is not None and len(selected_rows) > 0:
        row_id = selected_rows.iloc[0].get("id")
        last_selected_id = st.session_state.get("last_selected_associado_id")

        # Só abre diálogo se for uma nova seleção diferente
        dialog_active = st.session_state.get("associado_dialog_active")
        if row_id != last_selected_id or not dialog_active:
            st.session_state["last_selected_associado_id"] = row_id
            # Recupera o registro original da lista 'associados' para preservar 'foto' (bytes)
            original = None
            try:
                for a in associados:
                    if int(a.get("id")) == int(row_id):
                        original = a
                        break
            except Exception:
                original = None

            if original is not None:
                st.session_state["associado_dialog_requested"] = True
                dialog_editar_associado(original)
            else:
                # Fallback: usa os dados da grid se não encontrar o original
                row = selected_rows.iloc[0].to_dict()
                st.session_state["associado_dialog_requested"] = True
                dialog_editar_associado(row)
    else:
        # Limpa o ID quando não há seleção
        st.session_state.pop("last_selected_associado_id", None)

    # Se o dialog foi fechado sem passar pelo Cancelar, limpa estado e força re-render
    if st.session_state.get("associado_dialog_active") and not st.session_state.get("associado_dialog_requested"):
        st.session_state["associado_dialog_active"] = False
        st.session_state["grid_counter"] = st.session_state.get("grid_counter", 0) + 1
        st.session_state.pop("last_selected_associado_id", None)


def _render_developer_section():
    """Página de desenvolvedor (somente visível para admin/developer)."""
    import os

    st.subheader("Developer / Test Panel")
    st.markdown("Use este painel apenas para testes locais. Não exponha credenciais em repositórios.")

    smtp_host = st.text_input("SMTP_HOST", value=os.getenv("SMTP_HOST", ""), key="dev_smtp_host_page")
    smtp_port = st.text_input("SMTP_PORT", value=os.getenv("SMTP_PORT", "587"), key="dev_smtp_port_page")
    smtp_user = st.text_input("SMTP_USER", value=os.getenv("SMTP_USER", ""), key="dev_smtp_user_page")
    smtp_password = st.text_input("SMTP_PASSWORD", value=os.getenv("SMTP_PASSWORD", ""), type="password", key="dev_smtp_password_page")
    email_from = st.text_input("EMAIL_FROM", value=os.getenv("EMAIL_FROM", ""), key="dev_email_from_page")

    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Apply to session", key="dev_apply_page"):
            os.environ["SMTP_HOST"] = smtp_host
            os.environ["SMTP_PORT"] = smtp_port
            os.environ["SMTP_USER"] = smtp_user
            os.environ["SMTP_PASSWORD"] = smtp_password
            os.environ["EMAIL_FROM"] = email_from
            st.success("Credenciais aplicadas à sessão (variáveis de ambiente do processo).")
    with col2:
        if st.button("Test SMTP connection", key="dev_test_smtp_page"):
            try:
                import smtplib
                s = smtplib.SMTP(smtp_host, int(smtp_port), timeout=10)
                s.starttls()
                s.login(smtp_user, smtp_password)
                s.quit()
                st.success("Conexão SMTP OK")
            except Exception as e:
                st.error(f"Erro conexão SMTP: {e}")

    if st.button("Test DB connection", key="dev_test_db_page"):
        try:
            from db import get_connection
            with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    _ = cur.fetchone()
            st.success("Conexão com o banco OK")
        except Exception as e:
            st.error(f"Erro conexão DB: {e}")
