"""Geração de variantes UVL com LLMs atuais.

Dois modos:
* `codex_style_insertion` — reproduz a chamada original (completions com `suffix`,
  inserção na linha 10). Só funciona com modelos que ainda aceitam `suffix`
  na API legada de completions; o Codex (code-davinci-002) foi desativado em 2023.
* `instruction_prompt_variant` — replicação: instruction prompting com o texto
  descrito no próprio artigo (Seção 3), via Chat Completions. Funciona com a
  OpenAI e com qualquer endpoint compatível (ex.: Ollama, OPENAI_BASE_URL).
"""
from __future__ import annotations

import re

# Texto do artigo (Galindo et al., SPLC'23, seção sobre instruction prompting).
PAPER_CONTEXT = (
    "UVL specifies variability models with a tree-like structure to represent the "
    "hierarchical structure of variability models. Below, you can see a simple example "
    "of a variability model in UVL."
)
PAPER_INSTRUCTION = "Augment the following UVL example while preserving formalism and semantic similarity."
# Acréscimo nosso (documentar no artigo como desvio): formato de saída.
OUTPUT_FORMAT = (
    "Return ONLY the complete augmented UVL model, using tabs for indentation, "
    "without explanations and without markdown code fences."
)

# Parâmetros do experimento original
DEFAULT_TEMPERATURE = 0.7
DEFAULT_TOP_P = 1


def build_instruction_prompt(uvl_text: str) -> str:
    return f"{PAPER_CONTEXT}\n\n{PAPER_INSTRUCTION}\n\n{uvl_text.rstrip()}\n\n{OUTPUT_FORMAT}"


_FENCE = re.compile(r"```[a-zA-Z]*\n(.*?)```", re.DOTALL)


def extract_uvl(text: str) -> str:
    """Remove cercas markdown (```uvl ... ```) caso o LLM as inclua mesmo assim."""
    m = _FENCE.search(text)
    return (m.group(1) if m else text).strip("\n") + "\n"


def instruction_prompt_variant(client, model: str, uvl_text: str,
                               temperature: float = DEFAULT_TEMPERATURE,
                               top_p: float = DEFAULT_TOP_P,
                               max_tokens: int = 4096,
                               seed: int | None = None):
    """Retorna (uvl_gerado, resposta_bruta_dict)."""
    kwargs = dict(
        model=model,
        messages=[{"role": "user", "content": build_instruction_prompt(uvl_text)}],
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
    )
    if seed is not None:
        kwargs["seed"] = seed
    resp = client.chat.completions.create(**kwargs)
    text = resp.choices[0].message.content or ""
    return extract_uvl(text), resp.model_dump()


def codex_style_insertion(client, model: str, prompt: str, suffix: str,
                          temperature: float = DEFAULT_TEMPERATURE, max_tokens: int = 500):
    """Chamada equivalente à original (openai<1.0 `openai.Completion.create`)."""
    resp = client.completions.create(
        model=model,
        prompt=prompt,
        suffix=suffix,
        temperature=temperature,
        max_tokens=max_tokens,
        top_p=1,
        frequency_penalty=0,
        presence_penalty=0,
        stop=["def", "#", "public", "$"],
    )
    return resp.model_dump()
