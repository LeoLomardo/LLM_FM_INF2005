"""Avaliação em funil (IG-12 a IG-17).

Etapas — cada uma só avalia as variantes aprovadas na anterior:
  1 SINTAXE   parser UVL do Flamapy; relação "Other" = inválida (critério do artigo).
  2 LÓGICA    modelo não vazio (>= 1 produto) e SEM dead features NOVAS em relação ao
              original (3 originais já têm dead features: REAL-FM-5, REAL-FM-19, fame_dbms).
  3 ESTRUTURA features e cross-tree constraints acrescentadas/removidas (por nome / AST).
  4 DOMÍNIO   só variantes que acrescentaram features sem remover nenhuma.
              Embedding SÓ das features acrescentadas vs. embedding do original; limiar
              0,5 (artigo) + linha de base nula (original vs. features dos outros 29 modelos).
              Nomes codificados (_id_N, F1...) são sinalizados.

Também calcula, para comparação com o artigo, o cosseno "estilo original" (lista inteira de
features da variante vs. do original) para todas as variantes sintaticamente válidas.

Uso:
    python -m replication.funnel                 # etapas 1-3 (+4 se COHERE_API_KEY definida)
    python -m replication.funnel --no-domain     # pula a etapa 4
Saída: 3.results/funnel/
"""
from __future__ import annotations

import argparse
import hashlib
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PATHS, env

warnings.filterwarnings("ignore")

OUT_DIR = PATHS["results"] / "funnel"
CACHE_DIR = PATHS["cohere_v3"] / "cache"
DOMAIN_THRESHOLD = 0.5
CODED_NAME = re.compile(r"^(_?id_[\d_]+|F\d+|feature_?\d+)$", re.IGNORECASE)


def llm_sources() -> dict[str, Path]:
    """{rótulo do LLM: pasta com as variantes <i>_<modelo>.uvl}"""
    src = {"codex": PATHS["codex_new_models"]}
    if PATHS["replication"].exists():
        for d in sorted(PATHS["replication"].iterdir()):
            if (d / "2.new_models").is_dir() and not d.name.startswith("codex_style"):
                src[d.name] = d / "2.new_models"
    return src


# ----------------------------------------------------------------------------- análise
def parse(path: Path):
    from flamapy.core.discover import DiscoverMetamodels
    return DiscoverMetamodels().use_transformation_t2m(str(path), "fm")


def syntax_ok(path: Path):
    try:
        model = parse(path)
    except Exception as e:
        return False, None, type(e).__name__
    if "Other" in str(model):
        return False, None, "OtherRelation"
    return True, model, None


def logic(model):
    """(válido/não vazio, set de dead features)."""
    from flamapy.metamodels.pysat_metamodel.transformations.fm_to_pysat import FmToPysat
    from flamapy.metamodels.pysat_metamodel import operations as sat
    sat_model = FmToPysat(model).transform()
    valid = bool(sat.Glucose3Valid().execute(sat_model).get_result())
    dead = set(sat.Glucose3DeadFeatures().execute(sat_model).get_result()) if valid else set()
    return valid, dead


def features(model) -> list[str]:
    return [f.name for f in model.get_features()]


def constraints(model) -> set[str]:
    return {str(c.ast) for c in model.get_constraints()}


_LEAF = re.compile(r"\[([^\[\]]+)\]")


def undeclared_in_constraints(model, names: set[str]) -> set[str]:
    """Nomes citados em constraints que não são features da árvore."""
    out = set()
    for c in model.get_constraints():
        s = str(c.ast)
        leaves = _LEAF.findall(s) if "[" in s else [s]
        out |= {x.strip() for x in leaves} - names
    return out


def originals() -> dict[str, dict]:
    out = {}
    for f in sorted(PATHS["selected_uvl"].glob("*.uvl")):
        m = parse(f)
        valid, dead = logic(m)
        out[f.name] = {"features": features(m), "constraints": constraints(m),
                       "dead": dead, "n_relations": len(m.get_relations())}
    return out


def evaluate(llm: str, var_dir: Path, orig: dict) -> list[dict]:
    rows = []
    for name, o in orig.items():
        for it in range(1, 6):
            p = var_dir / f"{it}_{name}"
            r = {"llm": llm, "input": name, "iteration": it, "exists": p.is_file()}
            rows.append(r)
            if not p.is_file():
                continue
            # 1 sintaxe
            ok, m, err = syntax_ok(p)
            r.update(s1_syntax=ok, s1_error=err)
            if not ok:
                continue
            fv, cv = features(m), constraints(m)
            added = [x for x in fv if x not in set(o["features"])]
            removed = [x for x in o["features"] if x not in set(fv)]
            r.update(n_features=len(fv), n_constraints=len(cv), n_relations=len(m.get_relations()),
                     features_string=" ".join(fv))
            # 3 estrutura (registrada para todas as sintaticamente válidas; o resumo filtra pela etapa 2)
            r.update(feat_added=len(added), feat_removed=len(removed),
                     ctc_added=len(cv - o["constraints"]), ctc_removed=len(o["constraints"] - cv),
                     added_features=";".join(added), removed_features=";".join(removed),
                     coded_added=sum(bool(CODED_NAME.match(x)) for x in added),
                     # feature já existente inserida de novo (o Codex faz isso): mesmo conjunto
                     # de nomes, mas estrutura diferente
                     n_duplicated=len(fv) - len(set(fv)))
            same_structure = (len(fv) == len(o["features"]) and cv == o["constraints"]
                              and r["n_relations"] == o["n_relations"])
            if not added and not removed:
                change = "copy" if same_structure else ("duplicated" if r["n_duplicated"] else "restructured")
            elif added and not removed:
                change = "only_added"
            elif removed and not added:
                change = "only_removed"
            else:
                change = "added_and_removed"
            r["s3_change"] = change
            # 2 lógica. O parser aceita constraints que citam features inexistentes
            # (ex.: "dynamic includes search_page" vira 3 constraints soltas); a tradução
            # para SAT quebra nesses casos -> erro semântico, classificado explicitamente.
            und = undeclared_in_constraints(m, set(fv))
            if und:
                r.update(s2_logic=False, s2_error="undeclared_feature_in_ctc",
                         undeclared=";".join(sorted(und)))
                continue
            try:
                valid, dead = logic(m)
            except Exception as e:
                r.update(s2_logic=False, s2_error=f"analysis_error:{type(e).__name__}")
                continue
            new_dead = sorted(dead - o["dead"])
            r.update(s2_not_void=valid, n_dead=len(dead), n_new_dead=len(new_dead),
                     new_dead=";".join(new_dead), s2_logic=valid and not new_dead)
            if not valid:
                r["s2_error"] = "void"
            elif new_dead:
                r["s2_error"] = "new_dead_features"
    return rows


# ----------------------------------------------------------------------------- domínio
def _cache_path(text: str, model: str) -> Path:
    h = hashlib.sha256(f"{model}\n{text}".encode()).hexdigest()[:24]
    return CACHE_DIR / f"{h}.npy"


def embed_many(texts: list[str], model: str) -> dict[str, np.ndarray]:
    """Embeddings com cache em disco; lotes de 96 (limite da API da Cohere)."""
    from .config import get_cohere_client
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    out, todo = {}, []
    for t in dict.fromkeys(texts):
        cp = _cache_path(t, model)
        if cp.exists():
            out[t] = np.load(cp)
        else:
            todo.append(t)
    if todo:
        co = get_cohere_client()
        for i in range(0, len(todo), 96):
            batch = todo[i:i + 96]
            resp = co.embed(texts=batch, model=model, input_type="clustering", embedding_types=["float"])
            for t, e in zip(batch, resp.embeddings.float_):
                out[t] = np.array(e)
                np.save(_cache_path(t, model), out[t])
    return out


def cos(a, b) -> float:
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))


def domain(df: pd.DataFrame, orig: dict, model: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    orig_str = {k: " ".join(v["features"]) for k, v in orig.items()}
    sel = df["s2_logic"].eq(True) & df["s3_change"].eq("only_added")
    added_str = df.loc[sel, "added_features"].str.replace(";", " ")
    texts = list(orig_str.values()) + added_str.tolist() + df["features_string"].dropna().tolist()
    E = embed_many(texts, model)

    # cosseno "estilo artigo": lista inteira da variante vs original (todas sintaticamente válidas)
    df["cos_full_list"] = [cos(E[fs], E[orig_str[i]]) if isinstance(fs, str) else np.nan
                           for fs, i in zip(df["features_string"], df["input"])]
    # etapa 4: só features acrescentadas vs original
    df["cos_added"] = np.nan
    df.loc[sel, "cos_added"] = [cos(E[a], E[orig_str[i]]) for a, i in zip(added_str, df.loc[sel, "input"])]
    df["s4_domain"] = np.where(sel, df["cos_added"] >= DOMAIN_THRESHOLD, np.nan)

    # linha de base nula: original i vs. features do original j (j != i)
    base = [{"input": i, "other": j, "cos": cos(E[orig_str[i]], E[orig_str[j]])}
            for i in orig_str for j in orig_str if i != j]
    return df, pd.DataFrame(base)


# ----------------------------------------------------------------------------- resumo
def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (c - h, c + h)


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for llm, g in df.groupby("llm", sort=False):
        n = int(g["exists"].sum())
        s1 = int(g["s1_syntax"].eq(True).sum())
        s2 = int(g["s2_logic"].eq(True).sum())
        oa = int((g["s2_logic"].eq(True) & g["s3_change"].eq("only_added")).sum())
        s4 = int(g["s4_domain"].eq(1).sum()) if "s4_domain" in g else np.nan
        lo, hi = wilson(s1, n)
        rows.append({
            "llm": llm, "variantes": n,
            "s1_sintaxe": s1, "s1_%": round(100 * s1 / n, 1) if n else np.nan,
            "s1_IC95": f"[{100*lo:.1f}; {100*hi:.1f}]",
            "s2_logica": s2, "s2_%_das_s1": round(100 * s2 / s1, 1) if s1 else np.nan,
            "copias": int(g["s3_change"].eq("copy").sum()),
            "so_acrescentou": oa,
            "so_removeu": int(g["s3_change"].eq("only_removed").sum()),
            "acresc_e_removeu": int(g["s3_change"].eq("added_and_removed").sum()),
            "feat_add_med": g.loc[g["s1_syntax"].eq(True), "feat_added"].mean().round(2),
            "feat_rem_med": g.loc[g["s1_syntax"].eq(True), "feat_removed"].mean().round(2),
            "ctc_add_med": g.loc[g["s1_syntax"].eq(True), "ctc_added"].mean().round(2),
            "ctc_rem_med": g.loc[g["s1_syntax"].eq(True), "ctc_removed"].mean().round(2),
            "s4_dominio": s4,
            "cos_added_mediana": g["cos_added"].median().round(3) if "cos_added" in g else np.nan,
            "cos_full_mediana": g["cos_full_list"].median().round(3) if "cos_full_list" in g else np.nan,
        })
    return pd.DataFrame(rows)


def per_input_tests(df: pd.DataFrame) -> pd.DataFrame:
    """Wilcoxon pareado (30 modelos de entrada) da taxa de validade sintática entre LLMs."""
    from itertools import combinations
    from scipy.stats import wilcoxon
    rate = df[df["exists"]].groupby(["input", "llm"])["s1_syntax"].apply(lambda s: s.eq(True).mean()).unstack()
    out = []
    for a, b in combinations(rate.columns, 2):
        d = (rate[a] - rate[b]).dropna()
        p = wilcoxon(rate[a], rate[b], zero_method="zsplit").pvalue if d.abs().sum() > 0 else 1.0
        out.append({"llm_a": a, "llm_b": b, "media_a": rate[a].mean().round(3),
                    "media_b": rate[b].mean().round(3), "wilcoxon_p": round(float(p), 4)})
    return pd.DataFrame(out)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-domain", action="store_true")
    args = ap.parse_args(argv)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Analisando originais...")
    orig = originals()
    rows = []
    for llm, d in llm_sources().items():
        print(f"Funil: {llm} ({d})")
        rows += evaluate(llm, d, orig)
    df = pd.DataFrame(rows)

    model = env("COHERE_EMBED_MODEL", "embed-english-v3.0")
    if not args.no_domain and env("COHERE_API_KEY"):
        print(f"Etapa 4 com Cohere {model}...")
        df, base = domain(df, orig, model)
        base.to_csv(OUT_DIR / "domain_baseline.csv", index=False)
        print(f"Linha de base nula: mediana={base['cos'].median():.3f} p95={base['cos'].quantile(.95):.3f}")
    else:
        print("Etapa 4 PULADA (sem COHERE_API_KEY ou --no-domain).")

    df.to_csv(OUT_DIR / "funnel_variants.csv", index=False)
    summ = summarize(df)
    summ.to_csv(OUT_DIR / "funnel_summary.csv", index=False)
    tests = per_input_tests(df)
    tests.to_csv(OUT_DIR / "rq1_tests.csv", index=False)
    pd.set_option("display.width", 250, "display.max_columns", 40)
    print(summ.T.to_string())
    print(tests.to_string(index=False))


if __name__ == "__main__":
    main()
