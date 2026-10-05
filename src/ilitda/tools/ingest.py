"""자료 읽기: 폴더를 훑고 읽을 수 있는 파일을 모두 읽는다.

읽지 못한 파일이 있어도 멈추지 않는다. 읽지 못한 파일은 이유와 함께 따로 모은다.
"""
from ilitda.tools.parse import UnreadableError, parse_document
from ilitda.tools.scan import scan_folder


def ingest(folder, log, allowed=None):
    """{"documents": [...], "unreadable": [...], "copies": [...]}를 돌려준다."""
    with log.tool("scan_folder", folder=str(folder)) as call:
        files = scan_folder(folder, allowed)
        call["result"] = f"파일 {len(files)}개"

    documents, unreadable, copies = [], [], []
    seen = {}
    for f in files:
        # 내용이 완전히 같은 사본은 한 번만 읽는다
        if f["sha1"] in seen:
            copies.append({"name": f["name"], "same_as": seen[f["sha1"]]})
            continue
        seen[f["sha1"]] = f["name"]
        try:
            with log.tool("parse_document", file=f["name"]) as call:
                doc = parse_document(f["path"], allowed)
                call["result"] = f"{len(doc['text'])}자"
        except UnreadableError as e:
            unreadable.append({"name": f["name"], "reason": str(e)})
            continue
        documents.append(doc | {"sha1": f["sha1"]})

    if unreadable:
        log.add("feedback", f"읽지 못한 파일 {len(unreadable)}개를 건너뜀",
                [f"{u['name']}: {u['reason']}" for u in unreadable])
    return {"documents": documents, "unreadable": unreadable, "copies": copies}
