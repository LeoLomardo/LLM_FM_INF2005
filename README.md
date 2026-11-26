# LLM_FM_INF2005
Reprodução e replicação de *Large Language Models to generate meaningful feature model instances*
(Galindo et al., SPLC'23, DOI 10.1145/3579027.3608973) — INF2005, PUC-Rio, 2026.2.

## Setup (Python 3.12)
```bash
./scripts/setup_env.sh          # cria .venv, instala deps, registra kernel "Python (splc23-llm)"
source .venv/bin/activate
cp .env.example .env            # (o setup já faz isso) e preencha OPENAI_API_KEY / COHERE_API_KEY
```
As chaves são lidas **somente do `.env`** (que tem prioridade sobre variáveis do shell). Nunca commite o `.env`.

> O Flamapy está fixado nas versões de 2023: o Flamapy 2.x atual não lê 26 dos 30 modelos originais.
> O `flamapy-bdd==1.0.1` tem metadados quebrados no PyPI, por isso o script o instala com `--no-deps`.

## Estrutura
| Caminho | Conteúdo |
|---|---|
| `SPLC'23.ipynb` | notebook **original** dos autores (não editar — referência da reprodução) |
| `SPLC23_atualizado.ipynb` | notebook corrigido/atualizado (roda local; flags `RUN_*` para chamadas pagas) |
| `replication/` | config (`.env`), geração com LLM (OpenAI/Ollama), embeddings Cohere v2 API |
| `fm_characterization/` | métricas/análise de FMs dos autores (com correção de API do flamapy-sat) |
| `1.model_selection/` | 1215 modelos SPLOT (FamaXML) e os 30 selecionados em UVL |
| `2.inference/1.API_call/` | 150 respostas originais do Codex (somente leitura) |
| `2.inference/replication/<modelo>/` | saídas da replicação com LLMs atuais |
| `3.results/` | embeddings originais (`2.cohere`), recalculados (`3.cohere_v3`), CSV e figuras |
| `Documentos/Artigo/` | artigo em LaTeX (`acmart`) |

## LLM local (Ollama)
No `.env`: `OPENAI_BASE_URL=http://localhost:11434/v1`, `OPENAI_MODEL=llama3.1:8b`, `OPENAI_API_KEY=ollama`.
