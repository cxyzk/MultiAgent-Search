from dataclasses import dataclass, asdict
import sys
import time
from app.agent.main_agent import run_main_agent
from pathlib import Path
import yaml
import json
import asyncio
from datetime import datetime



@dataclass
class CaseResult:
    case_id: str
    question: str
    passed: bool
    latency_s: float
    dispatched: list[str]      # 实际被调度的子智能体
    tool_calls: int            # 实际工具调用总次数
    failures: list[str]        # ★ 失败原因逐条列出，而不是一个干巴巴的 False
    answer_preview: str        # 回答前 150 字，人肉复核用


SUBAGENT_NAMES = {"search_agent", "weather_agent"}

CASES_PATH = Path(__file__).resolve().parent / "cases.yml"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def load_cases() -> list[dict]:
    with open(CASES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)

async def run_one_case(case) -> CaseResult:
    events:list[dict] = []
    async def on_progress(payload: dict) -> None:
        events.append(payload)  # 只记录，不推送——评测模式没有 WS
    start = time.monotonic()
    answer = await run_main_agent(case["question"], on_progress=on_progress)
    latency = round(time.monotonic() - start, 1)

    # ---- 从事件流审计实际行为 ----
    dispatched_set = set()

    for e in events:
        if e.get("agent") != "main_agent":
            continue
        if e.get("type") != "progress":
            continue

        for t in e.get("tools", []):
            if t in SUBAGENT_NAMES:
                dispatched_set.add(t)

    dispatched = sorted(dispatched_set)


    tool_calls = len([e for e in events if e["type"] == "tool_result"])

    # ---- 逐项对照 expect，失败原因进 failures ----
    expect = case["expect"]
    failures = []
    expected_subagents = sorted(expect.get("subagents", []))
    if sorted(dispatched) != expected_subagents:
        failures.append(f"调度不符：期望 {expected_subagents}，实际 {dispatched}")
    max_tool_calls = expect.get("max_tool_calls", 99)
    if tool_calls > max_tool_calls:
        failures.append(f"超预算：工具调用 {tool_calls} 次 > 上限 {max_tool_calls}")
    missing = [k for k in expect.get("must_contain", []) if k not in answer]
    if missing:
        failures.append(f"回答缺少关键词：{missing}")
    max_latency = expect.get("max_latency_s", 999)
    if latency > max_latency:
        failures.append(f"超时：{latency}s > {max_latency}s")

    return CaseResult(
        case_id=case["id"], question=case["question"],
        passed=not failures, latency_s=latency,
        dispatched=dispatched, tool_calls=tool_calls,
        failures=failures, answer_preview=answer[:150],
    )

async def main() -> None:
    cases = load_cases()
    # 命令行传用例 id 可只跑匹配的：python evals/runner.py vague_search_001
    only = set(sys.argv[1:])
    if only:
        cases = [c for c in cases if c["id"] in only]
    results = []
    for case in cases:
        print(f"▶ 运行 {case['id']}：{case['question']}")
        try:
            result = await run_one_case(case)
        except Exception as e:
            # 单个用例崩了记成失败继续跑，不能让一个用例丢掉整轮报告
            result = CaseResult(
                case_id=case["id"], question=case["question"],
                passed=False, latency_s=0.0,
                dispatched=[], tool_calls=0,
                failures=[f"用例执行异常：{type(e).__name__}: {e}"],
                answer_preview="",
            )
        results.append(result)

    # ---- 控制台报告（人看的）----
    passed_count = 0
    for r in results:
        if r.passed:
            passed_count += 1
    print(f"\n===== 评测报告：{passed_count}/{len(results)} 通过 =====")
    for r in results:
        mark = "✅" if r.passed else "❌"
        print(f"{mark} {r.case_id}  {r.latency_s}s  调度{r.dispatched}  工具x{r.tool_calls}")
        for reason in r.failures:
            print(f"     └ {reason}")

    # ---- JSON 存档（机器看的，供以后 diff 对比）----
    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    report_path = RESULTS_DIR / f"report_{stamp}.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump([asdict(r) for r in results], f, ensure_ascii=False, indent=2)
    print(f"报告已存档：{report_path}")


if __name__ == "__main__":
    asyncio.run(main())




