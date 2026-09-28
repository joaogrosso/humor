"""Diário de humor — uma nota por dia para cada área da vida."""

import hmac
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import streamlit as st

import db

st.set_page_config(page_title="Humor", page_icon="🙂", layout="centered")

FUSO = ZoneInfo("America/Sao_Paulo")  # o servidor (ex.: Streamlit Cloud) roda em UTC

NOTAS = {"inicio": "Início", "fim": "Fim", "dia": "Dia"}
ESCALA_ROTULOS = {
    "casamento": "Casamento",
    "trabalho": "Trabalho",
    "espiritualidade": "Espiritualidade",
    "tempo": "Tempo",
    "investimentos": "Investimentos",
}
ESCALA = ["Horrível", "Ruim", "Médio", "Bom", "Maravilhoso"]
BINARIOS = {"exercicio": "Exercício"}

PADRAO = {c: 5 for c in NOTAS} | {c: "Médio" for c in ESCALA_ROTULOS} | {
    c: None for c in BINARIOS
}

hoje = datetime.now(FUSO).date()

# --------------------------------------------------------------------------
# Senha: o repositório é público, então o app pede a senha definida em
# st.secrets["senha_app"]. Sem ela configurada (uso local), não pede nada.
# --------------------------------------------------------------------------

try:
    SENHA_APP = st.secrets.get("senha_app")
except FileNotFoundError:
    SENHA_APP = None

if SENHA_APP and not st.session_state.get("autenticado"):
    with st.form("login"):
        senha = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", use_container_width=True):
            if hmac.compare_digest(senha, SENHA_APP):
                st.session_state["autenticado"] = True
                st.rerun()
            st.error("Senha incorreta.")
    st.stop()

# --------------------------------------------------------------------------
# Estado: ao abrir (ou trocar de pessoa/dia) carrega o rascunho salvo no banco
# --------------------------------------------------------------------------

# O nome fica na URL (?nome=João) para cada um salvar seu atalho no celular.
if "nome" not in st.session_state and st.query_params.get("nome") in db.NOMES:
    st.session_state["nome"] = st.query_params["nome"]

nome = st.segmented_control("Nome", db.NOMES, key="nome")
if nome is None:
    st.info("Escolha quem está preenchendo.")
    st.stop()
st.query_params["nome"] = nome

dia = st.date_input(
    "Dia", value=hoje, max_value=hoje, min_value=hoje - timedelta(days=30), format="DD/MM/YYYY"
)

if st.session_state.get("carregado") != (nome, dia):
    salvo = db.carregar_dia(dia, nome) or {}
    for campo in db.CAMPOS:
        valor = salvo.get(campo)
        st.session_state[campo] = PADRAO[campo] if valor is None else valor
    st.session_state["registrado"] = bool(salvo.get("registrado"))
    st.session_state["carregado"] = (nome, dia)


def valores_atuais() -> dict:
    return {c: st.session_state[c] for c in db.CAMPOS}


def salvar_rascunho() -> None:
    db.salvar_dia(dia, nome, valores_atuais())
    st.toast("Salvo", icon="💾")


# --------------------------------------------------------------------------
# Formulário (cada alteração é salva na hora como rascunho)
# --------------------------------------------------------------------------

if st.session_state["registrado"]:
    st.success("Dia registrado ✓ — alterações continuam sendo salvas.")
else:
    st.caption("Rascunho: vá preenchendo ao longo do dia, tudo fica salvo.")

st.subheader("Notas (0 a 10)")
for campo, rotulo in NOTAS.items():
    st.slider(rotulo, 0, 10, key=campo, on_change=salvar_rascunho)

st.subheader("Áreas")
for campo, rotulo in ESCALA_ROTULOS.items():
    st.select_slider(rotulo, options=ESCALA, key=campo, on_change=salvar_rascunho)

st.subheader("Hábitos")
for campo, rotulo in BINARIOS.items():
    st.segmented_control(rotulo, ["Sim", "Não"], key=campo, on_change=salvar_rascunho)

faltando = [BINARIOS[c] for c in BINARIOS if st.session_state[c] is None]
if st.button("Registrar", type="primary", use_container_width=True):
    if faltando:
        st.error(f"Preencha: {', '.join(faltando)}")
    else:
        db.salvar_dia(dia, nome, valores_atuais(), registrar=True)
        st.session_state["registrado"] = True
        st.rerun()

# --------------------------------------------------------------------------
# Histórico
# --------------------------------------------------------------------------

with st.expander("Histórico"):
    historico = db.carregar_historico(nome)
    if historico.empty:
        st.info("Nenhum dia registrado ainda.")
    else:
        st.line_chart(
            historico.set_index("data")[list(NOTAS)].rename(columns=NOTAS).sort_index()
        )
        st.dataframe(
            historico.drop(columns=["nome", "registrado", "atualizado_em"]).rename(
                columns={"data": "Data"} | NOTAS | ESCALA_ROTULOS | BINARIOS
            ),
            hide_index=True,
        )
