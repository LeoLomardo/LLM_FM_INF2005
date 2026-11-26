"""Embeddings dos nomes de features (experimento 3) com a API v2 da Cohere."""
from __future__ import annotations

import numpy as np

# O artigo usou o modelo padrão da Cohere em 2023 (embeddings de 4096 dims,
# "large"/embed-english-v2.0), hoje desativado. A replicação usa v3.0 (1024 dims).
DEFAULT_MODEL = "embed-english-v3.0"


def embed_text(co, text: str, model: str = DEFAULT_MODEL, input_type: str = "clustering") -> np.ndarray:
    """Retorna array shape (1, d), mesmo formato dos .npy originais."""
    resp = co.embed(texts=[text], model=model, input_type=input_type, embedding_types=["float"])
    return np.array(resp.embeddings.float_)
