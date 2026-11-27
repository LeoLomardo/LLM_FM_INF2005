#!/usr/bin/env bash
# Pipeline completo da replicação: geração (API + local) e funil.
# Retomável: pode ser interrompido (Ctrl+C) e rodado de novo; só gera o que falta.
# Uso: ./scripts/run_pipeline.sh [modelo_ollama]     (padrão: gemma2:9b)
set -euo pipefail
cd "$(dirname "$0")/.."
PY=.venv/bin/python
LOCAL_MODEL="${1:-gemma2:9b}"
mkdir -p 2.inference/replication

echo "== 1/3 Geração via API (OPENAI_MODEL do .env)"
$PY -u -W ignore -m replication.generate --provider openai

echo "== 2/3 Geração local via Ollama ($LOCAL_MODEL) — demora ~3 h"
curl -sf http://localhost:11434/api/version >/dev/null || { echo "Ollama não está rodando (ollama serve)"; exit 1; }
$PY -u -W ignore -m replication.generate --provider ollama --model "$LOCAL_MODEL"

echo "== 3/3 Funil (etapa 4 só se COHERE_API_KEY estiver no .env)"
$PY -W ignore -m replication.funnel 2> >(grep -v "^line \|ERROR:root" >&2)
echo ">> Resultados em 3.results/funnel/ — abra SPLC23_atualizado.ipynb para tabelas e figuras."
