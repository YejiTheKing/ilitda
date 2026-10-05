"""scan_folder: 허용된 폴더의 파일 목록을 만든다."""
import hashlib
import unicodedata
from pathlib import Path

from ilitda.safety.paths import check_allowed

READABLE = {".pdf", ".docx", ".xlsx", ".hwpx", ".hwp", ".txt", ".md"}
# 구형 오피스·사진 파일은 읽지 못한다. 목록에는 넣고 사용자에게 알린다. (.hwp는 글자만 읽는다)
KNOWN_UNREADABLE = {".doc", ".xls", ".ppt", ".pptx", ".jpg", ".jpeg", ".png"}


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def scan_folder(folder, allowed=None):
    """파일 목록을 돌려준다. 내용이 같은 사본은 같은 해시를 갖는다."""
    root = check_allowed(folder, allowed)
    if not root.is_dir():
        raise NotADirectoryError(f"폴더가 아닙니다: {folder}")

    files = []
    # 사본 표시가 붙은 파일은 뒤로 보내, 내용이 같을 때 원본 이름이 대표가 되게 한다
    def order(p):
        n = unicodedata.normalize("NFC", p.name).lower()
        return (any(k in n for k in ("복사본", "copy", "사본")), str(p))

    for p in sorted(root.rglob("*"), key=order):
        # 숨김 파일과 오피스 임시 잠금 파일(~$)은 업무 자료가 아니다
        if not p.is_file() or p.name.startswith((".", "~$")):
            continue
        # 가명 치환표·답변 파일 같은 설정 파일은 업무 자료가 아니다
        if p.suffix.lower() == ".json":
            continue
        ext = p.suffix.lower()
        files.append({
            "path": str(p),
            # macOS는 한글 파일명을 자모 분리 형태로 저장하는 경우가 있어 합쳐 준다
            "name": unicodedata.normalize("NFC", p.name),
            "ext": ext,
            "size": p.stat().st_size,
            "sha1": _sha1(p),
            "readable": ext in READABLE,
        })
    return files
