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
DEFAULT_MODEL = "claude-haiku-4-5-20251001"  # 가장 저렴 + 한글/OCR 충분


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

[A] 일반 공문 표지의 결정적 표지:
  ✓ "수신:" / "참조:" / "제목:" 라벨 (줄 단위)
  ✓ 하단 "시행 ○○(학교)제YYYY-N호(YYYY.MM.DD.)" 발송줄
  ✓ "끝." + 직인
  ✓ 상단 회사명/기관 로고
  ✓ 본문 "1. 귀 ○○의…", "2. 관련근거…", "3. 위 근거에…" 번호 단락

[B] 조달청 검사검수요청서 등 나라장터 양식의 표지:
  ✓ "검 사 검 수 요 청 서" 또는 "검사검수요청서" 큰 헤더
  ✓ "※나라장터전자문서출력물" 또는 비슷한 출처 표기
  ✓ [공공기관] / [납품업체] / [실제납품업체] 박스 구조
  ✓ "검사검수요청번호:", "계약건명:", "계약금액:", "계약번호:" 라벨
  ✓ "작성일자:", "검사요청일자:", "검수요청일자:" 라벨

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🎯 2단계: 식별된 유형에 따라 추출 규칙 적용
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

═══════ [A 유형 — 일반 공문] ═══════

[발신자] 표지 최상단 회사명/로고. 직인 옆 책임자 이름 아님.
  ❌ 본문 인용 "설계사공문 : DNB ..." 외부 공문번호 → 발신자 아님
  ❌ 본문 큰 글씨 공사명 → 발신자 아님
[제목] 표지의 "제목:" 줄. 짧고 문서 유형 (보고/회신/제출/검토서/요청 등).
  ❌ 본문 가운데 큰 글씨 공사명 → 제목 아님 (공사명일 뿐)
[문서번호] 페이지 하단 "시행" 줄 번호 (발신자 본인 번호).
  예: "시행 대성(갈현초)제2026-84호(2026.04.28.)" → "대성(갈현초)제2026-84호"
[시행일자] "시행" 줄 괄호 안 YYYY.MM.DD.
[수신자] "수신:" 줄 기관명 (직위 제거: "서부교육지원청장" → "서부교육지원청")
[요지] 본문 1~2문장(100자) 핵심. 공사명 포함 가능.

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
[요지] 빈 문자열 "" (사용자 지시).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
출력: JSON 한 객체만 (코드블록 X, 부가 설명 X)

{{
  "cover_page": 1,    // 표지가 몇 페이지인지 (1 또는 2). 없으면 0
  "doc_type": "A" 또는 "B",   // A: 공문, B: 검사검수요청서
  "title": "...",
  "sender": "...",
  "receiver": "...",
  "doc_no": "...",
  "date": "YYYY-MM-DD",
  "summary": "..."
}}

표지 식별 안 되면 cover_page=0, doc_type="?" 로 두고 나머지 빈 문자열.
참고용 파일명: {filename}
"""


# Claude API PDF 입력 제한
CLAUDE_MAX_PAGES = 5      # 어차피 표지는 1~2페이지이므로 5장이면 충분
CLAUDE_MAX_BYTES = 30 * 1024 * 1024  # 30MB


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


def extract_with_claude(pdf_path: Path, model: str = DEFAULT_MODEL) -> DocMeta | None:
    """Claude API로 PDF 메타데이터 추출. 키가 없으면 None 반환.

    PDF 가 100페이지/32MB 초과 시 자동으로 첫 5페이지로 잘라서 전송.
    """
    key = get_api_key()
    if not key:
        return None

    import anthropic
    client = anthropic.Anthropic(api_key=key)

    pdf_bytes = _truncate_pdf_if_needed(pdf_path)
    pdf_b64 = base64.standard_b64encode(pdf_bytes).decode("utf-8")
    prompt = PROMPT_TEMPLATE.format(filename=pdf_path.name)
    resp = client.messages.create(
        model=model,
        max_tokens=1024,
        messages=[{
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
    )

    text = resp.content[0].text.strip()
    # 코드블록이나 부가 텍스트가 섞여도 처음 발견되는 JSON 객체 추출
    m = re.search(r"\{[\s\S]*\}", text)
    if not m:
        raise ValueError(f"Claude 응답에서 JSON을 찾을 수 없음:\n{text}")
    data = json.loads(m.group())

    return DocMeta(
        title=data.get("title", "").strip(),
        sender=data.get("sender", "").strip(),
        receiver=data.get("receiver", "").strip(),
        doc_no=data.get("doc_no", "").strip(),
        enforce_date=data.get("date", "").strip(),
        summary=data.get("summary", "").strip(),
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


def extract_smart(pdf_path: str | Path, prefer: str = "auto") -> DocMeta:
    """
    4-tier fallback chain (속도/정확도 순):
        1) Claude API           - 최고 품질, 인터넷+키 필요, 1~3초
        2) OCR + 텍스트 LLM      - 오프라인, EasyOCR + gemma3:4b 텍스트, ~20~40초
        3) Vision-LLM           - 오프라인, gemma3:4b 이미지 직접, ~150초
        4) 파일명/본문 정규식    - LLM 없음, 즉시

    prefer: "auto" | "claude" | "ocr" | "vision" | "regex"
    """
    p = Path(pdf_path)
    if not p.exists():
        raise FileNotFoundError(p)

    from pdf_parser import extract as regex_extract

    # ── Tier 1: Claude API ──
    if prefer in ("auto", "claude"):
        try:
            meta = extract_with_claude(p)
            if meta:
                return _merge_with_filename(meta, p)
            claude_err = "API 키 미설정"
        except Exception as e:
            claude_err = str(e)
            if prefer == "claude":
                meta = regex_extract(p)
                meta.notes.append(f"Claude 실패, 정규식 fallback: {e}")
                return meta
    else:
        claude_err = "skipped"

    # ── Tier 2: OCR + 텍스트 LLM (오프라인 빠른 경로) ──
    if prefer in ("auto", "ocr"):
        try:
            from ocr_extract import extract_with_ocr_llm, is_available as ocr_available
            if ocr_available():
                meta, stats = extract_with_ocr_llm(p)
                if meta:
                    meta.notes.insert(0, f"Claude 미사용: {claude_err}")
                    return _merge_with_filename(meta, p)
                ocr_err = stats.get("error", "unknown")
            else:
                ocr_err = "Ollama 또는 EasyOCR 사용 불가"
        except Exception as e:
            ocr_err = str(e)
    else:
        ocr_err = "skipped"

    # ── Tier 3: Vision-LLM (오프라인 느린 경로) ──
    if prefer in ("auto", "vision"):
        try:
            from local_extract import extract_with_ollama, is_available, DEFAULT_MODEL
            if is_available(DEFAULT_MODEL):
                meta = extract_with_ollama(p)
                if meta:
                    meta.notes.insert(0, f"Claude/OCR 미사용: {claude_err} / {ocr_err}")
                    return _merge_with_filename(meta, p)
            vision_err = "Ollama 사용 불가"
        except Exception as e:
            vision_err = str(e)
    else:
        vision_err = "skipped"

    # ── Tier 4: 정규식 fallback ──
    meta = regex_extract(p)
    meta.notes.append(
        f"LLM 미사용 (Claude: {claude_err}, OCR+LLM: {ocr_err}, Vision: {vision_err})"
    )
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
