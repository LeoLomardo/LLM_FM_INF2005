"""Geração em lote das variantes UVL (IG-8/IG-9/IG-10).

Uso (na raiz do repo, com o .venv ativo):
    python -m replication.generate --provider openai                 # modelo de OPENAI_MODEL
    python -m replication.generate --provider ollama --model gemma2:9b

* Retomável: variantes já geradas são puladas.
* Log por chamada em <saida>/generation_log.jsonl (modelo/versão, tokens, tempo, finish).
* Saída: 2.inference/replication/<slug-do-modelo>/{1.API_call, 2.new_models}
"""
from __future__ import annotations

import argparse
import json
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from .config import PATHS, env, get_openai_client
from .llm import (DEFAULT_TEMPERATURE, DEFAULT_TOP_P, build_instruction_prompt,
                  extract_uvl, instruction_prompt_variant)

N_VARIANTS = 5


def slug(s: str) -> str:
    return "".join(c if c.isalnum() or c in "-._" else "_" for c in s)


def ollama_variant(model: str, uvl_text: str, num_ctx: int, num_predict: int,
                   host: str = "http://localhost:11434"):
    """API nativa do Ollama: permite fixar num_ctx (o endpoint /v1 ignora `options`)."""
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": build_instruction_prompt(uvl_text)}],
        "stream": False,
        "options": {"temperature": DEFAULT_TEMPERATURE, "top_p": DEFAULT_TOP_P,
                    "num_ctx": num_ctx, "num_predict": num_predict},
    }
    req = urllib.request.Request(f"{host}/api/chat", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        raw = json.loads(r.read())
    return extract_uvl(raw["message"]["content"]), raw


def ollama_digest(model: str, host: str = "http://localhost:11434") -> str | None:
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=10) as r:
            for m in json.loads(r.read())["models"]:
                if m["name"] == model or m["model"] == model:
                    return m.get("digest")
    except Exception:
        return None
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=["openai", "ollama"], required=True)
    ap.add_argument("--model", help="padrão: OPENAI_MODEL (openai) / gemma2:9b (ollama)")
    ap.add_argument("--n", type=int, default=N_VARIANTS)
    ap.add_argument("--workers", type=int, default=6, help="paralelismo (só openai)")
    ap.add_argument("--max-tokens", type=int, default=8192)
    ap.add_argument("--num-ctx", type=int, default=8192, help="janela do Ollama (gemma2: máx 8192)")
    ap.add_argument("--only", nargs="*", help="restringe a estes arquivos .uvl (piloto)")
    args = ap.parse_args(argv)

    model = args.model or (env("OPENAI_MODEL", required=True) if args.provider == "openai" else "gemma2:9b")
    base = PATHS["replication"] / slug(model)
    api_dir, var_dir = base / "1.API_call", base / "2.new_models"
    api_dir.mkdir(parents=True, exist_ok=True)
    var_dir.mkdir(parents=True, exist_ok=True)
    log_path = base / "generation_log.jsonl"
    lock = threading.Lock()

    inputs = sorted(PATHS["selected_uvl"].glob("*.uvl"))
    if args.only:
        inputs = [p for p in inputs if p.name in set(args.only)]
    jobs = [(f, i) for f in inputs for i in range(1, args.n + 1)
            if not (var_dir / f"{i}_{f.name}").exists()]
    print(f"[{model}] {len(jobs)} variantes a gerar em {base}")

    client = get_openai_client() if args.provider == "openai" else None
    digest = ollama_digest(model) if args.provider == "ollama" else None

    def run(f: Path, i: int):
        t0 = time.time()
        if args.provider == "openai":
            uvl, raw = instruction_prompt_variant(client, model, f.read_text(), max_tokens=args.max_tokens)
            usage = raw.get("usage") or {}
            rec = {"model_version": raw.get("model"), "prompt_tokens": usage.get("prompt_tokens"),
                   "completion_tokens": usage.get("completion_tokens"),
                   "finish_reason": raw["choices"][0].get("finish_reason"),
                   "system_fingerprint": raw.get("system_fingerprint")}
        else:
            uvl, raw = ollama_variant(model, f.read_text(), args.num_ctx, args.max_tokens)
            rec = {"model_version": f"{model}@{digest}", "prompt_tokens": raw.get("prompt_eval_count"),
                   "completion_tokens": raw.get("eval_count"), "finish_reason": raw.get("done_reason"),
                   "num_ctx": args.num_ctx}
        dt = time.time() - t0
        (api_dir / f"{f.name}_r_{i}.json").write_text(json.dumps(raw, indent=2))
        (var_dir / f"{i}_{f.name}").write_text(uvl)
        rec.update({"input": f.name, "iteration": i, "provider": args.provider, "model": model,
                    "seconds": round(dt, 2), "timestamp": datetime.now(timezone.utc).isoformat(),
                    "empty": not uvl.strip()})
        with lock, open(log_path, "a") as fh:
            fh.write(json.dumps(rec) + "\n")
        return rec

    workers = args.workers if args.provider == "openai" else 1
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(run, f, i): (f.name, i) for f, i in jobs}
        for fut in as_completed(futs):
            name, i = futs[fut]
            done += 1
            try:
                r = fut.result()
                print(f"[{done}/{len(jobs)}] {i}_{name} {r['seconds']}s "
                      f"out={r['completion_tokens']} finish={r['finish_reason']}", flush=True)
            except Exception as e:  # segue; a próxima execução retoma
                print(f"[{done}/{len(jobs)}] FALHA {i}_{name}: {type(e).__name__}: {e}", flush=True)


if __name__ == "__main__":
    main()
