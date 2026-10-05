"""개인정보 가림.

문서 내용을 LLM에 보내기 전에 개인정보 형식을 가린다.
형식만 보고 가리므로 이름·주소처럼 형식이 없는 정보는 가리지 못한다.
"""
import re

# 긴 형식부터 검사한다. 계좌번호를 전화번호로 잘못 가리지 않기 위해서다.
PATTERNS = [
    ("주민등록번호", re.compile(r"(?<!\d)\d{6}\s?-\s?[1-4]\d{6}(?!\d)")),
    ("사업자등록번호", re.compile(r"(?<!\d)\d{3}-\d{2}-\d{5}(?!\d)")),
    ("전화번호", re.compile(r"(?<!\d)0\d{1,2}[-.\s]\d{3,4}[-.\s]\d{4}(?!\d)")),
    ("계좌번호", re.compile(r"(?<!\d)\d{2,6}-\d{2,6}-\d{2,8}(?:-\d{1,4})?(?!\d)")),
    ("이메일", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("차량번호", re.compile(r"(?<![0-9])\d{2,3}\s?[가-힣]\s?\d{4}(?![0-9])")),
    # 도로명·지번 주소. 시도 이름으로 시작해 '로/길/동/읍/면 + 번지'까지
    ("주소", re.compile(r"(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주)"
                      r"(?:특별시|광역시|특별자치시|특별자치도|도)?[^|\n,]{0,25}?(?:로|길|동|읍|면|리)\s?\d+(?:-\d+)?"
                      r"(?:[^,|\n]{0,12}?(?:번길|번지|동|호|층)\s?\d*)?")),
]


DATE = re.compile(r"(?:19|20)\d{2}-(?:0?[1-9]|1[0-2])-(?:0?[1-9]|[12]\d|3[01])")


def _is_account(s):
    # 날짜(2026-10-06)는 버전 판별에 쓰이므로 가리면 안 된다. 계좌번호는 숫자가 10자리 이상이다.
    return not DATE.fullmatch(s) and sum(c.isdigit() for c in s) >= 10


def mask(text):
    """(가린 텍스트, 종류별 가린 개수)를 돌려준다."""
    counts = {}
    for label, pattern in PATTERNS:
        def replace(m, label=label):
            if label == "계좌번호" and not _is_account(m.group()):
                return m.group()
            counts[label] = counts.get(label, 0) + 1
            return f"[{label} 가림]"

        text = pattern.sub(replace, text)
    return text, counts
