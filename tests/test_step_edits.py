from ilitda.agent.graph import _apply_step_edits
from ilitda.runlog import RunLog


def test_owner_edits_and_removals(tmp_path):
    log = RunLog(root=tmp_path)
    steps = [
        {"order": 1, "action": "사업자등록증 수령", "status": "ok", "evidence": [{"doc": "a", "quote": "x", "found": True}]},
        {"order": 2, "action": "메일로 대표 확인", "status": "unverified", "evidence": []},
        {"order": 3, "action": "발송대장 기록", "status": "ok", "evidence": []},
    ]
    out = _apply_step_edits(steps, {"edits": {"2": "결재 시스템에서 대표 승인"}, "remove": ["3"]}, "이대표", log)
    assert [s["action"] for s in out] == ["사업자등록증 수령", "결재 시스템에서 대표 승인"]
    assert out[1]["status"] == "ok" and out[1]["edited_by"] == "이대표" and out[1]["evidence"][0]["doc"] == "책임자 확인"
    assert [s["order"] for s in out] == [1, 2]
    titles = [e["title"] for e in log.read()]
    assert any("단계 수정" in t for t in titles) and any("단계 삭제" in t for t in titles)


def test_no_edits_keeps_steps(tmp_path):
    steps = [{"order": 1, "action": "a", "status": "ok", "evidence": []}]
    assert _apply_step_edits(steps, {}, "x", RunLog(root=tmp_path)) == steps


def test_owner_adds_missing_steps(tmp_path):
    steps = [{"order": i, "action": f"단계{i}", "status": "ok", "evidence": []} for i in range(1, 4)]
    out = _apply_step_edits(steps, {"add": [{"after": 1, "action": "현장에서 직접 수리하고 납품한다"},
                                            {"after": 3, "action": "세금계산서를 발행하고 명세서를 전달한다", "who": "경리"}]},
                            "팀장", RunLog(root=tmp_path))
    assert [s["action"] for s in out] == ["단계1", "현장에서 직접 수리하고 납품한다", "단계2", "단계3", "세금계산서를 발행하고 명세서를 전달한다"]
    assert [s["order"] for s in out] == [1, 2, 3, 4, 5]
    assert out[4]["who"] == "경리" and out[1]["evidence"][0]["doc"] == "책임자 확인"
