"""Configuração central: caminhos do repositório e chaves lidas do arquivo .env.

Todas as chaves vêm do .env na raiz do repositório (veja .env.example).
Nada de chave hard-coded no código ou no notebook.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# override=True: o .env tem prioridade sobre variáveis já exportadas no shell
load_dotenv(ROOT / ".env", override=True)

PATHS = {
    "famaxml": ROOT / "1.model_selection" / "1.all_splot_in_fama_xml",
    "all_uvl": ROOT / "1.model_selection" / "2.all_splot_in_uvl",
    "selected_uvl": ROOT / "1.model_selection" / "3.selected_models_in_uvl",
    "selected_uvl_spaces": ROOT / "1.model_selection" / "4.selected_models_in_uvl_copy",
    # Respostas originais do Codex (2023) — somente leitura, não sobrescrever.
    "codex_api_calls": ROOT / "2.inference" / "1.API_call",
    "codex_new_models": ROOT / "2.inference" / "2.new_models",
    # Saídas da replicação com LLMs atuais: 2.inference/replication/<modelo>/
    "replication": ROOT / "2.inference" / "replication",
    "results": ROOT / "3.results",
    # Embeddings originais (Cohere v2, 4096 dims) — somente leitura.
    "cohere_v2": ROOT / "3.results" / "2.cohere",
    # Embeddings recalculados (Cohere embed-english-v3.0).
    "cohere_v3": ROOT / "3.results" / "3.cohere_v3",
}


def env(name: str, default: str | None = None, required: bool = False) -> str | None:
    """Lê uma variável do ambiente/.env. Strings vazias contam como ausentes."""
    value = os.getenv(name) or default
    if required and not value:
        raise RuntimeError(
            f"Variável {name} não definida. Preencha-a no arquivo {ROOT / '.env'} "
            "(copie de .env.example)."
        )
    return value


def get_openai_client():
    """Cliente OpenAI (SDK >= 1.0). Com OPENAI_BASE_URL aponta para o Ollama/local."""
    from openai import OpenAI

    base_url = env("OPENAI_BASE_URL")
    api_key = env("OPENAI_API_KEY", required=not base_url) or "ollama"
    return OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)


def get_cohere_client():
    """Cliente Cohere (SDK >= 5, API v2)."""
    import cohere

    return cohere.ClientV2(api_key=env("COHERE_API_KEY", required=True))
