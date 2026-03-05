"""Funções auxiliares e utilitárias para a aplicação."""

import pandas as pd
import streamlit as st
from datetime import date, datetime
from decimal import Decimal
import os
import smtplib
from email.message import EmailMessage


def esconder_botao_fechar_dialog() -> None:
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


def safe_convert_date(value):
    """Converte diversos formatos de data para date, retorna None se inválido."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.split("T")[0]).date()
        except Exception:
            return None
    if hasattr(value, "date"):
        try:
            return value.date()
        except Exception:
            return None
    return None


def safe_str(val):
    """Converte valor para string, retorna vazia se None ou NaN."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    return str(val)


def safe_int(val, default=0):
    """Converte valor para int, retorna default se inválido."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


def valor_to_float(v):
    """Converte valor (dict, Decimal, string) para float."""
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


def date_to_str(v):
    """Converte data/datetime para string no formato DD/MM/YYYY."""
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


def enviar_email_codigo(destinatario: str, nome: str, codigo: str) -> None:
    """Envia o código de redefinição para o e-mail informado.

    Configurar via variáveis de ambiente:
    - SMTP_HOST
    - SMTP_PORT
    - SMTP_USER
    - SMTP_PASSWORD
    - EMAIL_FROM (opcional)
    Se as variáveis não estiverem configuradas, a função irá levantar exceção.
    """
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    email_from = os.getenv("EMAIL_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_password:
        raise RuntimeError("Configuração SMTP incompleta. Defina SMTP_HOST, SMTP_USER e SMTP_PASSWORD.")

    subject = "Redefinição de senha - Gestão de Associados"
    body = f"""
        Olá {nome},

        Código de autenticação:
        {codigo}

        Este código possui 8 dígitos.
        Este código é válido por 15 minutos e só pode ser usado uma vez.

        Se você não solicitou a redefinição, ignore esta mensagem.

        Atenciosamente,
        Equipe Gestão de Associados
    """

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = destinatario
    msg.set_content(body)

    # Envia via TLS
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as server:
        server.starttls()
        server.login(smtp_user, smtp_password)
        server.send_message(msg)


def status_to_text(valor):
    """Normaliza status (dict ou outro) para texto legível."""
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
