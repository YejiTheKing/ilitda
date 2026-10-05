"""LLM 호출.

모든 호출은 JSON 스키마를 지정해 구조화된 결과를 받는다.
호출마다 요청과 응답을 기록하고, 재생 모드에서는 같은 요청에 기록된 응답을 돌려준다.
재생은 API 장애·발표 현장 네트워크 장애에 대비한 대체 경로이며, 사용 여부는 실행 로그에 남는다.
"""
import hashlib
import json
import os
import time
from pathlib import Path

import anthropic

DEFAULT_MODEL = "claude-opus-5-5"
# 이 PC에는 다른 용도의 ANTHROPIC_BASE_URL이 걸려 있을 수 있어 공식 주소를 기본값으로 둔다
DEFAULT_BASE_URL = "https://api.anthropic.com"
CACHE_DIR = Path("runs/_llm_cache")


class LLMError(Exception):
    pass


USAGE_FILE = Path("runs/_usage.json")


def _usage_today():
    from datetime import date
    try:
        data = json.loads(USAGE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    today = date.today().isoformat()
    return data, today, int(data.get(today, 0))


def _count_call():
    data, today, n = _usage_today()
    data[today] = n + 1
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps(data), encoding="utf-8")


def _check_cap():
    """공개 테스트 중 비용 폭주를 막는다. ILITDA_MAX_LIVE_CALLS_PER_DAY가 설정된 날에만 적용."""
    cap = os.environ.get("ILITDA_MAX_LIVE_CALLS_PER_DAY")
    if not cap:
        return
    _, _, n = _usage_today()
    if n >= int(cap):
        raise LLMError(f"오늘의 AI 호출 한도({cap}회)에 도달했습니다. 저장된 응답이 있는 기본 예시는 계속 쓸 수 있습니다")


class LLM:
    def __init__(self, log=None, mode=None, model=None, cache_dir=CACHE_DIR):
        """mode: 'live'(호출 후 기록), 'replay'(기록만 사용), 'auto'(기록 있으면 사용, 없으면 호출)."""
        self.log = log
        self.mode = mode or os.environ.get("ILITDA_LLM_MODE", "auto")
        self.model = model or os.environ.get("ILITDA_MODEL") or DEFAULT_MODEL
        self.cache_dir = Path(os.environ.get("ILITDA_LLM_CACHE", cache_dir))
        self._client = None
        self.calls = 0
        self.replays = 0
        self.usage = {"input_tokens": 0, "output_tokens": 0}

    @property
    def client(self):
        if self._client is None:
            self._client = anthropic.Anthropic(
                base_url=os.environ.get("ILITDA_API_BASE_URL", DEFAULT_BASE_URL),
                max_retries=2,
                timeout=120,
            )
        return self._client

    def _key(self, system, user, schema):
        raw = json.dumps([self.model, system, user, schema], ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:24]

    def ask(self, name, system, user, schema, effort="medium", max_tokens=16000):
        """구조화된 답을 dict로 돌려준다. name은 로그에 표시할 호출 이름."""
        key = self._key(system, user, schema)
        path = self.cache_dir / f"{key}.json"

        if self.mode in ("replay", "auto") and path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            self.replays += 1
            if self.log:
                self.log.add("tool", f"llm:{name}", "기록된 응답 재생", tool="llm", replay=True, model=data["model"])
            return data["output"]
        if self.mode == "replay":
            raise LLMError(f"재생할 기록이 없음: {name}")
        # 테스트용: 호출 실패 상황을 강제로 만든다
        if os.environ.get("ILITDA_FAIL_LLM") == "1":
            raise LLMError("API 오류 (강제 실패)")
        _check_cap()

        started = time.perf_counter()
        last_error = None
        for attempt in range(1, 3):
            try:
                # 긴 문서는 생각(thinking)과 출력이 길어진다. 스트리밍으로 받아야 시간 초과가 없다
                with self.client.messages.stream(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
                ) as stream:
                    response = stream.get_final_message()
            except anthropic.APIStatusError as e:
                raise LLMError(f"API 오류 {e.status_code}: {e.message[:200]}") from e
            except anthropic.APIConnectionError as e:
                raise LLMError(f"연결 실패: {str(e)[:200]}") from e

            if response.stop_reason == "refusal":
                raise LLMError("모델이 요청을 거부함")
            if response.stop_reason == "max_tokens":
                raise LLMError(f"응답이 길이 한도({max_tokens} 토큰)에 걸림: 자료를 줄이거나 한도를 올려야 함")
            text = next((b.text for b in response.content if b.type == "text"), "")
            try:
                output = json.loads(text)
                break
            except json.JSONDecodeError as e:
                # 형식이 깨진 응답은 한 번 더 요청한다
                last_error = LLMError(f"응답이 JSON이 아님: {text[:100]}")
                if self.log:
                    self.log.add("feedback", f"llm:{name} 응답 형식 오류, 다시 요청 ({attempt}/2)")
        else:
            raise last_error

        self.calls += 1
        _count_call()
        self.usage["input_tokens"] += response.usage.input_tokens
        self.usage["output_tokens"] += response.usage.output_tokens
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({
            "name": name, "model": response.model, "system": system, "user": user,
            "schema": schema, "output": output,
            "usage": {"input_tokens": response.usage.input_tokens, "output_tokens": response.usage.output_tokens},
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        if self.log:
            self.log.add("tool", f"llm:{name}", f"입력 {response.usage.input_tokens} / 출력 {response.usage.output_tokens} 토큰",
                         tool="llm", replay=False, model=response.model,
                         seconds=round(time.perf_counter() - started, 1))
        return output
