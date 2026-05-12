"""사용자 스크린샷에 추가 마크업 (4.png 만 보강).

원본 스크린샷: C:\\Users\\USER\\Desktop\\PROJECT\\문서접수\\클로드api\\
출력:        C:\\Users\\USER\\Desktop\\PROJECT\\문서접수\\guide\\real\\
"""
import math
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SRC = Path(r"C:\Users\USER\Desktop\PROJECT\문서접수\클로드api")
OUT = Path(__file__).parent / "real"
OUT.mkdir(exist_ok=True)

RED = (220, 40, 60)


def font(size, bold=False):
    try:
        return ImageFont.truetype("malgunbd.ttf" if bold else "malgun.ttf", size)
    except Exception:
        return ImageFont.load_default()


def draw_box(d, x1, y1, x2, y2, color=RED, width=4, label=None, label_below=False):
    d.rectangle([(x1, y1), (x2, y2)], outline=color, width=width)
    if label:
        f = font(16, bold=True)
        lx = x1
        ly = y2 + 10 if label_below else y1 - 30
        bbox = d.textbbox((lx, ly), label, font=f)
        # 흰 배경
        d.rectangle([(bbox[0] - 6, bbox[1] - 4), (bbox[2] + 8, bbox[3] + 4)],
                    fill=(255, 255, 255), outline=color, width=2)
        d.text((lx, ly), label, fill=color, font=f)


def draw_arrow(d, x1, y1, x2, y2, color=RED, width=5):
    d.line([(x1, y1), (x2, y2)], fill=color, width=width)
    angle = math.atan2(y2 - y1, x2 - x1)
    L, ah = 22, 10
    p1 = (x2, y2)
    p2 = (x2 - L * math.cos(angle - 0.4), y2 - L * math.sin(angle - 0.4))
    p3 = (x2 - L * math.cos(angle + 0.4), y2 - L * math.sin(angle + 0.4))
    d.polygon([p1, p2, p3], fill=color)


# 1, 2, 3, 5, 6, 7.png — 사용자가 이미 빨간 박스 그렸으므로 그대로 복사
for i in (1, 2, 3, 5, 6, 7):
    src = SRC / f"{i}.png"
    dst = OUT / f"{i}.png"
    shutil.copy2(src, dst)
    print(f"  copy: {i}.png")

# 4.png — 사이드바 [API 키] + 우상단 [+ 키 생성] 박스 추가 필요
img = Image.open(SRC / "4.png").convert("RGB")
d = ImageDraw.Draw(img)
W, H = img.size
print(f"  4.png size: {W}x{H}")

# 좌측 사이드바 'API 키' 메뉴는 사용자가 이미 흰 박스로 표시함.
# 빨간 박스 강조 추가 + 화살표
# 박스 위치(흰 박스): (0, 360, 240, 400) 추정
draw_box(d, 5, 358, 240, 400, label="① 사이드바 [API 키]")
# 우상단 [+ 키 생성] 버튼 위치 — 우측 상단
# 버튼 위치 추정: 우상단 (1755, 13, 1855, 50) 정도
# 실제 W=1870 정도, 우상단 25, height 50
draw_box(d, W - 175, 7, W - 5, 50, label="② [+ 키 생성] 클릭", label_below=True)

img.save(OUT / "4.png")
print("  4.png annotated")

print(f"\n총 7장 → {OUT}")
