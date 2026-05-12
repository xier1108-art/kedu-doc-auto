# 공유 가이드

## ⚠ 공유 전 체크리스트 (절대 포함 금지)

| 파일 | 위치 | 왜 |
|---|---|---|
| `.kedu_anthropic_key` | `%USERPROFILE%\` | Anthropic API 키 (요금 청구됨) |
| `.kedu_user.json` | `%USERPROFILE%\` | 개인 사번/부서 ID |
| `.kedu_taskcard.json` | `%USERPROFILE%\` | 조직별 과제카드 ID (다를 수 있음) |
| `_*.py`, `_*.txt`, `_*.json` | 프로젝트 폴더 | 개발 임시 파일 |
| `__pycache__/` | 프로젝트 폴더 | Python 컴파일 캐시 |

→ 위 파일들은 모두 `%USERPROFILE%` 의 받는 사람 본인 PC 에 별도 저장됩니다. 프로젝트 폴더에는 들어가지 않으니 자동으로 안전.

---

## 옵션 A: ZIP 파일 공유 (가장 간단, 추천)

### 보내는 사람
```cmd
python package.py
```
→ `dist\비전자문서등록_자동입력_v날짜.zip` (~40KB) 생성됨. 메일/카카오톡/공유드라이브로 전송.

### 받는 사람
1. ZIP 압축 풀기 (예: `C:\Tools\문서접수\`)
2. 폴더 안의 **`install.bat` 더블클릭** — Python 패키지 자동 설치
3. (선택) Ollama 설치: https://ollama.com/download → `ollama pull gemma3:4b`
4. 바탕화면 [비전자문서등록] 더블클릭
5. **본인 정보 1회 캡처** (필수):
   - 비전자문서등록 폼 열기
   - 🔍 으로 본인 검색 → 접수자/업무담당자 선택
   - 🔍 으로 본인 조직의 과제카드 선택
   - GUI 의 [👤 사용자 저장] + [📌 과제카드 저장] 각 한 번씩 클릭
6. (선택) Anthropic API 키 등록 — GUI [⚙ 설정]

---

## 옵션 B: GitHub 저장소 (협업/버전 관리에 좋음)

### 최초 발행
```cmd
cd C:\Users\USER\Desktop\PROJECT\문서접수
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/<사용자>/<레포지토리>.git
git push -u origin main
```
`.gitignore` 가 자동으로 개인정보 파일을 제외합니다.

### 받는 사람
```cmd
git clone https://github.com/<사용자>/<레포지토리>.git
cd <레포지토리>
install.bat
```
이후 옵션 A 의 4~6단계 동일.

### 사설(Private) 저장소 추천
- 상사/동료에게만 공유하려면 GitHub Private 저장소 사용
- 또는 회사 GitLab/Gitea 가 있다면 그걸 사용

---

## 옵션 C: 회사 NAS / 공유 폴더

`package.bat` 로 ZIP 만든 뒤 회사 공유 드라이브에 업로드. 받는 사람은 다운로드 후 옵션 A 와 동일.

---

## 옵션 D: 단일 EXE 배포 (받는 사람이 Python/개발도구 미설치) ⭐ 추천

받는 사람의 PC 에 **Python, Node.js 등 어떤 개발 도구도 없을 때** 최선.

### 두 가지 빌드 모드 선택 가능

| 모드 | 명령 | 결과 | 첫 실행 | 두 번째 이후 | 용도 |
|---|---|---|---|---|---|
| `--onefile` (기본) | `python build.py` | EXE 단일 파일 (80MB) | 30~60초 | 5~10초 | 보내기 편함 |
| `--onedir` (빠름) | `python build.py --onedir` | 폴더 ZIP (90MB) | 1~3초 | 1~3초 | 매일 사용 |

### 보내는 사람 (개발자)
```cmd
# 단일 EXE
python build.py
→ dist\비전자문서등록.exe (~80MB)

# 또는 빠른 시작용 폴더 ZIP
python build.py --onedir
→ dist\비전자문서등록\ (폴더, ~160MB)
→ dist\비전자문서등록-fast.zip (~90MB, ZIP 압축)
```

### 받는 사람
1. EXE 다운로드 (Python 설치 불필요!)
2. Windows Defender 가 처음에 차단하면 [추가 정보] → [실행]
   (서명 안 된 EXE 라 그렇음)
3. 더블클릭 → **첫 실행은 30~60초 정도 멈춤 (정상!)**
   PyInstaller `--onefile` 이 EXE 안의 Python 런타임을 임시폴더에 풀어내는 시간.
   두 번째 실행부터는 빠름.
4. GUI 가 뜨면 K-에듀파인 비전자문서등록 폼 열고 본인 정보 1회 캡처:
   - 접수자/업무담당자/과제카드 수동 선택
   - GUI [👤 사용자 저장] + [📌 과제카드 저장]
5. (강력 권장) Anthropic API 키 등록 — GUI [⚙ 설정]

### EXE 의 한계
| 기능 | 단일 EXE | install.bat 방식 |
|---|---|---|
| Claude API (온라인 추출) | ✅ | ✅ |
| 정규식 fallback | ✅ | ✅ |
| 폼 자동입력/저장/적용 | ✅ | ✅ |
| **오프라인 LLM (Gemma)** | ❌ Ollama 별도 설치 필요 | ❌ Ollama 별도 |
| **오프라인 OCR (EasyOCR)** | ❌ ~500MB라 EXE에서 제외 | ✅ |

→ EXE 만 쓰는 사람은 **Anthropic API 키 등록 권장** (PDF 1건당 ~1원).
   오프라인 LLM 도 원하면 Ollama 설치 (https://ollama.com/download) + `ollama pull gemma3:4b`.
   EasyOCR 까지 원한다면 install.bat 방식 사용.

---

## 받는 사람 — 자주 묻는 질문

**Q. Anthropic API 키 꼭 있어야 하나요?**
A. 아니요. 키 없으면 자동으로 오프라인 LLM(Ollama gemma3:4b) 또는 정규식 fallback 사용.
   다만 정확도/속도는 Claude API 가 가장 좋음. 본인 카드로 키 발급 후 [⚙ 설정] 에 등록 권장.

**Q. 사용자/과제카드는 왜 1회 수동 선택해야 하나요?**
A. K-에듀파인 보안상 직접 ID 입력 불가. 검색 팝업으로만 선택 가능.
   1회 선택 시점의 hidden 필드들을 캡처해 두면 이후 자동 복원됩니다.

**Q. 부서가 바뀌면?**
A. GUI 의 [👤 사용자 저장] 다시 누르면 새 부서 정보로 갱신됩니다.

**Q. 다른 사람 PC에서 내 키/사용자 정보 사용되지 않나요?**
A. 안 됩니다. 모든 개인 정보는 각자 PC 의 `%USERPROFILE%` 에만 저장됨.

---

## 라이센스/책임

- 비공식 도구 (K-에듀파인 공식 API 사용 안함)
- 페이지 구조가 바뀌면 작동 안 할 수 있음
- 자동 입력 후 사용자가 [저장] 누르기 전 검토 필수
- 사용 결과에 대한 책임은 사용자 본인
