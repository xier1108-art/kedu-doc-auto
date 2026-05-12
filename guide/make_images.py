"""Anthropic API 키 발급 가이드용 모형 이미지 생성.
실제 화면을 시뮬레이션한 mockup 에 화살표/박스로 클릭 위치 표시."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).parent / "images"
OUT_DIR.mkdir(exist_ok=True)

W, H = 1000, 600
BG = (245, 247, 250)
TXT = (40, 50, 60)
LIGHT_TXT = (130, 140, 150)
ANTHROPIC_ORANGE = (203, 117, 87)
LINE = (200, 205, 215)
ARROW_RED = (220, 40, 60)
BOX_RED = (220, 40, 60)
INPUT_BG = (255, 255, 255)


def font(size=14, bold=False):
    try:
        return ImageFont.truetype("malgunbd.ttf" if bold else "malgun.ttf", size)
    except Exception:
        return ImageFont.load_default()


def base_img(title: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)
    # 브라우저 chrome
    d.rectangle([(0, 0), (W, 50)], fill=(60, 65, 75))
    d.ellipse([(15, 18), (29, 32)], fill=(255, 100, 100))
    d.ellipse([(35, 18), (49, 32)], fill=(255, 200, 80))
    d.ellipse([(55, 18), (69, 32)], fill=(80, 200, 100))
    d.rounded_rectangle([(120, 14), (W - 20, 36)], radius=12, fill=(95, 105, 120))
    d.text((135, 18), f"🔒  {title}", fill=(220, 225, 230), font=font(13))
    return img, d


def draw_arrow(d, x1, y1, x2, y2, color=ARROW_RED, width=4):
    """직선 + 화살촉."""
    d.line([(x1, y1), (x2, y2)], fill=color, width=width)
    # 화살촉
    import math
    angle = math.atan2(y2 - y1, x2 - x1)
    L = 18
    ah = 8
    p1 = (x2, y2)
    p2 = (x2 - L * math.cos(angle - 0.35), y2 - L * math.sin(angle - 0.35))
    p3 = (x2 - L * math.cos(angle + 0.35), y2 - L * math.sin(angle + 0.35))
    d.polygon([p1, p2, p3], fill=color)


def draw_box(d, x1, y1, x2, y2, color=BOX_RED, width=3, label=None, label_pos="top"):
    d.rectangle([(x1, y1), (x2, y2)], outline=color, width=width)
    if label:
        lx = x1
        ly = y1 - 28 if label_pos == "top" else y2 + 6
        # 라벨 배경
        bbox = d.textbbox((lx, ly), label, font=font(13, bold=True))
        d.rectangle([(bbox[0] - 4, bbox[1] - 2), (bbox[2] + 6, bbox[3] + 2)],
                    fill=(255, 255, 255), outline=color, width=2)
        d.text((lx, ly), label, fill=color, font=font(13, bold=True))


def header(d, title: str, subtitle: str = ""):
    d.text((30, 70), title, fill=TXT, font=font(22, bold=True))
    if subtitle:
        d.text((30, 105), subtitle, fill=LIGHT_TXT, font=font(13))


# ──────────────────────────────────────────────────────────────────
# 1) Anthropic Console 메인 — 가입/로그인
# ──────────────────────────────────────────────────────────────────
img, d = base_img("console.anthropic.com")
header(d, "Anthropic Console", "Claude API 사용을 위한 가입/로그인 페이지")

# 로고 영역
d.text((W // 2 - 80, 170), "✦ ANTHROPIC", fill=ANTHROPIC_ORANGE, font=font(28, bold=True))
d.text((W // 2 - 50, 215), "Welcome", fill=TXT, font=font(18))

# Google 로그인 버튼
d.rounded_rectangle([(W // 2 - 180, 270), (W // 2 + 180, 320)], radius=8,
                    outline=LINE, width=2, fill=INPUT_BG)
d.text((W // 2 - 100, 285), "Continue with Google", fill=TXT, font=font(14, bold=True))

# OR 구분
d.line([(W // 2 - 180, 350), (W // 2 - 30, 350)], fill=LINE, width=1)
d.text((W // 2 - 8, 343), "OR", fill=LIGHT_TXT, font=font(12))
d.line([(W // 2 + 30, 350), (W // 2 + 180, 350)], fill=LINE, width=1)

# 이메일 입력
d.text((W // 2 - 180, 375), "Email", fill=TXT, font=font(12))
d.rounded_rectangle([(W // 2 - 180, 395), (W // 2 + 180, 435)], radius=6,
                    outline=LINE, width=2, fill=INPUT_BG)
d.text((W // 2 - 165, 408), "name@example.com", fill=LIGHT_TXT, font=font(13))

# 계속 버튼
d.rounded_rectangle([(W // 2 - 180, 450), (W // 2 + 180, 495)], radius=8,
                    fill=ANTHROPIC_ORANGE)
d.text((W // 2 - 30, 463), "Continue", fill=(255, 255, 255), font=font(14, bold=True))

# 화살표 + 박스
draw_box(d, W // 2 - 190, 260, W // 2 + 190, 330, label="1️⃣ Google 계정으로 가입 (가장 빠름)")
draw_box(d, W // 2 - 190, 385, W // 2 + 190, 505, label="② 또는 이메일로 가입", label_pos="bottom")
draw_arrow(d, 250, 295, W // 2 - 200, 295)

img.save(OUT_DIR / "01_signup.png")
print("01_signup.png")

# ──────────────────────────────────────────────────────────────────
# 2) 결제 - Billing 메뉴
# ──────────────────────────────────────────────────────────────────
img, d = base_img("console.anthropic.com/settings/billing")
header(d, "결제(Billing) 설정", "API 사용 전 결제 수단 등록 + 크레딧 충전 필요")

# 사이드바
d.rectangle([(0, 150), (220, H)], fill=(252, 253, 254))
d.line([(220, 150), (220, H)], fill=LINE, width=1)
menu = ["Dashboard", "API Keys", "Usage", "Plans & Billing",
        "Workspaces", "Members", "Logs"]
for i, name in enumerate(menu):
    y = 175 + i * 38
    is_active = name == "Plans & Billing"
    if is_active:
        d.rectangle([(0, y - 4), (220, y + 28)], fill=(255, 240, 230))
        d.rectangle([(0, y - 4), (4, y + 28)], fill=ANTHROPIC_ORANGE)
    d.text((24, y + 4), name,
           fill=ANTHROPIC_ORANGE if is_active else TXT, font=font(13, bold=is_active))

# 메인 컨텐츠
d.text((250, 170), "Plans & Billing", fill=TXT, font=font(20, bold=True))

# 카드 등록 영역
d.rounded_rectangle([(250, 230), (970, 350)], radius=8, outline=LINE, width=1, fill=INPUT_BG)
d.text((270, 250), "Payment Method", fill=TXT, font=font(14, bold=True))
d.text((270, 280), "결제 수단이 등록되지 않았습니다.", fill=LIGHT_TXT, font=font(12))
d.rounded_rectangle([(270, 305), (440, 335)], radius=6, fill=(50, 110, 230))
d.text((290, 313), "+ Add payment method", fill=(255, 255, 255), font=font(12, bold=True))

# 크레딧 충전 영역
d.rounded_rectangle([(250, 380), (970, 530)], radius=8, outline=LINE, width=1, fill=INPUT_BG)
d.text((270, 400), "Credits", fill=TXT, font=font(14, bold=True))
d.text((270, 430), "Balance: $0.00", fill=TXT, font=font(13))
d.text((270, 455), "Auto-reload 또는 1회 충전 가능 (최소 $5 권장)", fill=LIGHT_TXT, font=font(12))
d.rounded_rectangle([(270, 485), (430, 515)], radius=6, fill=(50, 110, 230))
d.text((290, 493), "+ Buy credits", fill=(255, 255, 255), font=font(12, bold=True))

# 화살표
draw_box(d, 5, 290, 215, 322, label="① 사이드바 [Plans & Billing] 클릭")
draw_box(d, 260, 290, 460, 350, label="② 카드 등록", label_pos="bottom")
draw_box(d, 260, 470, 450, 525, label="③ 크레딧 충전 (최소 $5 권장)", label_pos="bottom")

img.save(OUT_DIR / "02_billing.png")
print("02_billing.png")

# ──────────────────────────────────────────────────────────────────
# 3) API Keys 페이지 — Create Key
# ──────────────────────────────────────────────────────────────────
img, d = base_img("console.anthropic.com/settings/keys")
header(d, "API Keys", "API 키 발급 페이지 — [Create Key] 클릭")

# 사이드바
d.rectangle([(0, 150), (220, H)], fill=(252, 253, 254))
d.line([(220, 150), (220, H)], fill=LINE, width=1)
for i, name in enumerate(menu):
    y = 175 + i * 38
    is_active = name == "API Keys"
    if is_active:
        d.rectangle([(0, y - 4), (220, y + 28)], fill=(255, 240, 230))
        d.rectangle([(0, y - 4), (4, y + 28)], fill=ANTHROPIC_ORANGE)
    d.text((24, y + 4), name,
           fill=ANTHROPIC_ORANGE if is_active else TXT, font=font(13, bold=is_active))

d.text((250, 170), "API Keys", fill=TXT, font=font(20, bold=True))

# Create Key 버튼
d.rounded_rectangle([(800, 170), (970, 205)], radius=6, fill=(50, 110, 230))
d.text((830, 180), "+ Create Key", fill=(255, 255, 255), font=font(13, bold=True))

# 키 목록 (빈 상태)
d.rounded_rectangle([(250, 230), (970, 530)], radius=8, outline=LINE, width=1, fill=INPUT_BG)
d.text((W // 2 - 100, 350), "아직 API 키가 없습니다", fill=LIGHT_TXT, font=font(14))
d.text((W // 2 - 110, 380), "[+ Create Key] 버튼으로 만드세요", fill=LIGHT_TXT, font=font(12))

draw_box(d, 5, 290, 215, 322, label="① 사이드바 [API Keys] 클릭")
draw_box(d, 795, 165, 975, 210, label="② [+ Create Key] 버튼 클릭", label_pos="bottom")
draw_arrow(d, 700, 187, 795, 187)

img.save(OUT_DIR / "03_apikeys.png")
print("03_apikeys.png")

# ──────────────────────────────────────────────────────────────────
# 4) Create Key 다이얼로그
# ──────────────────────────────────────────────────────────────────
img, d = base_img("console.anthropic.com/settings/keys (모달)")
# 배경 어둡게
d.rectangle([(0, 50), (W, H)], fill=(20, 25, 35))
# 헤더 텍스트
d.text((30, 70), "API Key 생성", fill=(220, 225, 230), font=font(22, bold=True))
d.text((30, 105), "이름을 정하고 [Create] 클릭", fill=(180, 190, 200), font=font(13))

# 모달
mx1, my1, mx2, my2 = 200, 170, 800, 480
d.rounded_rectangle([(mx1, my1), (mx2, my2)], radius=12, fill=INPUT_BG)
d.text((mx1 + 30, my1 + 25), "Create API Key", fill=TXT, font=font(18, bold=True))

# Name 입력
d.text((mx1 + 30, my1 + 80), "Name", fill=TXT, font=font(12, bold=True))
d.rounded_rectangle([(mx1 + 30, my1 + 105), (mx2 - 30, my1 + 145)], radius=6,
                    outline=LINE, width=2, fill=INPUT_BG)
d.text((mx1 + 45, my1 + 117), "kedu-doc-auto", fill=TXT, font=font(13))

# Workspace 선택
d.text((mx1 + 30, my1 + 165), "Workspace", fill=TXT, font=font(12, bold=True))
d.rounded_rectangle([(mx1 + 30, my1 + 190), (mx2 - 30, my1 + 230)], radius=6,
                    outline=LINE, width=2, fill=(252, 252, 254))
d.text((mx1 + 45, my1 + 202), "Default Workspace", fill=TXT, font=font(13))
d.text((mx2 - 55, my1 + 205), "▼", fill=LIGHT_TXT, font=font(10))

# 버튼
d.rounded_rectangle([(mx2 - 200, my2 - 55), (mx2 - 120, my2 - 25)], radius=6,
                    outline=LINE, width=1, fill=INPUT_BG)
d.text((mx2 - 180, my2 - 47), "Cancel", fill=TXT, font=font(12))
d.rounded_rectangle([(mx2 - 110, my2 - 55), (mx2 - 30, my2 - 25)], radius=6,
                    fill=ANTHROPIC_ORANGE)
d.text((mx2 - 85, my2 - 47), "Create", fill=(255, 255, 255), font=font(12, bold=True))

draw_box(d, mx1 + 25, my1 + 100, mx2 - 25, my1 + 150,
         label="① 이름 입력 (예: 'kedu-doc-auto')")
draw_box(d, mx2 - 115, my2 - 60, mx2 - 25, my2 - 20,
         label="② [Create] 클릭", label_pos="bottom")
draw_arrow(d, mx2 + 20, my2 - 40, mx2 - 10, my2 - 40)

img.save(OUT_DIR / "04_createkey.png")
print("04_createkey.png")

# ──────────────────────────────────────────────────────────────────
# 5) 키 복사 화면 (한 번만 표시됨)
# ──────────────────────────────────────────────────────────────────
img, d = base_img("console.anthropic.com/settings/keys")
header(d, "API 키 생성 완료 — 반드시 복사하세요!",
       "⚠ 이 키는 한 번만 표시됩니다. 닫으면 다시 못 봅니다.")

# 강조 배경
d.rectangle([(30, 145), (970, 165)], fill=(255, 230, 200))
d.text((40, 145), "⚠ 보안 — 이 키는 본인만 보관. 메신저/메일 등에 공유 금지.",
       fill=(180, 80, 30), font=font(12, bold=True))

# 모달
mx1, my1, mx2, my2 = 100, 195, 900, 470
d.rounded_rectangle([(mx1, my1), (mx2, my2)], radius=12,
                    outline=ANTHROPIC_ORANGE, width=3, fill=INPUT_BG)
d.text((mx1 + 30, my1 + 25), "✓ Your API key", fill=(30, 130, 80), font=font(18, bold=True))
d.text((mx1 + 30, my1 + 60), "다음 키를 복사하고 안전한 곳에 보관하세요.",
       fill=TXT, font=font(13))

# 키 박스
d.rounded_rectangle([(mx1 + 30, my1 + 110), (mx2 - 130, my1 + 155)], radius=6,
                    fill=(250, 251, 253), outline=LINE, width=2)
d.text((mx1 + 45, my1 + 122),
       "sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX...",
       fill=TXT, font=font(13, bold=True))

# 복사 버튼
d.rounded_rectangle([(mx2 - 115, my1 + 110), (mx2 - 30, my1 + 155)], radius=6,
                    fill=(50, 110, 230))
d.text((mx2 - 95, my1 + 122), "📋 Copy", fill=(255, 255, 255), font=font(13, bold=True))

# Done 버튼
d.rounded_rectangle([(mx2 - 110, my2 - 55), (mx2 - 30, my2 - 25)], radius=6,
                    fill=ANTHROPIC_ORANGE)
d.text((mx2 - 90, my2 - 47), "Done", fill=(255, 255, 255), font=font(12, bold=True))

draw_box(d, mx1 + 25, my1 + 105, mx2 - 25, my1 + 160,
         label="🔑 키 (sk-ant-... 로 시작)")
draw_box(d, mx2 - 120, my1 + 105, mx2 - 25, my1 + 160,
         label="① [Copy] 클릭", label_pos="bottom")
draw_arrow(d, 50, my1 + 130, mx1 + 25, my1 + 130)

img.save(OUT_DIR / "05_copykey.png")
print("05_copykey.png")


# ──────────────────────────────────────────────────────────────────
# 6) 비전자문서등록 자동입력 GUI - [⚙ 설정] 화면
# ──────────────────────────────────────────────────────────────────
img = Image.new("RGB", (W, H), BG)
d = ImageDraw.Draw(img)
# 윈도우 헤더
d.rectangle([(0, 0), (W, 35)], fill=(60, 110, 200))
d.text((15, 8), "Claude API 설정 — 비전자문서등록 자동입력", fill=(255, 255, 255), font=font(14, bold=True))
# 닫기 버튼
d.rectangle([(W - 50, 0), (W - 15, 35)], fill=(60, 110, 200))
d.text((W - 38, 8), "×", fill=(255, 255, 255), font=font(20, bold=True))

# 윈도우 본체
d.rectangle([(0, 35), (W, H)], fill=(245, 247, 250))

# 섹션 1: API 키
d.text((30, 65), "Anthropic API 키", fill=TXT, font=font(16, bold=True))
d.text((30, 95), "https://console.anthropic.com/settings/keys 에서 발급",
       fill=LIGHT_TXT, font=font(12))

# 키 입력 필드
d.rounded_rectangle([(30, 130), (W - 30, 175)], radius=4,
                    outline=(60, 110, 200), width=2, fill=INPUT_BG)
d.text((45, 145), "sk-ant-api03-XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX...",
       fill=TXT, font=font(13, bold=True))

d.text((30, 185), "키는 %USERPROFILE%\\.kedu_anthropic_key 에 저장됩니다.",
       fill=LIGHT_TXT, font=font(11))

# 구분선
d.line([(30, 220), (W - 30, 220)], fill=LINE, width=1)

# 섹션 2: 모델 선택
d.text((30, 240), "Claude 모델", fill=TXT, font=font(16, bold=True))
d.text((30, 270), "사용 가능한 모델 — 새로고침 시 본인 키로 사용 가능한 최신 목록",
       fill=LIGHT_TXT, font=font(11))

# 콤보박스
d.rounded_rectangle([(30, 305), (W - 180, 345)], radius=4,
                    outline=LINE, width=1, fill=INPUT_BG)
d.text((45, 318), "Claude Sonnet 4.5  (claude-sonnet-4-5-20250929)  — 균형",
       fill=TXT, font=font(13))
d.text((W - 200, 320), "▼", fill=LIGHT_TXT, font=font(10))

# 새로고침 버튼
d.rounded_rectangle([(W - 165, 305), (W - 30, 345)], radius=4,
                    outline=LINE, width=1, fill=INPUT_BG)
d.text((W - 145, 318), "🔄 새로고침", fill=TXT, font=font(13))

# tier 안내
d.text((30, 365), "모델별 특성:", fill=TXT, font=font(13, bold=True))
d.text((50, 395), "• Opus: 최고 정확도 / 비싼 (~50원/PDF)", fill=LIGHT_TXT, font=font(11))
d.text((50, 415), "• Sonnet: 균형 (~10원/PDF) ★ 기본값", fill=LIGHT_TXT, font=font(11))
d.text((50, 435), "• Haiku: 저렴 / 빠른 (~1원/PDF)", fill=LIGHT_TXT, font=font(11))

# 저장/취소 버튼
d.rounded_rectangle([(W // 2 - 110, 510), (W // 2 - 10, 550)], radius=6,
                    fill=ANTHROPIC_ORANGE)
d.text((W // 2 - 75, 522), "저장", fill=(255, 255, 255), font=font(14, bold=True))
d.rounded_rectangle([(W // 2 + 10, 510), (W // 2 + 110, 550)], radius=6,
                    outline=LINE, width=2, fill=INPUT_BG)
d.text((W // 2 + 45, 522), "취소", fill=TXT, font=font(14))

# 주석
draw_box(d, 25, 125, W - 25, 180, label="① 복사한 키 (sk-ant-...) 붙여넣기")
draw_box(d, W // 2 - 115, 505, W // 2 - 5, 555, label="② [저장] 클릭", label_pos="bottom")
draw_arrow(d, W // 2 - 200, 580, W // 2 - 80, 555)

img.save(OUT_DIR / "06_gui_settings.png")
print("06_gui_settings.png")

print("\n총 6장 생성 완료")
