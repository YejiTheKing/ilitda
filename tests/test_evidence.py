from ilitda.tools.evidence import find_quote, verify_evidence

DOC = {"name": "메모.txt", "text": "1. 거래처가 처음이면 사업자등록증부터 받는다.\n2. 회계 프로그램에 거래처 코드를 만든다. (코드는 영업이 직접 만듦)"}


def test_exact_and_whitespace_tolerant_match():
    assert find_quote("사업자등록증부터 받는다", DOC["text"])[0]
    assert find_quote("회계프로그램에 거래처코드를 만든다", DOC["text"])[0]


def test_fabricated_quote_is_rejected():
    found, ratio = find_quote("대표 승인을 받은 뒤 결재 시스템에 올린다", DOC["text"])
    assert not found and ratio < 0.85


def test_verify_marks_steps_without_real_evidence():
    steps = [
        {"order": 1, "action": "사업자등록증 수령", "evidence": [{"doc": "메모.txt", "quote": "사업자등록증부터 받는다"}]},
        {"order": 2, "action": "대표 승인", "evidence": [{"doc": "메모.txt", "quote": "대표 승인을 받는다"}]},
        {"order": 3, "action": "없는 파일 인용", "evidence": [{"doc": "규정.pdf", "quote": "아무 문장"}]},
    ]
    out = verify_evidence(steps, [DOC])
    assert [s["status"] for s in out] == ["ok", "unverified", "unverified"]
    assert out[2]["evidence"][0]["why"] == "그런 파일이 없음"
