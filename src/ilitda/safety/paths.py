"""폴더 허용 목록.

에이전트는 사용자가 허용한 폴더 안의 파일만 읽는다.
"""
import os
from pathlib import Path


class NotAllowedError(PermissionError):
    pass


def allowed_dirs():
    raw = os.environ.get("ILITDA_ALLOWED_DIRS", "data/sample,data/real,runs/uploads")
    dirs = [Path(p.strip()).resolve() for p in raw.split(",") if p.strip()]
    if os.environ.get("ILITDA_PUBLIC") == "1":
        # 공개 모드는 설정이 어떻게 되어 있어도 가상 자료와 올린 파일만 읽는다 (실제 자료 노출 방지)
        public_ok = {Path("data/sample").resolve(), Path("runs/uploads").resolve()}
        dirs = [d for d in dirs if d in public_ok]
    return dirs


def check_allowed(path, allowed=None):
    """허용된 폴더 안이면 실제 경로를 돌려주고, 아니면 NotAllowedError."""
    # resolve()로 ../ 와 심볼릭 링크를 풀어서 허용 폴더 밖으로 나가는 경로를 막는다
    real = Path(path).resolve()
    for base in allowed if allowed is not None else allowed_dirs():
        base = Path(base).resolve()
        if real == base or base in real.parents:
            return real
    raise NotAllowedError(f"허용되지 않은 경로입니다: {path}")
