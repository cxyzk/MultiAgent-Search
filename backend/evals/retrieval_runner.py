"""检索评测：在固定问题集上比较不同召回策略的命中率。

用法（backend 目录）：
    python -m evals.retrieval_runner
    python -m evals.retrieval_runner --mode bm25 --mode bm25+rerank

指标：
    Hit@1/3/5  gold 文档是否出现在前 k 条里
    MRR        首个命中排名的倒数均值（越接近 1 越好）

前提：eval_data/docs 下的文档已入库（title = 文件名去掉 .md）。
"""
import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

import yaml

from app.kb.embedding_retriever import embedding_retriever
from app.kb.hybrid_retriever import HybridRetriever
from app.kb.reranked_retriever import RerankedRetriever
from app.kb.retriever import bm25_retriever

CASES_PATH = Path(__file__).resolve().parent / "retrieval_cases.yml"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
TOP_K = 5
DEFAULT_MODES = ["bm25", "bm25+rerank", "embedding", "hybrid"]


def build(modes: list[str]) -> dict:
    hybrid = lambda: HybridRetriever(bm25_retriever, embedding_retriever)
    all_modes = {
        "bm25": bm25_retriever,
        "embedding": embedding_retriever,
        "hybrid": hybrid(),
        "bm25+rerank": RerankedRetriever(bm25_retriever),
        "hybrid+rerank": RerankedRetriever(hybrid()),
    }
    return {m: all_modes[m] for m in modes}


async def eval_mode(name: str, retriever, cases: list[dict]) -> list[dict]:
    rows = []
    for case in cases:
        try:
            hits = await retriever.search(case["question"], TOP_K)
        except Exception as e:                       # 单个策略失败不影响其它
            rows.append({"id": case["id"], "type": case.get("type", "positive"),
                         "error": str(e), "first_rank": None, "mrr": 0.0})
            continue

        titles = [h.get("title", "") for h in hits]
        gold = set(case["gold_docs"])
        ranks = [i + 1 for i, t in enumerate(titles) if t in gold]
        first = ranks[0] if ranks else None
        rows.append({
            "id": case["id"],
            "type": case.get("type", "positive"),
            "first_rank": first,
            "top5": titles,
            "mrr": (1 / first) if first else 0.0,
        })
    return rows


def summarize(rows: list[dict]) -> dict:
    n = len(rows) or 1
    ranks = [r.get("first_rank") for r in rows]

    def hit(k: int) -> float:
        return sum(1 for x in ranks if x and x <= k) / n

    return {"n": len(rows), "hit1": hit(1), "hit3": hit(3), "hit5": hit(5),
            "mrr": sum(r.get("mrr", 0.0) for r in rows) / n}


def pct(x: float) -> str:
    return f"{x * 100:5.1f}%"


def print_table(results: dict[str, list[dict]]) -> None:
    print(f"===== 检索评测（top_k={TOP_K}）=====\n")
    print(f"{'策略':<16}{'Hit@1':>8}{'Hit@3':>8}{'Hit@5':>8}{'MRR':>8}")
    print("-" * 50)
    for name, rows in results.items():
        s = summarize(rows)
        print(f"{name:<16}{pct(s['hit1']):>8}{pct(s['hit3']):>8}{pct(s['hit5']):>8}{s['mrr']:>8.3f}")

    print("\n===== 按题型分组（Hit@5 / MRR）=====")
    types = sorted({r["type"] for rows in results.values() for r in rows})
    print(f"{'策略':<16}" + "".join(f"{t:>18}" for t in types))
    print("-" * (16 + 18 * len(types)))
    for name, rows in results.items():
        cells = []
        for t in types:
            sub = [r for r in rows if r["type"] == t]
            s = summarize(sub)
            cells.append(f"{pct(s['hit5'])} / {s['mrr']:.2f}")
        print(f"{name:<16}" + "".join(f"{c:>18}" for c in cells))

    print("\n===== 未召回明细（前 5 条里没有 gold）=====")
    for name, rows in results.items():
        miss = [r for r in rows if not r.get("first_rank")]
        if not miss:
            print(f"{name}: 全部命中")
            continue
        print(f"{name}: {len(miss)} 题未命中 -> {[r['id'] for r in miss]}")


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", action="append", choices=DEFAULT_MODES + ["hybrid+rerank"],
                        help="只跑指定策略，可重复")
    args = parser.parse_args()

    cases = yaml.safe_load(CASES_PATH.read_text(encoding="utf-8"))
    modes = args.mode or DEFAULT_MODES
    retrievers = build(modes)

    results = {}
    for name, retriever in retrievers.items():
        print(f"▶ 评测 {name}（{len(cases)} 题）...")
        results[name] = await eval_mode(name, retriever, cases)

    print()
    print_table(results)

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    path = RESULTS_DIR / f"retrieval_{stamp}.json"
    payload = {
        "top_k": TOP_K,
        "summary": {name: summarize(rows) for name, rows in results.items()},
        "details": results,
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n报告已存档：{path}")


if __name__ == "__main__":
    asyncio.run(main())
