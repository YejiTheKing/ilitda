"""명령 인터페이스.

사용:
  python -m ilitda.cli read <자료 폴더>
  python -m ilitda.cli run <자료 폴더> --goal "인계 목표"            (멈출 때마다 터미널에서 답을 받음)
  python -m ilitda.cli run <자료 폴더> --goal "..." --replies 파일.json   (답을 파일에서 읽음, 테스트용)
"""
import argparse
import json
import sys

from dotenv import load_dotenv

from ilitda.runlog import RunLog
from ilitda.safety.paths import NotAllowedError
from ilitda.tools.ingest import ingest


def cmd_read(args):
    log = RunLog()
    try:
        result = ingest(args.folder, log)
    except (NotAllowedError, NotADirectoryError) as e:
        print(f"중단: {e}")
        return 1

    print(f"실행 ID {log.run_id}")
    print(f"읽은 문서 {len(result['documents'])}개")
    for d in result["documents"]:
        print(f"  - {d['name']} ({len(d['text'])}자)")
    if result["copies"]:
        print(f"같은 내용의 사본 {len(result['copies'])}개")
        for c in result["copies"]:
            print(f"  - {c['name']} = {c['same_as']}")
    if result["unreadable"]:
        print(f"읽지 못한 파일 {len(result['unreadable'])}개")
        for u in result["unreadable"]:
            print(f"  - {u['name']}: {u['reason']}")
    if not result["documents"]:
        print("읽을 수 있는 자료가 없습니다. 양식, 절차 메모, 체크리스트 파일(PDF, Word, Excel, HWPX, 텍스트)을 넣어 주세요.")
        return 1
    print(f"실행 로그: {log.path}")
    return 0


# ---------- run ----------

def _answer_interactively(pending):
    kind = pending["type"]
    if kind == "error":
        print(f"\n[오류] {pending['message']}")
        if input("다시 시도할까요? (y/n)> ").strip().lower() != "y":
            raise SystemExit(1)
        return None
    if kind == "clarify_goal":
        print(f"\n[되물음] {pending['question']}")
        return input("> ").strip()
    if kind == "ask_owner":
        print(f"\n[{pending['owner']}에게 확인 요청 {len(pending['questions'])}건] 모르면 비워 두세요(미확정 처리). 절차 수정은 화면에서만 할 수 있습니다.")
        replies = {}
        for i, q in enumerate(pending["questions"], 1):
            print(f"\n{i}. ({q['kind']}) {q['question']}")
            for c in q.get("claims", []):
                print(f"     - {c['doc']}: {c['says']}")
            replies[q["topic"]] = input("   답변> ").strip()
        return replies
    if kind == "newcomer_progress":
        print(f"\n[{pending['newcomer']} 수행 확인] 완료한 항목 번호를 쉼표로 입력하세요. 없으면 비워 두세요.")
        for i in pending["checklist"]:
            mark = "완료" if pending["progress"].get(str(i["order"]), {}).get("done") else ("필수" if i["required"] else "선택")
            print(f"  {i['order']}. [{mark}] {i['text']}  (확인: {i['how_to_verify']})")
        raw = input("완료 번호> ").strip()
        return {k.strip(): {"done": True} for k in raw.split(",") if k.strip()}
    if kind == "owner_approval":
        print(f"\n[{pending['owner']} 승인] 미완료 필수 항목 {len(pending['incomplete'])}개")
        for i in pending["incomplete"]:
            print(f"  - {i['text']}")
        ok = input("인계 완료를 승인합니까? (y/n)> ").strip().lower() == "y"
        return {"approved": ok, "note": input("메모> ").strip()}
    raise ValueError(f"알 수 없는 멈춤 종류: {kind}")


def _answer_from_file(pending, replies):
    """테스트용. replies: {"ask_owner": {...}, "newcomer_progress": [{...}, ...], "owner_approval": {...}}"""
    kind = pending["type"]
    value = replies.get(kind)
    if isinstance(value, list):
        return value.pop(0) if value else {}
    if value is None:
        return "" if kind == "clarify_goal" else {}
    return value


def cmd_run(args):
    from ilitda.agent.runner import Runner

    scripted = json.load(open(args.replies, encoding="utf-8")) if args.replies else None
    runner = Runner(llm_mode=args.llm_mode)
    print(f"실행 ID {runner.log.run_id}")
    try:
        pending = runner.start(args.goal, args.folder)
        same = 0
        while pending:
            if pending["type"] == "error" and scripted:
                print(f"[오류] {pending['message']}")
                break
            reply = _answer_from_file(pending, scripted) if scripted else _answer_interactively(pending)
            before = pending["type"]
            pending = runner.retry() if pending["type"] == "error" else runner.resume(reply)
            # 같은 자리에서 계속 멈추면 답이 통하지 않는 것이다. 무한 반복을 막는다
            same = same + 1 if pending and pending["type"] == before else 0
            if scripted and same >= 3:
                print(f"[중단] '{before}' 단계에서 같은 멈춤이 반복됩니다. 대본의 답을 확인하세요.")
                break
        state = runner.state()
    finally:
        runner.close()

    print(f"\n상태: {state.get('status')}")
    for v in state.get("versions", []):
        print(f"최신본: {v['latest']}  ← {', '.join(v['family'])}")
    for s in state.get("steps", []):
        flag = "" if s["status"] == "ok" else " [확인 필요]"
        print(f"  {s['order']}. {s['action']}{flag}")
    for a in state.get("answers", []):
        print(f"답변({a['source']}): {a['topic']} → {a['answer'] or '미확정'}")
    print("지표:", json.dumps(state.get("metrics", {}), ensure_ascii=False))
    print(f"실행 로그: {runner.log.path}")
    return 0 if state.get("status") == "completed" else 1


def main(argv=None):
    load_dotenv(".env")
    parser = argparse.ArgumentParser(prog="ilitda", description="일잇다 인수인계 AI Agent")
    sub = parser.add_subparsers(dest="command", required=True)
    read = sub.add_parser("read", help="자료 폴더를 읽고 목록을 보여준다")
    read.add_argument("folder")
    read.set_defaults(func=cmd_read)
    run = sub.add_parser("run", help="인계를 처음부터 끝까지 진행한다")
    run.add_argument("folder")
    run.add_argument("--goal", required=True, help="인계 목표 문장")
    run.add_argument("--replies", help="멈춤에 대한 답을 담은 JSON 파일 (테스트용)")
    run.add_argument("--llm-mode", choices=["live", "replay", "auto"], default=None)
    run.set_defaults(func=cmd_run)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
