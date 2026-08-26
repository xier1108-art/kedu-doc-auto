"""
AI 기반 PDF 메타데이터 추출 (Claude API)
=========================================

스캔 PDF (이미지 기반) 도 vision으로 OCR + 의미 파악합니다.
파일명 정규식보다 훨씬 정확하지만, ANTHROPIC_API_KEY 가 필요합니다.

API 키 설정 (택1)
-----------------
1) 환경변수: setx ANTHROPIC_API_KEY "sk-ant-..."  (재시작 필요)
2) 설정파일: %USERPROFILE%/.kedu_anthropic_key 에 키 한 줄
3) gui.py 의 [⚙ 설정] 버튼

비용: PDF 1건당 약 0.5~2원 (Haiku 4.5, 1~3페이지 기준)
"""
from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path

from pdf_parser import DocMeta

KEY_PATH = Path.home() / ".kedu_anthropic_key"
MODEL_PATH = Path.home() / ".kedu_anthropic_model"          # 선택된 모델 id 저장
MODELS_CACHE_PATH = Path.home() / ".kedu_anthropic_models.json"  # 동적 fetch 캐시

# Fallback 모델 목록 (API 호출 실패 시 사용)
# Anthropic 이 출시한 주요 모델들 — 실제 사용 가능 여부는 API 가 결정
_FALLBACK_MODELS: list[dict] = [
    {"id": "claude-opus-4-7",                "name": "Claude Opus 4.7",    "tier": "opus"},
    {"id": "claude-sonnet-4-6",              "name": "Claude Sonnet 4.6",  "tier": "sonnet"},
    {"id": "claude-opus-4-6",                "name": "Claude Opus 4.6",    "tier": "opus"},
    {"id": "claude-opus-4-5-20251101",       "name": "Claude Opus 4.5",    "tier": "opus"},
    {"id": "claude-haiku-4-5-20251001",      "name": "Claude Haiku 4.5",   "tier": "haiku"},
    {"id": "claude-sonnet-4-5-20250929",     "name": "Claude Sonnet 4.5",  "tier": "sonnet"},
]

# 기본값 — 첫 사용 시. 정확도 / 비용 균형
DEFAULT_MODEL = "claude-sonnet-4-5-20250929"


def _tier_of(model_id: str) -> str:
    """모델 id 에서 tier 추론. Anthropic 이 신규 tier 이름을 출시해도
    (예: fable, mythos) 최소한 '?' 로 안전하게 떨어짐 — 새로 발견되면
    TIER_HINT 에 한 줄만 추가하면 됨."""
    mid = model_id.lower()
    for t in ("opus", "sonnet", "haiku", "fable", "mythos"):
        if t in mid:
            return t
    return "?"


# 모델 tier 별 안내 (사용자에게 비용 감각)
TIER_HINT: dict[str, str] = {
    "opus":   "최고 정확도 / 비싼 (~50원/PDF 추정)",
    "sonnet": "균형 (정확 + 합리적 비용, ~10원/PDF)",
    "haiku":  "저렴 / 빠른 (~1원/PDF, 디지털 PDF 적합)",
    "fable":  "최상위 신규 모델 (가격 미확정 — 사용 전 콘솔에서 요금 확인)",
    "mythos": "최상위 신규 모델 (가격 미확정 — 사용 전 콘솔에서 요금 확인)",
    "?":      "신규/미분류 모델 — 사용 전 콘솔에서 요금 확인 권장",
}


def list_available_models(refresh: bool = False) -> list[dict]:
    """사용자 키로 사용 가능한 모델 목록.

    - refresh=True: API 호출해서 최신 목록 가져와 캐시 저장
    - refresh=False: 캐시 있으면 사용, 없으면 fallback
    """
    if refresh:
        key = get_api_key()
        if not key:
            return list(_FALLBACK_MODELS)
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=key)
            resp = client.models.list(limit=50)
            models = [
                {
                    "id": m.id,
                    "name": getattr(m, "display_name", m.id),
                    "tier": _tier_of(m.id),
                }
                for m in resp.data
            ]
            MODELS_CACHE_PATH.write_text(
                json.dumps(models, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            return models
        except Exception:
            # API 호출 실패 시 캐시 또는 fallback
            pass
    # 캐시 우선
    if MODELS_CACHE_PATH.exists():
        try:
            return json.loads(MODELS_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return list(_FALLBACK_MODELS)


def get_model() -> str:
    """저장된 모델 id (없으면 DEFAULT)."""
    if MODEL_PATH.exists():
        v = MODEL_PATH.read_text(encoding="utf-8").strip()
        if v:
            return v
    return DEFAULT_MODEL


def get_model_label() -> str:
    """현재 선택된 모델의 사람 친화 표시명 (예: 'Sonnet 4.5')."""
    mid = get_model()
    for m in list_available_models():
        if m["id"] == mid:
            # 'Claude Sonnet 4.5' → 'Sonnet 4.5'
            return m["name"].replace("Claude ", "")
    return mid


def save_model_id(model_id: str) -> None:
    """사용자가 선택한 모델 id 저장."""
    if not model_id:
        raise ValueError("model_id 가 비어있음")
    MODEL_PATH.write_text(model_id, encoding="utf-8")


# 하위 호환 — gui.py 가 import 하던 이름들
AVAILABLE_MODELS = {  # 더 이상 사용 안 하지만 import 호환용
    m["id"]: (m["id"], m["name"], TIER_HINT.get(m["tier"], ""))
    for m in _FALLBACK_MODELS
}
get_model_key = get_model           # alias (구 API)
save_model_key = save_model_id      # alias (구 API)


def get_api_key() -> str | None:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip()
    if KEY_PATH.exists():
        return KEY_PATH.read_text(encoding="utf-8").strip()
    return None


def save_api_key(key: str) -> None:
    KEY_PATH.write_text(key.strip(), encoding="utf-8")


PROMPT_TEMPLATE = """이 PDF는 한국 공공기관 접수용 문서입니다. 두 가지 유형 중 하나:
  [A] 일반 공문 (수신/참조/제목/시행 양식)
  [B] 조달청 검사검수요청서 등 나라장터 전자양식

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 1단계: 처음 1~2 페이지에서 유형 식별
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

‼ 기본값은 [A] 일반 공문이다. [B] 는 매우 엄격한 조건 모두 만족할 때만 인정.
   의심스러우면 무조건 [A] 로 처리.

[A] 일반 공문 표지의 결정적 표지 (다음 중 일부만 있어도 충분):
  ✓ "수신:" / "참조:" / "제목:" 라벨 (줄 단위)
  ✓ 하단 "시행 ○○(학교)제YYYY-N호(YYYY.MM.DD.)" 발송줄
  ✓ "끝." + 직인
  ✓ 상단 회사명/기관 로고
  ✓ 본문 "1. 귀 ○○의…", "2. 관련근거…", "3. 위 근거에…" 번호 단락

[B] 조달청 검사검수요청서 — ⚠ 다음 3개 조건을 ★모두★ 만족해야 인정:
  ★1. 페이지 상단 헤더에 "검 사 검 수 요 청 서" (띄어쓰기 포함) 또는 "검사검수요청서"
       가 큰 글자로 단독 배치. (본문 안에 인용된 "검사검수 요청" 같은 표현은 절대 아님)
  ★2. "※나라장터전자문서출력물" 표기가 헤더 부근에 있음
  ★3. 본문 구조에 "[공공기관]" 과 "[납품업체]" 박스가 좌우로 명시되어 있고
       그 안에 "기 관 명:", "업 체 명:", "기관코드:", "대 표 자:" 라벨이 표 형태로 있음

  ⚠ 다음 경우는 [B] 가 아니다 (= [A] 로 처리):
    - "수신: ..." / "참조: ..." / "제목: ..." 줄이 있는 문서 → A
    - 본문에 "검사검수요청" 또는 "검사" 단어만 등장하는 일반 보고/회신/요청 문서 → A
    - "○○공사 검사검수 요청 보고", "검사검수 의뢰" 같은 제목의 공문 → A
    - 표지에 "검사검수요청서" 헤더만 있고 [공공기관]/[납품업체] 박스가 없음 → A
    - "[공공기관]" / "[납품업체]" 박스가 없고 단순 표/내용만 있음 → A

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 2단계: 식별된 유형에 따라 추출 규칙 적용
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

═══════ [A 유형 — 일반 공문] ═══════

[발신자] **다음 3곳 중 어디서든 회사명/기관명을 잡아라** (서로 일치해야 신뢰):
  ★ 페이지 ★최상단★ 의 큰 글자 (예: "장위토건", "㈜대성씨엠건축사사무소") — 회사명/상호/기관명
  ★ 표지 ★하단 발신명의★ 영역 (직인 옆): "[주소] [회사명] 대표이사 [이름]" 패턴
  ★ ★직인★ 자체의 회사명

  ⚠ 다음은 절대 발신자가 아니다:
  ❌ "우 12345 주소: 서울시 ○○구 ..." 같은 주소 줄 → 주소일 뿐
  ❌ 행정구역명 단독 (예: "서울특별시 동대문구") → 주소의 일부, 발신기관 아님
  ❌ 직인 옆 책임자 이름 (대표이사/소장/원장 이름) → 발신자는 회사/기관, 사람이 아님
  ❌ 본문 인용 "설계사공문 : DNB ..." 외부 공문번호 → 발신자 아님
  ❌ 본문 큰 글씨 공사명 → 발신자 아님

  💡 사기업 공문(시공사/설계사 등): 회사명이 한자/한글 큰 글자로 상단 단독 배치.
     주소·전화·팩스는 그 회사명 옆/아래에 작게 표기됨. 회사명만 발신자.
[제목] 표지의 "제목:" 줄. 짧고 문서 유형 (보고/회신/제출/검토서/요청 등).
  ❌ 본문 가운데 큰 글씨 공사명 → 제목 아님 (공사명일 뿐)
[문서번호] 페이지 하단 "시행" 줄 번호 (발신자 본인 번호).
  예: "시행 대성(갈현초)제2026-84호(2026.04.28.)" → "대성(갈현초)제2026-84호"
[시행일자] "시행" 줄 괄호 안 YYYY.MM.DD.
[수신자] **반드시 "수신:" 줄에서만** 추출 (페이지 중상단, 발신자 주소 아래쪽)
  ✓ "수신: 서울특별시 서부교육지원청 교육장" → "서부교육지원청"
  ✓ 직위 제거: "○○지원청장"/"○○교육장"/"○○부장관" → 직위 단어만 빼고
  ⚠ 절대 수신자가 아닌 것 (수신자 후보에서 즉시 제외):
  ❌ 발신자(시공사·설계사 등) 자신의 주소 (예: "서울시 동대문구 천호대로 3,606호")
     → **발신자와 같은 행정구역**이면 100% 발신자 주소다. 수신자 아님.
  ❌ 행정구역명만 단독 (예: "서울특별시 동대문구") — 주소이지 기관 아님
  ❌ "○○구 교육청" 같이 ★존재하지 않는 기관★ (한국에는 시·도 교육청만 있음.
     "동대문구 교육청" / "강남구 교육청" 등은 없음 → OCR 환각이므로 절대 출력 금지)
  ❌ "참조:" 줄의 ○○과장/○○부장 등 — 참조이지 수신자 아님
═══════ [B 유형 — 조달청 검사검수요청서] ═══════

[제목] 형식: "검사검수요청서[{{계약건명}}]"
  계약건명 = "계약건명:" 또는 "계 약 건 명:" 옆의 텍스트 (공사명 + 자재명).
  예: "검사검수요청서[갈현초그린스마트미래학교및복합화증개축관급자재(레미콘-1차)]"
  ⚠ 금액 절대 포함 금지. 띄어쓰기는 원문 그대로.
[발신자] "[납품업체]" 박스의 "업 체 명:" 옆 회사명
  ❌ "[공공기관]" / "[실제납품업체]" 박스의 이름 → 아님
  예: "경기서북부레미콘사업협동조합"
[수신자] "[공공기관]" 박스의 "기 관 명:" 옆 기관명
  ✂ "서울특별시교육청서울특별시서부교육지원청" → "서울특별시서부교육지원청" 으로 단축
  ✂ 마지막 단위까지 (가장 구체적인 하위 기관). "서울특별시교육청" 만은 너무 광범위.
[문서번호] "검사검수요청번호:" 옆 값
  예: "R26NQ05390037-000"
  ❌ "계약번호", "납품요구번호", "주문번호" → 아님 (정확히 검사검수요청번호)
[시행일자] "작성일자:" 옆 날짜 → YYYY-MM-DD
  ❌ "검사요청일자", "검수요청일자" → 아님 (정확히 작성일자)
  예: "작성일자: 2026년05월07일" → "2026-05-07"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 출력 방법

반드시 record_document_metadata 도구를 호출해서 결과를 기록하라.
설명·분석 과정을 따로 쓰지 말고 곧바로 도구를 호출한다.
해당 항목을 못 찾으면 그 값은 빈 문자열 "" 로 둔다.

값 예시 (A 유형):
  cover_page="1", doc_type="A",
  title="설계도서 검토서(건축3차) 보고",
  sender="㈜대성씨엠건축사사무소",
  receiver="서울특별시서부교육지원청",
  doc_no="대성(갈현초)제2026-84호",
  date="2026-04-28"

⚠ 첨부 자료가 여러 장 붙어 있어도 ★표지(맨 앞 공문)★ 기준으로 판단한다.
   뒤쪽에 검사검수요청서가 별첨돼 있어도 표지가 일반 공문이면 doc_type="A".

참고용 파일명: {filename}
"""


# Claude API PDF 입력 제한
CLAUDE_MAX_PAGES = 5      # 어차피 표지는 1~2페이지이므로 5장이면 충분
CLAUDE_MAX_BYTES = 30 * 1024 * 1024  # 30MB

# `temperature` 를 거부하는 모델 id 캐시 (프로세스 내에서만 유지).
# 최신 모델은 temperature 가 deprecated 되어 400 을 반환하므로,
# 한 번 걸린 모델은 다음부터 아예 파라미터를 빼고 호출한다.
_NO_TEMPERATURE_MODELS: set[str] = set()


# 추출 결과를 받아내기 위한 도구 스키마.
# tool_choice 로 이 도구를 강제하면 모델이 반드시 이 형태로 값을 채워 보내므로
# "JSON 앞에 산문을 쓰다가 잘리는" 문제가 원천적으로 사라진다.
EXTRACT_TOOL: dict = {
    "name": "record_document_metadata",
    "description": "PDF 에서 읽어낸 한국 공문서 메타데이터를 기록한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "cover_page": {
                "type": "string",
                "description": "공문 표지가 몇 번째 페이지인지 ('1' 또는 '2'). 못 찾으면 '0'",
            },
            "doc_type": {
                "type": "string",
                "description": "'A'=일반 공문, 'B'=조달청 검사검수요청서. 판별 불가면 '?'",
            },
            "title": {
                "type": "string",
                "description": "제목. A유형은 '제목:' 줄, B유형은 '검사검수요청서[계약건명]' 형식",
            },
            "sender": {
                "type": "string",
                "description": "발신 기관/회사명. 주소·사람 이름·공사명은 제외",
            },
            "receiver": {
                "type": "string",
                "description": "수신 기관명. 직위(장/교육장) 제거",
            },
            "doc_no": {
                "type": "string",
                "description": "문서번호. A유형은 '시행' 줄 번호, B유형은 검사검수요청번호",
            },
            "date": {
                "type": "string",
                "description": "시행일자 YYYY-MM-DD 형식",
            },
        },
        "required": [
            "cover_page", "doc_type", "title",
            "sender", "receiver", "doc_no", "date",
        ],
    },
}


def _parse_json_object(text: str) -> dict:
    """응답 문자열에서 첫 번째 완결된 JSON 객체를 파싱.

    문자열 리터럴 안의 중괄호/이스케이프까지 고려해 괄호 균형을 맞춰 자른다.
    (greedy 정규식은 뒤에 설명 문장이 붙으면 실패하므로 직접 스캔)
    """
    start = text.find("{")
    if start == -1:
        raise ValueError(f"Claude 응답에서 JSON을 찾을 수 없음:\n{text[:500]}")

    depth = 0
    in_str = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])

    raise ValueError(f"Claude 응답의 JSON 이 닫히지 않았습니다:\n{text[:500]}")


def _truncate_pdf_if_needed(pdf_path: Path, max_pages: int = CLAUDE_MAX_PAGES,
                            max_bytes: int = CLAUDE_MAX_BYTES) -> bytes:
    """
    Claude API 의 100-page / 32MB 제한을 피하기 위해
    PDF 가 크면 첫 max_pages 페이지만 잘라서 새 PDF 바이트로 반환.
    표지는 어차피 1~2페이지에 있으므로 잘라도 손실 없음.
    """
    raw = pdf_path.read_bytes()
    try:
        import fitz
    except ImportError:
        return raw  # pymupdf 없으면 원본 그대로 (운에 맡김)

    with fitz.open(stream=raw, filetype="pdf") as doc:
        n = len(doc)
        if n <= max_pages and len(raw) <= max_bytes:
            return raw
        # 첫 max_pages 페이지만 추출
        out = fitz.open()
        out.insert_pdf(doc, from_page=0, to_page=min(max_pages, n) - 1)
        truncated = out.tobytes()
        out.close()
        return truncated


def extract_with_claude(pdf_path: Path, model: str | None = None) -> DocMeta | None:
    """Claude API로 PDF 메타데이터 추출. 키가 없으면 None 반환.

    PDF 가 100페이지/32MB 초과 시 자동으로 첫 5페이지로 잘라서 전송.
    model 지정 안 하면 사용자 저장 모델(없으면 기본=Sonnet) 사용.
    """
    key = get_api_key()
    if not key:
        return None
    if model is None:
        model = get_model()

    import anthropic
    client = anthropic.Anthropic(api_key=key)

    pdf_bytes = _truncate_pdf_if_needed(pdf_path)
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    prompt = PROMPT_TEMPLATE.format(filename=pdf_path.name)
    kwargs = {
        "model": model,
        # 도구 호출로 결과를 받지만, 모델이 앞서 생각을 쓸 수 있으므로 여유 있게.
        "max_tokens": 2048,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": pdf_b64,
                    },
                },
                {"type": "text", "text": prompt},
            ],
        }],
        # ★ 도구 호출 강제 (structured output).
        #   자유 텍스트로 받으면 최신 모델이 JSON 앞에 분석 산문을 길게 쓰다가
        #   max_tokens 에서 잘려 JSON 을 못 내놓는 사고가 남. 도구를 강제하면
        #   스키마에 맞는 값이 그대로 오므로 파싱 실패 자체가 사라진다.
        "tools": [EXTRACT_TOOL],
        "tool_choice": {"type": "tool", "name": EXTRACT_TOOL["name"]},
    }

    # temperature 는 일부 최신 모델(Sonnet 5 등)에서 deprecated → 400 에러.
    # 지원하는 모델에서는 결정적 추출을 위해 0 을 쓰고, 거부하면 빼고 재시도.
    resp = None
    if model not in _NO_TEMPERATURE_MODELS:
        try:
            resp = client.messages.create(temperature=0, **kwargs)
        except Exception as e:
            if "temperature" in str(e).lower():
                _NO_TEMPERATURE_MODELS.add(model)  # 다음부터는 바로 생략
            else:
                raise
    if resp is None:
        resp = client.messages.create(**kwargs)

    # 도구 호출 결과(dict) 를 그대로 사용 — JSON 파싱 불필요.
    data = None
    for block in resp.content:
        if getattr(block, "type", None) == "tool_use":
            data = block.input
            break

    if data is None:
        # 도구를 안 쓴 경우(이론상 없음) 텍스트에서 JSON 추출 시도
        text = "".join(
            b.text for b in resp.content if getattr(b, "type", None) == "text"
        )
        if getattr(resp, "stop_reason", None) == "max_tokens":
            raise ValueError(
                f"Claude 응답이 max_tokens 에서 잘렸습니다 (model={model}).\n{text[:400]}"
            )
        data = _parse_json_object(text)

    def _s(key: str) -> str:
        """None/숫자 등이 와도 안전하게 문자열로."""
        v = data.get(key)
        return str(v).strip() if v is not None else ""

    return DocMeta(
        title=_s("title"),
        sender=_s("sender"),
        receiver=_s("receiver"),
        doc_no=_s("doc_no"),
        enforce_date=_s("date"),
        summary=_s("summary"),
        source_file=str(pdf_path),
        notes=[f"Claude API ({model})"],
    )


def _merge_with_filename(meta: DocMeta, p: Path) -> DocMeta:
    """LLM이 비워둔 필드를 파일명 패턴으로 보충."""
    from pdf_parser import parse_filename
    fname = parse_filename(p.stem)
    if not meta.title:
        meta.title = fname.title
    if not meta.sender:
        meta.sender = fname.sender
    if not meta.receiver:
        meta.receiver = fname.receiver
    if not meta.doc_no:
        meta.doc_no = fname.doc_no
    if not meta.enforce_date:
        meta.enforce_date = fname.enforce_date
    return meta


def extract_smart(pdf_path: str | Path, prefer: str = "claude") -> DocMeta:
    """
    추출 흐름 (v1.0.7 단순화):
        1) Claude API           - 인터넷+키 필요, 1~3초
        2) 파일명/본문 정규식    - Claude 실패 시 fallback

    prefer: "claude" (기본) | "regex"
    """
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(p)

    from pdf_parser import extract as regex_extract

    # ── Tier 1: Claude API ──
    if prefer == "claude":
        try:
            meta = extract_with_claude(p)
            if meta:
                return _merge_with_filename(meta, p)
            claude_err = "API 키 미설정"
        except Exception as e:
            claude_err = str(e)
    else:
        claude_err = "skipped"

    # ── Tier 2: 정규식 fallback ──
    meta = regex_extract(p)
    meta.notes.append(f"Claude 미사용 ({claude_err}) — 정규식 fallback")
    return meta


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python ai_extract.py <pdf>")
        sys.exit(1)
    m = extract_smart(sys.argv[1])
    out = Path(__file__).parent / "_ai_meta.txt"
    out.write_text(str(m), encoding="utf-8")
    print(f"Wrote: {out}")
