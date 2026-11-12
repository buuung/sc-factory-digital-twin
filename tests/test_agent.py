"""Agent 루프와 자동 채점. 실제 API 대신 미리 짜 둔 응답을 돌려주는 가짜 모델을 쓴다."""

import json
from types import SimpleNamespace

import yaml

from openfab.agent import Toolbox, grade, load_questions, run_agent, run_eval
from openfab.agent.grading import Question
from openfab.agent.loop import parse_verdict
from openfab.agent.prompt import build_system_prompt


def text(value):
    return SimpleNamespace(type="text", text=value)


def tool_use(name, arguments, id="call_1"):
    return SimpleNamespace(type="tool_use", name=name, input=arguments, id=id)


def scripted(*responses):
    """호출될 때마다 다음 응답을 돌려주는 가짜 모델. 받은 messages는 .seen에 남긴다."""
    queue = list(responses)
    seen = []

    def model(messages):
        seen.append(list(messages))
        content, stop_reason = queue.pop(0)
        return SimpleNamespace(content=content, stop_reason=stop_reason)

    model.seen = seen
    return model


PHOTO_EXPERIMENT = {
    "name": "photo_machines",
    "vary": {"processes.photo.machines": [1, 2], "release.lots": [30]},
    "seeds": [1],
    "reason": "병목 후보인 photo에 장비를 추가했을 때의 생산량 비교",
}


def experiment_then_answer(answer="판정: 답변\n병목은 photo입니다."):
    return scripted(
        ([text("실험하겠습니다."), tool_use("run_experiment", PHOTO_EXPERIMENT)], "tool_use"),
        ([text(answer)], "end_turn"),
    )


def test_loop_runs_tool_and_feeds_result_back(tmp_path):
    model = experiment_then_answer()
    run = run_agent("병목은?", Toolbox(results_dir=tmp_path, approve=lambda plan: True), model)

    assert run.verdict == "answer" and run.turns == 2
    assert run.tool_calls[0].result["status"] == "done"
    assert (tmp_path / "photo_machines" / "results.csv").exists()

    # 두 번째 호출에는 도구 결과가 tool_use_id와 함께 들어 있어야 한다
    tool_result = model.seen[1][-1]["content"][0]
    assert tool_result["type"] == "tool_result" and tool_result["tool_use_id"] == "call_1"
    conditions = json.loads(tool_result["content"])["experiments"][0]["conditions"]
    assert len(conditions) == 2 and "limited_by" in conditions[0]
    json.dumps(run.to_dict(), ensure_ascii=False)  # 기록을 JSON으로 저장할 수 있어야 한다


def test_rejected_experiment_is_reported_to_model_and_not_run(tmp_path):
    model = experiment_then_answer("판정: 모른다\n실험이 거절되어 답할 수 없습니다.")
    run = run_agent("병목은?", Toolbox(results_dir=tmp_path, approve=lambda plan: False), model)

    assert run.tool_calls[0].result["status"] == "rejected"
    assert not (tmp_path / "photo_machines").exists()
    assert "rejected" in model.seen[1][-1]["content"][0]["content"]


def test_tool_error_is_returned_as_error_result(tmp_path):
    bad = {**PHOTO_EXPERIMENT, "vary": {"processes.diffusion.machines": [1, 2]}}
    model = scripted(
        ([tool_use("run_experiment", bad)], "tool_use"),
        ([text("판정: 모른다\n그런 공정이 없습니다.")], "end_turn"),
    )
    run_agent("확산 공정은?", Toolbox(results_dir=tmp_path, approve=lambda plan: True), model)
    result = model.seen[1][-1]["content"][0]
    assert result["is_error"] and "없는 공정" in result["content"]


def test_loop_stops_after_max_turns(tmp_path):
    call = ([tool_use("search_results", {"query": "x"})], "tool_use")
    run = run_agent("?", Toolbox(results_dir=tmp_path), scripted(call, call, call), max_turns=3)
    assert run.stop_reason == "max_turns" and run.verdict == "invalid" and run.turns == 3


def test_verdict_line():
    assert parse_verdict("판정: 답변\n...") == "answer"
    assert parse_verdict("판정 : 모른다\n고장 모델이 없습니다.") == "unknown"
    assert parse_verdict("병목은 photo입니다.") == "invalid"


def test_experiment_names_cannot_escape_results_dir(tmp_path):
    toolbox = Toolbox(results_dir=tmp_path / "results", approve=lambda plan: True)
    result = toolbox.call("run_experiment", {**PHOTO_EXPERIMENT, "name": "../outside"})
    assert "error" in result and not (tmp_path / "outside").exists()


def test_grading_rules(tmp_path):
    experiment = Question("q", "?", "experiment", must_vary=["processes.photo.machines"])
    unknown = Question("q", "?", "unknown")
    toolbox = lambda approved: Toolbox(results_dir=tmp_path / str(approved), approve=lambda plan: approved)  # noqa: E731

    ran = run_agent("?", toolbox(True), experiment_then_answer())
    assert grade(experiment, ran).passed
    assert not grade(unknown, ran).passed  # 데이터가 없는 질문에 답을 냄

    # 실험이 거절됐는데도 답을 낸 경우: 실행된 실험이 없으므로 실패
    not_run = run_agent("?", toolbox(False), experiment_then_answer())
    assert not grade(experiment, not_run).passed

    said_unknown = run_agent("?", toolbox(True), scripted(([text("판정: 모른다\n고장 모델이 없습니다.")], "end_turn")))
    assert grade(unknown, said_unknown).passed
    assert not grade(experiment, said_unknown).passed

    no_verdict = run_agent("?", toolbox(True), scripted(([text("잘 모르겠습니다.")], "end_turn")))
    assert not grade(unknown, no_verdict).passed


def test_eval_writes_report_and_failure_record(tmp_path):
    questions = load_questions("eval/questions.yaml")[:2]
    assert [q.kind for q in questions] == ["experiment", "unknown"]

    # q01은 맞는 실험을 하고, q02(고장 질문)는 지어내서 답한다 → 1/2
    model = scripted(
        ([tool_use("run_experiment", PHOTO_EXPERIMENT)], "tool_use"),
        ([text("판정: 답변\n병목은 photo입니다.")], "end_turn"),
        ([text("판정: 답변\n고장이 잦으면 생산량이 20% 줄어듭니다.")], "end_turn"),
    )
    report = run_eval(questions, model, tmp_path, approve=lambda plan: True)

    assert (report["passed"], report["total"], report["meets_goal"]) == (1, 2, False)
    saved = json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))
    assert [q["passed"] for q in saved["questions"]] == [True, False]
    assert (tmp_path / "q01" / "photo_machines" / "results.csv").exists()  # 문제마다 결과 폴더가 따로
    assert (tmp_path / "q02" / "transcript.json").exists()
    failures = (tmp_path / "failures.md").read_text(encoding="utf-8")
    assert "## q02" in failures and "20% 줄어듭니다" in failures and "## q01" not in failures


def test_system_prompt_is_built_from_config():
    with open("configs/factory.yaml", encoding="utf-8") as f:
        prompt = build_system_prompt(yaml.safe_load(f))
    assert "photo: 장비 1대" in prompt and "판정: 모른다" in prompt
