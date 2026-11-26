#!/usr/bin/env bash
# Cria o .venv do projeto e instala as dependências.
# Uso: ./scripts/setup_env.sh            (usa python3.12 do sistema/pyenv)
#      PYTHON=python3.12 ./scripts/setup_env.sh
set -euo pipefail
cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3.12}"

if command -v uv >/dev/null 2>&1; then
    uv venv -p "$PYTHON" .venv
    export VIRTUAL_ENV="$PWD/.venv"
    uv pip install -r requirements.txt
    # flamapy-bdd 1.0.1: metadados quebrados no PyPI ("dd (>=0.5.6graphviz~=0.20)")
    uv pip install --no-deps flamapy-bdd==1.0.1
else
    "$PYTHON" -m venv .venv
    .venv/bin/pip install --upgrade pip
    .venv/bin/pip install -r requirements.txt
    .venv/bin/pip install --no-deps flamapy-bdd==1.0.1
fi

# Kernel do Jupyter apontando para este venv
.venv/bin/python -m ipykernel install --user --name splc23-llm --display-name "Python (splc23-llm)"

[ -f .env ] || { cp .env.example .env; echo ">> .env criado a partir de .env.example — preencha as chaves."; }
echo ">> Ambiente pronto. Ative com: source .venv/bin/activate"
