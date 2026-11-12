"""질문 → (도구 호출 → 결과)* → 답변 루프. 프레임워크 없이 API의 tool calling만 쓴다.

    messages = [질문]
    반복:
        응답 = 모델(messages)
        응답에 도구 호출이 없으면 → 그 글이 최종 답
        있으면 → Toolbox로 실행(승인·기록 포함)하고 결과를 messages에 붙여 다시 묻는다

모델은 "messages를 받아 응답을 돌려주는 함수"로만 다룬다. 그래서 테스트에서는 API 없이
미리 짜 둔 응답을 돌려주는 가짜 모델을 넣을 수 있다.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from openfab.agent.prompt import VERDICT_ANSWER, VERDICT_UNKNOWN, build_system_prompt
from openfab.agent.tools import TOOL_SCHEMAS, Toolbox

DEFAULT_MODEL = "claude-opus-5-5"
MAX_TURNS = 12  # 모델을 부르는 횟수 상한. 도구만 계속 부르며 끝나지 않는 경우를 막는다

Model = Callable[[list[dict[str, Any]]], Any]  # messages → 응답(.content, .stop_reason)

_VERDICT = re.compile(rf"^\s*판정\s*[:：]\s*({VERDICT_ANSWER}|{VERDICT_UNKNOWN})", re.MULTILINE)


@dataclass
class ToolCall:
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]


@dataclass
class AgentRun:
    question: str
    answer: str = ""
    verdict: str = "invalid"  # answer | unknown | invalid(판정 줄이 없거나 답을 못 끝냄)
    stop_reason: str = ""
    turns: int = 0
    tool_calls: list[ToolCall] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)  # 전체 대화 (기록용)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "verdict": self.verdict,
            "answer": self.answer,
            "stop_reason": self.stop_reason,
            "turns": self.turns,
            "tool_calls": [vars(call) for call in self.tool_calls],
            "messages": self.messages,
        }


def run_agent(question: str, toolbox: Toolbox, model: Model, max_turns: int = MAX_TURNS) -> AgentRun:
    run = AgentRun(question=question)
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]

    for turn in range(1, max_turns + 1):
        response = model(messages)
        run.turns, run.stop_reason = turn, response.stop_reason
        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [block for block in response.content if block.type == "tool_use"]
        if response.stop_reason != "tool_use" or not tool_uses:
            # end_turn이면 정상 종료. max_tokens·refusal 등으로 끊긴 답은 판정 줄이 없어 invalid가 된다
            run.answer = "\n".join(block.text for block in response.content if block.type == "text").strip()
            if response.stop_reason == "end_turn":
                run.verdict = parse_verdict(run.answer)
            break

        results = []
        for block in tool_uses:  # 한 응답에 도구 호출이 여러 개면 결과를 한 메시지에 모아 돌려준다
            result = toolbox.call(block.name, dict(block.input))
            run.tool_calls.append(ToolCall(block.name, dict(block.input), result))
            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": json.dumps(result, ensure_ascii=False),
                "is_error": "error" in result,
            })
        messages.append({"role": "user", "content": results})
    else:
        run.stop_reason = "max_turns"

    run.messages = [{"role": m["role"], "content": _plain(m["content"])} for m in messages]
    return run


def parse_verdict(answer: str) -> str:
    match = _VERDICT.search(answer)
    if not match:
        return "invalid"
    return "unknown" if match.group(1) == VERDICT_UNKNOWN else "answer"


def claude_model(base: dict[str, Any], model: str | None = None, effort: str = "medium") -> Model:
    """Claude API를 부르는 모델 함수를 만든다. `uv sync --extra agent`와 API 키가 필요하다."""
    try:
        import anthropic
    except ImportError as e:
        raise RuntimeError("anthropic 패키지가 없습니다. `uv sync --extra agent`를 실행해 주세요.") from e

    client = anthropic.Anthropic()  # ANTHROPIC_API_KEY 등 환경에서 인증 정보를 읽는다
    model = model or os.environ.get("OPENFAB_AGENT_MODEL", DEFAULT_MODEL)
    system = build_system_prompt(base)

    def call(messages: list[dict[str, Any]]) -> Any:
        return client.beta.messages.create(
            model=model,
            max_tokens=16000,
            system=system,
            tools=TOOL_SCHEMAS,
            messages=messages,
            output_config={"effort": effort},
            # 안전 분류기가 요청을 거절하면 서버가 다른 모델로 같은 요청을 이어서 처리한다
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )

    return call


def _plain(content: Any) -> Any:
    """SDK 응답 객체를 JSON으로 저장할 수 있는 dict로 바꾼다."""
    if isinstance(content, (str, dict)):
        return content
    blocks = []
    for block in content:
        if isinstance(block, dict):
            blocks.append(block)
        elif hasattr(block, "to_dict"):
            blocks.append(block.to_dict())
        else:
            blocks.append({k: v for k, v in vars(block).items() if not k.startswith("_")})
    return blocks
