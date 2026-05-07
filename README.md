# K-에듀파인 비전자문서등록 자동 입력기

PDF 한 개를 드래그하면 OCR + 의미 분석으로 비전자문서등록 폼을 자동으로 채워주는 도구.
**오프라인(로컬 LLM) / 온라인(Claude API) 둘 다 지원.**

---

## 핵심 동작

```
PDF (스캔/디지털 무관)
    │
    ├─ 추출 엔진 (4-tier fallback, 산업 표준 OCR + LLM 분리 구조)
    │     ① ☁ Claude API (Haiku 4.5)              - 최고 품질, 인터넷+키, ~2초
    │     ② 📷 OCR(EasyOCR) + 텍스트 LLM(gemma3)    - 빠른 오프라인, ~30~50초
    │     ③ 👁 Vision-LLM(gemma3:4b 직접)          - 느린 오프라인, ~150초
    │     ④ 📝 파일명 정규식 (LLM 없음)             - 즉시
    │
    └─ 비전자문서등록 폼 (WXSClient.exe 의 임베디드 IE)
          ① 사용자 기본값 7개 자동 적용
          ② LLM 이 추출한 메타데이터 자동 입력
          ③ [저장] 버튼은 사람이 직접 클릭
```

### 왜 OCR + LLM 을 분리하나?
산업 표준 패턴 (Google Document AI, AWS Textract 모두 동일):
- 전문 OCR 모델은 **글자 인식만** 학습 → 한국어 인식이 작은 vision-LLM 보다 훨씬 정확
- 텍스트 LLM 은 비전 인코더 우회 → 같은 모델이라도 **5-10배 빠름**
- 모듈화 → OCR 또는 LLM 만 교체 가능

### 측정값 (i5-13500 CPU 기준)

| 방식 | 시간 | 발신/수신 구분 | 글자 오인식 |
|---|---|---|---|
| Vision-LLM 단일 (`gemma3:4b` 이미지) | 152초 | ❌ 헷갈림 | 다수 |
| **OCR+LLM 분리 (EasyOCR + gemma3:4b)** | **41초** | ✅ 정확 | 거의 없음 |
| Claude API (참고) | ~2초 | ✅ 정확 | 없음 |

---

## 사용 방법 (3가지)

### ① 바탕화면 바로가기 (가장 편함)
바탕화면의 **[비전자문서등록]** 더블클릭 → GUI 실행 → PDF 드래그앤드롭

### ② 우클릭 [보내기] 메뉴
파일 탐색기에서 PDF 우클릭 → **보내기 → 비전자문서등록**
GUI 가 떠서 자동으로 해당 PDF 처리.

### ③ 명령줄
```powershell
python auto_fill.py "C:\Path\to\문서.pdf"
python auto_fill.py --dry-run "..."   # 폼에 안 넣고 추출만
```

---

## 설치 (이미 완료된 항목)

```powershell
cd C:\Users\USER\Desktop\PROJECT\문서접수

# Python 패키지
pip install --user pywinauto comtypes pdfplumber pypdf anthropic tkinterdnd2 pywin32 pymupdf pillow

# Ollama (오프라인 LLM 데몬) — 이미 설치됨, 부팅 시 자동 실행
ollama pull gemma3:4b   # 3.3GB, 멀티모달

# 바탕화면/SendTo 바로가기
python install_shortcuts.py
```

---

## 추출 엔진 비교

| 엔진 | 정확도 | 속도 | 인터넷 | 비용 |
|---|---|---|---|---|
| ☁ **Claude API (Haiku 4.5)** | ★★★★★ | 1~3초 | 필요 | PDF 1건당 0.5~2원 |
| 📷 **OCR(EasyOCR) + 텍스트 LLM** | ★★★★ | 30~50초 | 불필요 | 무료 |
| 👁 **Vision-LLM (gemma3:4b)** | ★★★ | 2~3분 | 불필요 | 무료 |
| 📝 **정규식만** | ★★ | 즉시 | 불필요 | 무료 |

**추천**: GUI 의 [추출 엔진]을 **자동** 으로 두면 위 순서대로 시도.

### 오프라인 스택 사양
- **OCR 엔진**: EasyOCR (`ko`+`en`), CPU 추론, PyTorch 기반, ~150MB 모델
- **텍스트 LLM**: Gemma 3 4B (`gemma3:4b`, 3.3GB, Q4 양자화)
- **요구 RAM**: 6 GB+
- **요구 디스크**: 4 GB+
- **확인된 속도** (i5-13500): 디지털 PDF ~33초 / 스캔 PDF ~50초
- **위치**: `%USERPROFILE%\.ollama\models\` + EasyOCR 캐시

---

## Claude API 키 (선택, 권장)

오프라인 LLM 만 써도 동작하지만 정확도/속도 차이가 큽니다. 키 등록 권장:

### 발급
https://console.anthropic.com/settings/keys

### 등록 (택1)
1. **GUI 의 [⚙ 설정]** 버튼 (가장 쉬움)
2. **환경변수**: `setx ANTHROPIC_API_KEY "sk-ant-..."` 후 재시작
3. **파일**: `%USERPROFILE%\.kedu_anthropic_key` 에 키 한 줄

---

## 자동 적용되는 기본값

[auto_fill.py](auto_fill.py) 의 `DEFAULTS` 상수에서 변경 가능합니다.

| 항목 | 값 | 폼 ID |
|---|---|---|
| 등록구분 | 접수 | `R_SENDRECEIVE` → `SENDRECEIVE2` |
| 대국민공개여부 | 비공개 | `PUBLICATION` → `PUBLICATION2` |
| 공개제한근거 | 5호 | `ho5` 체크 |
| 직원열람범위 | 기관 | `readngScope` → `readngScope1` |
| 직원열람제한 | 설정안함 | `SECURITY` → `SECURITY0` |
| 접수자 | 김상현 | `DRAFTERNAME` |
| 업무담당자 | 김상현 | `LASTSIGNERNAME` |

## PDF 에서 LLM 이 추출하는 항목

| 항목 | 폼 ID |
|---|---|
| 제목 | `TITLE` |
| 발신기관 | `DRFTINSTTNM` / `DSPTCHNMCN` / `ORGDRAFTDEPTNAME` |
| 수신자 | `RECEIVERNAME` |
| 문서번호 | `DOCREGNO` |
| 시행일자 | `ENFORCEDATE` |
| 본문 요지 | `docOutline` |

---

## 파일 구성

| 파일 | 역할 |
|---|---|
| `gui.py` | **메인 GUI** (드래그앤드롭, 백엔드 선택, 키 설정) |
| `auto_fill.py` | 명령줄 진입점, 기본값 + PDF 적용 로직 |
| `ai_extract.py` | **4-tier fallback 라우터** (Claude → OCR+LLM → Vision → 정규식) |
| `ocr_extract.py` | **EasyOCR + 텍스트 LLM 분리 파이프라인** ⭐ 추천 오프라인 |
| `local_extract.py` | Vision-LLM 직접 (Gemma 3 멀티모달) |
| `pdf_parser.py` | 파일명 패턴 매칭 + 본문 정규식 |
| `wxs_form.py` | 비전자문서등록 폼 DOM 조작 (IHTMLDocument) |
| `install_shortcuts.py` | 바탕화면/SendTo 바로가기 생성 |

---

## 주의사항

1. **저장 버튼은 자동으로 누르지 않습니다.** 자동 입력 후 화면에서 검토 → [저장] 클릭.
2. **과제카드명** (`untkID`) 은 K-에듀파인 자체 팝업 검색이 필요한 항목입니다. 폼이 이미 셋업된 경우 그대로 유지됩니다.
3. **접수자 ID** (hidden) 는 처음 한 번 🔍 아이콘으로 사용자 검색이 필요할 수 있습니다.
4. **첨부파일**은 별도로 [파일추가] 버튼을 클릭해서 업로드해야 합니다 (보안상 JS 로 파일 첨부 불가).
5. **오프라인 LLM 정확도**: gemma3:4b 의 한국어 OCR 은 ~80% 수준. 인명/회사명에서 글자 오인식 가능. 결과는 항상 사람이 검토 필요.

## 트러블슈팅

| 증상 | 해결 |
|---|---|
| `WXSClient.exe 프로세스를 찾을 수 없습니다` | 비전자문서등록 창 열고 다시 실행 |
| GUI 의 "💻 오프라인: 비활성" | `ollama serve` 가 실행 중인지 확인. 작업 표시줄 알림 영역에서 재시작 가능 |
| 오프라인 추출이 너무 느림 | 정상. CPU 추론은 PDF 1건 1~3분. 더 빠르게 하려면 Claude API 키 등록 |
| OCR 결과 글자 오류 | gemma3:4b 의 한계. 결과 표를 보고 직접 수정하거나 Claude API 사용 |
| 한글 깨짐 | `set PYTHONIOENCODING=utf-8` 후 실행 (콘솔에서만) |
