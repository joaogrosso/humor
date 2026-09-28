# Humor

Diário de humor diário (João e Raissa) em Streamlit. Cada alteração é salva na hora como
rascunho; "Registrar" fecha o dia.

## Rodar local

```
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m streamlit run app.py
```

Sem `.streamlit/secrets.toml` usa SQLite local (`humor.db`). Para usar o Supabase, copie
`.streamlit/secrets.toml.example` para `secrets.toml` e preencha `database_url`.
