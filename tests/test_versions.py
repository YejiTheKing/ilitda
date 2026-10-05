from ilitda.tools.versions import diff_versions, group_versions, pick_latest, stem


def doc(name, text, revision=None):
    return {"name": name, "text": text, "meta": {"revision": revision} if revision else {}}


OLD = "견 적 서\n문서번호: Q-____-___\n유효기간: 견적일로부터 30일\n납품조건: 당사 출고 기준\n아래와 같이 견적합니다."
NEW = ("견 적 서\n문서번호: Q-2025-____ (연도-일련번호)\n유효기간: 견적일로부터 14일\n결제조건: 납품 후 30일 이내 현금 결제\n"
       "납품조건: 당사 출고 기준\n담당자: ______\n아래와 같이 견적합니다.\n※ 2025.03 개정: 유효기간 단축")


def test_stem_strips_version_noise():
    assert stem("견적서 양식_수정.docx") == stem("견적서 양식.docx") == stem("견적서 양식 - 복사본 (2).docx")
    assert stem("견적서 양식.docx") != stem("거래처등록_체크리스트.xlsx")


def test_group_by_name_or_content():
    docs = [doc("견적서 양식.docx", OLD), doc("견적서 양식_수정.docx", NEW),
            doc("체크리스트.xlsx", "순서 | 확인 항목\n1 | 사업자등록증 사본 수령")]
    fams = group_versions(docs)
    sizes = sorted(len(f["members"]) for f in fams)
    assert sizes == [1, 2]


def test_filled_record_is_not_a_version_of_the_blank_form():
    record = ("견 적 서\n문서번호: Q-2025-012\n수신: 한빛테크 귀중\n견적일자: 2025년 5월 20일\n"
              "유효기간: 견적일로부터 14일\n결제조건: 납품 후 30일 이내 현금 결제\n납품조건: 당사 출고 기준")
    docs = [doc("견적서 양식.docx", OLD), doc("견적서 양식_수정.docx", NEW), doc("견적서_Q-2025-012.docx", record)]
    fams = group_versions(docs)
    forms = next(f for f in fams if any(m["name"] == "견적서 양식.docx" for m in f["members"]))
    assert [m["name"] for m in forms["members"]] == ["견적서 양식.docx", "견적서 양식_수정.docx"]
    assert docs[2]["role"] == "record" and docs[0]["role"] == "form"


def test_pick_latest_by_content_not_mtime():
    fam = {"members": [doc("견적서 양식_수정.docx", NEW), doc("견적서 양식.docx", OLD)]}
    result = pick_latest(fam)
    assert result["latest"]["name"] == "견적서 양식_수정.docx"
    assert result["confident"]
    assert any("2025.03" in e for e in result["evidence"])


def test_pick_latest_flags_ambiguous_pair():
    fam = {"members": [doc("메모.txt", "1. 접수\n2. 검토"), doc("메모(1).txt", "1. 접수\n2. 발송")]}
    result = pick_latest(fam)
    assert not result["confident"]
    assert any("확인 필요" in e for e in result["evidence"])


def test_diff_reports_changed_added_removed():
    changes = diff_versions(doc("old", OLD), doc("new", NEW))
    kinds = [c["kind"] for c in changes]
    assert "changed" in kinds and "added" in kinds
    changed = [c for c in changes if c["kind"] == "changed" and "유효기간" in (c["old"] or "")]
    assert changed and "14일" in changed[0]["new"]


def test_revision_number_from_text_and_name():
    from ilitda.tools.versions import revision_number
    assert revision_number("구매 규정\n개정번호: 3\n제1조 ...") == (3,)
    assert revision_number("품질 매뉴얼 제2차 개정\n...") == (2,)
    assert revision_number("Rev. 1.2\n...") == (1, 2)
    assert revision_number("아무 표시 없음", "발주서_v2.docx") == (2,)
    assert revision_number("아무 표시 없음", "발주서.docx") is None


def test_explicit_revision_beats_dates():
    # 구버전에 더 최근 날짜가 적혀 있어도(예: 참고 일정) 개정번호가 우선한다
    old = doc("규정.docx", "구매 규정\n개정번호: 3\n시행일 2026.01.01\n제1조 발주는 팀장 승인")
    new = doc("규정_개정.docx", "구매 규정\n개정번호: 4\n시행일 2025.07.01\n제1조 발주는 대표 승인")
    r = pick_latest({"members": [old, new]})
    assert r["latest"]["name"] == "규정_개정.docx" and r["confident"]
    assert any("개정번호 4" in e for e in r["evidence"])


def test_partial_revision_numbers_are_not_used():
    a = doc("메모.txt", "개정번호: 2\n1. 접수")
    b = doc("메모_수정.txt", "1. 접수\n2. 검토\n2025.03 수정")
    r = pick_latest({"members": [a, b]})
    assert r["latest"]["name"] == "메모_수정.txt"
    assert any("일부 버전에만" in e for e in r["evidence"])


def test_field_level_diff():
    from ilitda.tools.versions import fields_of
    old = doc("a", "견 적 서\n유효기간: 30일\n납품조건: 당사 출고 기준\n아래와 같이 견적합니다.")
    new = doc("b", "견 적 서\n유효기간: 14일\n결제조건: 납품 후 30일\n납품조건: 당사 출고 기준\n아래와 같이 견적합니다.\n※ 2025.03 개정")
    assert fields_of(old["text"]) == {"유효기간": "30일", "납품조건": "당사 출고 기준"}
    changes = diff_versions(old, new)
    by_field = {c["field"]: c for c in changes if c["field"]}
    assert by_field["유효기간"]["kind"] == "changed" and "14일" in by_field["유효기간"]["new"]
    assert by_field["결제조건"]["kind"] == "added"
    assert any(c["field"] is None and c["kind"] == "added" and "개정" in c["new"] for c in changes)
