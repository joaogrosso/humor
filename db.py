"""Camada de dados do diário de humor.

Um único registro por pessoa por dia (chave = data + nome). Enquanto o dia não é registrado, a linha
fica com registrado = FALSE e funciona como rascunho: cada alteração na tela é salva
na hora, então dá para preencher aos poucos (e em aparelhos diferentes) e só clicar
em "Registrar" no fim do dia.

Banco: usa a URL em st.secrets["database_url"] (ex.: Supabase/Postgres) ou, se não
houver, um SQLite local em humor.db — assim o app roda local sem configurar nada.
"""

import importlib.util
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine, make_url

CAMPOS_NOTA = ["sono", "inicio", "fim", "dia"]  # 0 a 10
CAMPOS_ESCALA = ["casamento", "trabalho", "espiritualidade", "tempo", "investimentos"]
CAMPOS_BINARIOS = ["exercicio"]
CAMPOS = CAMPOS_NOTA + CAMPOS_ESCALA + CAMPOS_BINARIOS

NOMES = ("João", "Raissa")

ARQUIVO_SQLITE = Path(__file__).with_name("humor.db")


def _url_banco() -> str:
    try:
        url = st.secrets.get("database_url")
    except FileNotFoundError:  # sem secrets.toml → modo local
        url = None
    if not url:
        return f"sqlite:///{ARQUIVO_SQLITE}"
    driver = "psycopg" if importlib.util.find_spec("psycopg") else "psycopg2"
    return make_url(url).set(drivername=f"postgresql+{driver}").render_as_string(
        hide_password=False
    )


@st.cache_resource(show_spinner=False)
def engine() -> Engine:
    eng = create_engine(_url_banco(), pool_pre_ping=True)
    tipos = {c: "INTEGER" for c in CAMPOS_NOTA} | {
        c: "TEXT" for c in CAMPOS_ESCALA + CAMPOS_BINARIOS
    }
    colunas = ",\n".join(f"{c} {tipo}" for c, tipo in tipos.items())
    with eng.begin() as conn:
        conn.execute(
            text(
                f"""
                CREATE TABLE IF NOT EXISTS registros (
                    data DATE NOT NULL,
                    nome TEXT NOT NULL CHECK (nome IN {NOMES}),
                    {colunas},
                    registrado BOOLEAN NOT NULL DEFAULT FALSE,
                    atualizado_em TEXT NOT NULL,
                    PRIMARY KEY (data, nome)
                )
                """
            )
        )
        # Migração: campos criados depois da tabela (ex.: sono) entram como colunas novas,
        # vazias nos dias já registrados.
        existentes = {col["name"] for col in inspect(conn).get_columns("registros")}
        for campo in CAMPOS:
            if campo not in existentes:
                conn.execute(text(f"ALTER TABLE registros ADD COLUMN {campo} {tipos[campo]}"))
        if eng.dialect.name == "postgresql":
            # Mesmo cuidado do dashboard financeiro: nada exposto pela API pública do Supabase.
            conn.execute(text("ALTER TABLE registros ENABLE ROW LEVEL SECURITY"))
            conn.execute(text("REVOKE ALL ON TABLE registros FROM anon, authenticated"))
    return eng


def carregar_dia(dia: date, nome: str) -> dict | None:
    with engine().connect() as conn:
        linha = conn.execute(
            text("SELECT * FROM registros WHERE data = :data AND nome = :nome"),
            {"data": dia.isoformat(), "nome": nome},
        ).mappings().first()
    return dict(linha) if linha else None


def salvar_dia(dia: date, nome: str, valores: dict, registrar: bool = False) -> None:
    """Upsert do dia. registrar=True marca como registrado; senão preserva o status."""
    params = {c: valores.get(c) for c in CAMPOS}
    params |= {
        "data": dia.isoformat(),
        "nome": nome,
        "registrar": registrar,
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
    }
    colunas = ", ".join(CAMPOS)
    marcadores = ", ".join(f":{c}" for c in CAMPOS)
    atualizacoes = ", ".join(f"{c} = excluded.{c}" for c in CAMPOS)
    with engine().begin() as conn:
        conn.execute(
            text(
                f"""
                INSERT INTO registros (data, nome, {colunas}, registrado, atualizado_em)
                VALUES (:data, :nome, {marcadores}, :registrar, :atualizado_em)
                ON CONFLICT (data, nome) DO UPDATE SET
                    {atualizacoes},
                    registrado = registros.registrado OR excluded.registrado,
                    atualizado_em = excluded.atualizado_em
                """
            ),
            params,
        )


def carregar_historico(nome: str) -> pd.DataFrame:
    with engine().connect() as conn:
        return pd.read_sql(
            text("SELECT * FROM registros WHERE registrado AND nome = :nome ORDER BY data DESC"),
            conn,
            params={"nome": nome},
        )
