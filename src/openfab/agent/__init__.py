"""[3층] AI Agent: 하네스를 도구로만 사용해 실험을 계획·실행·해석한다.

tools.py    Agent가 누를 수 있는 도구 3개, 승인 게이트, 호출 기록
prompt.py   시스템 프롬프트 (규칙 + 기준 공장 설정)
loop.py     질문 → 도구 호출 → 답변 루프 (Claude API tool calling)
grading.py  eval/questions.yaml 자동 채점과 틀린 문제 기록
"""

from openfab.agent.grading import grade, load_questions, run_eval
from openfab.agent.loop import AgentRun, run_agent
from openfab.agent.tools import TOOL_SCHEMAS, Toolbox

__all__ = ["TOOL_SCHEMAS", "AgentRun", "Toolbox", "grade", "load_questions", "run_agent", "run_eval"]
