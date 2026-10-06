# 일잇다 — 담당자가 떠난 자리의 업무를 복원하는 인수인계 AI Agent

제4회 경남 AI·SW 경진대회 (일반부 · 업무혁신) 제출용 저장소 · 팀 바톤터치 (1인)

남겨진 파일 폴더 하나로 **최신본을 가리고, 근거 있는 절차를 복원하고, 모르는 것은 책임자에게 묻고, 신규자가 첫 업무를 끝내 책임자가 승인하면 인계 완료로 판정하고, 결과를 인수인계서(Word)로 내놓는** AI Agent입니다. LangGraph 상태 그래프 위에서 LLM 호출 5종이 이어지고, 사람 확인 4곳에서 멈췄다가 같은 자리에서 잇습니다.

## 실행

```bash
git clone https://github.com/YejiTheKing/ilitda
cd ilitda
python3 -m venv .venv && source .venv/bin/activate      # Windows: python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt && pip install -e .
cp .env.example .env                                      # Windows: copy .env.example .env  (ANTHROPIC_API_KEY=... 를 채웁니다)
streamlit run src/ilitda/ui/app.py                        # http://localhost:8501
```

- 가상 자료(`data/sample`)는 저장소에 들어 있습니다. `scripts/make_sample.py`는 다시 만들 때만 씁니다.
- API 키 없이도 가상 자료 `거래처등록_견적`은 `runs/_llm_cache`의 저장 응답으로 재생되어 끝까지 돌아갑니다. 화면과 로그에 "준비된 결과 재생"으로 표시됩니다. 인계 목표 문장을 바꾸거나 책임자 답변을 다르게 쓰면 실제 API 호출이 필요합니다.
pip install -r requirements.txt && pip install -e .
cp .env.example .env                      # ANTHROPIC_API_KEY=... 를 채웁니다
python scripts/make_sample.py             # 가상 자료 3종 생성 (data/sample)
streamlit run src/ilitda/ui/app.py        # http://localhost:8501
```

- API 키 없이도 가상 자료 `거래처등록_견적`은 `runs/_llm_cache`의 저장 응답으로 재생되어 끝까지 돌아갑니다. 화면과 로그에 "준비된 결과 재생"으로 표시됩니다.
- 화면 순서: **인계 시작**(파일 올리기 → 목표 한 문장) → **확인 요청함**(책임자: 질문 답변·절차 수정·승인) → **내 인계**(신규자: 체크리스트·인수인계서 내려받기) → **실행 로그**(판단·도구 호출·토큰·재생 여부).
- 시연영상의 실행 로그: `runs/20261006-045149-4c4a0e/log.jsonl`

## 검증

```bash
pytest                                    # 단위 테스트 24건
python scripts/run_testcases.py           # 대표 테스트 (API 키 필요, 저장 응답이 있으면 재생)
```

## 구조

| 경로 | 내용 |
|---|---|
| `src/ilitda/agent/graph.py` | LangGraph 노드 9개와 사람 확인 4곳 (interrupt), 완료 판정 |
| `src/ilitda/llm/` | Anthropic API 호출 5종 (JSON 스키마), 응답 기록·재생, 하루 한도 |
| `src/ilitda/tools/` | 파일 읽기 6형식(HWP 직접 구현), 버전 묶기·최신본 판별·변경 비교, 근거 실존 확인 |
| `src/ilitda/safety/` | 개인정보 형식 가림, 허용 폴더 밖 읽기 차단 |
| `src/ilitda/memory/` | 책임자 답변 저장(선택) · 다음 인계에 제안 |
| `src/ilitda/ui/` | Streamlit 화면 4개, 인수인계서(Word) 생성 |
| `data/sample/` | 가상 자료 3종(파일 22개)과 정답 메모 — 회사·사람·금액 모두 지어낸 것 |
| `docs/제출물/` | 개발완료보고서 · 기술설명서 · 발표자료 · 출처·AI 활용 신고서 |
| `docs/테스트결과/` | 대표 테스트 기록, 테스트 케이스 40건, 전후 비교 |
| `docs/07_문제해결_기록.md` | 보완 69건 (날짜·원인·조치) |

## 데이터와 안전

- 실제 사업장 자료는 저장소에 없습니다. 제공자 동의 아래 가명 사본만 LLM에 전달했고 대회 후 삭제합니다.
- 전송 전 개인정보 형식 7종을 가리고, 허용된 폴더만 읽으며 파일을 옮기거나 지우지 않습니다. API 키는 `.env`에만 둡니다.
- 근거 인용이 원문에 없으면 신규자에게 보여 주지 않습니다. 충돌·빈틈은 단정하지 않고 책임자에게 묻습니다.

## 오픈소스

LangGraph · Anthropic SDK · Streamlit · python-docx · openpyxl · pypdf · olefile 등 (MIT·BSD·Apache-2.0). 목록은 `requirements.lock.txt`, 출처는 `docs/제출물/05_출처_AI활용_신고서.md`.
