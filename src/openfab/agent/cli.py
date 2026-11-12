"""명령줄에서 Agent에게 질문하거나, 시험 문제로 채점한다.

    python -m openfab.agent ask "현재 공장에서 병목 공정은 어디인가요?"
    python -m openfab.agent eval                    # eval/questions.yaml 전체를 풀리고 채점
    python -m openfab.agent eval --only q01 q02     # 일부 문제만

실험 전에는 항상 "실행할까요? [y/N]"을 묻는다. eval에서 --auto-approve를 주면 묻지 않고
승인하되, 어떤 실험을 요청했는지는 agent_log.jsonl과 report.json에 그대로 남는다.
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import yaml

from openfab.agent.grading import PASS_RATIO, load_questions, run_eval
from openfab.agent.loop import claude_model, run_agent
from openfab.agent.tools import Toolbox, ask_human


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="OpenFab AI Agent")
    parser.add_argument("--base", default="configs/factory.yaml", help="기준 공장 설정")
    parser.add_argument("--model", help="모델 ID (기본: 환경변수 OPENFAB_AGENT_MODEL 또는 claude-opus-5-5)")
    commands = parser.add_subparsers(dest="command", required=True)

    ask = commands.add_parser("ask", help="질문 하나에 답하게 한다")
    ask.add_argument("question")
    ask.add_argument("--results", default="results", help="실험 결과 폴더")

    evaluate = commands.add_parser("eval", help="시험 문제를 풀리고 자동 채점한다")
    evaluate.add_argument("--questions", default="eval/questions.yaml")
    evaluate.add_argument("--only", nargs="+", metavar="ID", help="이 id의 문제만")
    evaluate.add_argument("--out", help="기록 폴더 (기본: results/eval/<날짜-시각>)")
    evaluate.add_argument("--auto-approve", action="store_true", help="실험 승인을 묻지 않는다 (기록은 남는다)")

    args = parser.parse_args(argv)
    with open(args.base, encoding="utf-8") as f:
        base = yaml.safe_load(f)
    model = claude_model(base, args.model)

    if args.command == "ask":
        run = run_agent(args.question, Toolbox(args.base, args.results), model)
        print(run.answer or f"(답을 끝내지 못했습니다: {run.stop_reason})")
        return

    questions = load_questions(args.questions)
    if args.only:
        missing = set(args.only) - {q.id for q in questions}
        if missing:
            parser.error(f"없는 문제 id입니다: {sorted(missing)}")
        questions = [q for q in questions if q.id in args.only]
    out = Path(args.out) if args.out else Path("results/eval") / time.strftime("%Y%m%d-%H%M%S")
    approve = (lambda plan: print(plan, "\n→ 자동 승인") or True) if args.auto_approve else ask_human
    report = run_eval(questions, model, out, args.base, approve)
    goal = "달성" if report["meets_goal"] else "미달"
    print(f"\n점수: {report['passed']}/{report['total']} (목표 {PASS_RATIO:.0%} {goal})")
    print(f"기록: {out / 'report.json'} · 틀린 문제: {out / 'failures.md'}")


if __name__ == "__main__":
    main()
