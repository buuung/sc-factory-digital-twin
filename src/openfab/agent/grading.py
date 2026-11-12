"""시험 문제(eval/questions.yaml)를 Agent에게 풀리고 자동 채점한다.

채점 기준 (정답 요약 answer와 함정 trap은 사람이 볼 참고용이고 채점에는 쓰지 않는다)
  kind: experiment  승인되어 실제로 실행된 run_experiment의 vary에 must_vary 키가 모두 들어 있고,
                    마지막 답이 "판정: 답변"이다
  kind: unknown     마지막 답이 "판정: 모른다"이다 (지어내지 않았다)

자동 채점은 "맞는 실험을 골랐는가"까지만 본다. 답의 숫자와 해석이 맞는지는 명민이 report를 보고
직접 검증한다. 문제마다 빈 결과 폴더에서 시작하므로 다른 문제의 실험 결과를 가져다 쓸 수 없다.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from openfab.agent.loop import AgentRun, Model, run_agent
from openfab.agent.tools import Toolbox, ask_human

KINDS = ("experiment", "unknown")
PASS_RATIO = 0.8  # 성공 기준: 10문제 중 8개 이상


@dataclass
class Question:
    id: str
    question: str
    kind: str
    must_vary: list[str] = field(default_factory=list)
    answer: str = ""
    trap: str = ""


@dataclass
class Grade:
    id: str
    passed: bool
    reason: str


def load_questions(path: str | Path) -> list[Question]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    questions = []
    for item in data.get("questions") or []:
        expected = item.get("expected") or {}
        kind = expected.get("kind")
        if kind not in KINDS:
            raise ValueError(f"{item.get('id')}: expected.kind는 {KINDS} 중 하나여야 합니다: {kind!r}")
        questions.append(Question(
            id=str(item["id"]),
            question=item["question"],
            kind=kind,
            must_vary=list(expected.get("must_vary") or []),
            answer=str(expected.get("answer", "")),
            trap=str(item.get("trap") or expected.get("trap") or ""),
        ))
    ids = [q.id for q in questions]
    if len(ids) != len(set(ids)):
        raise ValueError(f"문제 id가 중복됩니다: {ids}")
    return questions


def varied_keys(run: AgentRun) -> set[str]:
    """실제로 실행된(승인되고 오류 없이 끝난) 실험에서 바꾼 값의 키."""
    keys: set[str] = set()
    for call in run.tool_calls:
        if call.name == "run_experiment" and call.result.get("status") == "done":
            keys.update(call.arguments.get("vary") or {})
    return keys


def grade(question: Question, run: AgentRun) -> Grade:
    if run.verdict == "invalid":
        return Grade(question.id, False, f"답을 끝내지 못했거나 판정 줄이 없음 (stop_reason={run.stop_reason})")
    if question.kind == "unknown":
        if run.verdict == "unknown":
            return Grade(question.id, True, "데이터가 없다고 답함")
        return Grade(question.id, False, "데이터가 없는 질문인데 답을 냄")

    if run.verdict == "unknown":
        return Grade(question.id, False, "실험으로 답할 수 있는 질문인데 모른다고 함")
    missing = sorted(set(question.must_vary) - varied_keys(run))
    if missing:
        return Grade(question.id, False, f"필요한 값을 바꾸는 실험을 하지 않음: {missing}")
    return Grade(question.id, True, "필요한 실험을 실행하고 답함")


def run_eval(
    questions: list[Question],
    model: Model,
    out_dir: str | Path,
    base_config: str | Path = "configs/factory.yaml",
    approve: Callable[[str], bool] = ask_human,
) -> dict[str, Any]:
    """모든 문제를 풀리고 채점한 뒤 out_dir에 기록을 남긴다.

    out_dir/report.json           점수와 문제별 채점 결과
    out_dir/failures.md           틀린 문제를 "AI가 틀린 기록" 양식으로 정리한 초안
    out_dir/<문제 id>/            그 문제에서 Agent가 돌린 실험 결과, 도구 호출 기록, 전체 대화
    """
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    entries = []
    for question in questions:
        toolbox = Toolbox(base_config=base_config, results_dir=out / question.id, approve=approve)
        run = run_agent(question.question, toolbox, model)
        result = grade(question, run)
        (out / question.id).mkdir(parents=True, exist_ok=True)  # 도구를 한 번도 안 부르면 폴더가 없다
        with open(out / question.id / "transcript.json", "w", encoding="utf-8") as f:
            json.dump(run.to_dict(), f, ensure_ascii=False, indent=2, default=str)
        entries.append({
            "id": question.id,
            "passed": result.passed,
            "reason": result.reason,
            "question": question.question,
            "kind": question.kind,
            "must_vary": question.must_vary,
            "expected_answer": question.answer,
            "trap": question.trap,
            "verdict": run.verdict,
            "answer": run.answer,
            "tool_calls": [
                {"tool": c.name, "arguments": c.arguments, "status": _status(c.result)} for c in run.tool_calls
            ],
        })
        print(f"[{'통과' if result.passed else '실패'}] {question.id}: {result.reason}")

    passed = sum(e["passed"] for e in entries)
    report = {
        "passed": passed,
        "total": len(entries),
        "ratio": round(passed / len(entries), 3) if entries else 0.0,
        "meets_goal": bool(entries) and passed / len(entries) >= PASS_RATIO,
        "questions": entries,
    }
    with open(out / "report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    (out / "failures.md").write_text(_failures_markdown(entries), encoding="utf-8")
    return report


def _status(result: dict[str, Any]) -> str:
    if "error" in result:
        return f"error: {result['error']}"
    return str(result.get("status", "ok"))


def _failures_markdown(entries: list[dict[str, Any]]) -> str:
    """과정 기록의 "AI가 틀린 기록" 양식. 왜 틀렸나·고친 것·다시 해보니는 사람이 채운다."""
    failed = [e for e in entries if not e["passed"]]
    if not failed:
        return "# AI가 틀린 기록\n\n틀린 문제가 없습니다.\n"
    parts = ["# AI가 틀린 기록 (자동 생성 초안)\n"]
    for e in failed:
        calls = "\n".join(
            f"  - `{c['tool']}` {json.dumps(c['arguments'], ensure_ascii=False)} → {c['status']}"
            for c in e["tool_calls"]
        ) or "  - (도구를 부르지 않음)"
        expected = f"kind={e['kind']}" + (f", must_vary={e['must_vary']}" if e["must_vary"] else "")
        answer = "\n".join(f"  > {line}" for line in (e["answer"] or "(답 없음)").splitlines())
        parts.append(
            f"## {e['id']}\n\n"
            f"- 질문: {e['question']}\n"
            f"- 기대한 실험·도구: {expected} / 정답 요약: {e['expected_answer']}\n"
            f"- 실제 호출한 도구·입력값:\n{calls}\n"
            f"- AI 답 (판정: {e['verdict']}):\n{answer}\n"
            f"- 자동 채점 사유: {e['reason']}\n"
            + (f"- 문제에 적어 둔 함정: {e['trap']}\n" if e["trap"] else "")
            + "- 왜 틀렸나:\n- 고친 것 (도구 설명·시스템 프롬프트·규칙):\n- 다시 해보니:\n"
        )
    return "\n".join(parts)
