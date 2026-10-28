"""
Zephanto "Daily Tech Talk" image: 1080 x 1350 (4:5), same series style as
Day 1-11 (background, logo, slogan, eyebrow, question, zephanto.com).

Formats (exactly like Day 9, 10, 11):
  myth_fact     MYTH card (crossed out) + FACT card
  before_after  two-line headline + BEFORE panel + AFTER panel
  quote         one strong statement on a dark panel
Text is measured and the font shrinks until it fits, so Gemini's text
never runs outside its box.
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

BRAND = Path(__file__).parent / "brand"
BACKGROUND = BRAND / "background.jpg"
LOGO = BRAND / "logo.png"
FONTS = {
    "bold": BRAND / "fonts" / "Outfit-Bold.ttf",
    "semi": BRAND / "fonts" / "DMSans-SemiBold.ttf",
    "medium": BRAND / "fonts" / "DMSans-Medium.ttf",
    "regular": BRAND / "fonts" / "DMSans-Regular.ttf",
}

WIDTH, HEIGHT = 1080, 1350
NAVY = (7, 11, 26)
WHITE = (255, 255, 255)
LIGHT_GREY = (187, 199, 218)
BLUE = (22, 139, 255)
CYAN = (22, 199, 232)
CORAL = (255, 107, 107)
PANEL_FILL = (10, 23, 47, 225)
PROMPT = "Tell us in the comments"


def font(size, weight="regular"):
    return ImageFont.truetype(str(FONTS[weight]), size=size)


# ── drawing helpers ─────────────────────────────────────────────────────────

def horizontal_gradient(size, left, right):
    width, height = size
    strip = Image.new("RGBA", (width, 1))
    for x in range(width):
        t = x / max(1, width - 1)
        strip.putpixel((x, 0), tuple(round(left[i] + (right[i] - left[i]) * t) for i in range(4)))
    return strip.resize((width, height))


def gradient_text(image, xy, text, face):
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).text(xy, text, font=face, fill=255, anchor="lt")
    bbox = mask.getbbox()
    if bbox:
        x0, y0, x1, y1 = bbox
        fill = horizontal_gradient((x1 - x0, y1 - y0), (*BLUE, 255), (*CYAN, 255))
        image.paste(fill, (x0, y0), mask.crop(bbox))


def tracked_text(draw, xy, text, face, fill, tracking):
    x, y = xy
    for ch in text:
        draw.text((x, y), ch, font=face, fill=fill, anchor="lt")
        x += draw.textlength(ch, font=face) + tracking


def wrap(draw, text, face, width):
    lines, line = [], ""
    for word in text.split():
        trial = f"{line} {word}".strip()
        if draw.textlength(trial, font=face) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fit(draw, text, weight, width, start, smallest, max_lines):
    """Largest size (start → smallest) at which the text wraps into max_lines."""
    for size in range(start, smallest - 1, -2):
        lines = wrap(draw, text, font(size, weight), width)
        if len(lines) <= max_lines:
            return size, lines
    return smallest, wrap(draw, text, font(smallest, weight), width)


def veil(image, strength, base_alpha):
    """Darken the picture, most on the left and at the top/bottom edges, so text stays readable."""
    width, height = image.size
    image = Image.alpha_composite(image, Image.new("RGBA", image.size, (*NAVY, base_alpha)))
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for x in range(width):
        alpha = round(225 * ((1 - x / width) ** strength) + 14)
        draw.line((x, 0, x, height), fill=(*NAVY, min(alpha, 232)))
    image = Image.alpha_composite(image, layer)
    edge = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(edge)
    for y in range(height):
        top = max(0.0, 1 - y / (height * 0.23))
        bottom = max(0.0, (y - height * 0.76) / (height * 0.24))
        alpha = round(95 * top * top + 150 * bottom * bottom)
        if alpha:
            draw.line((0, y, width, y), fill=(*NAVY, min(alpha, 185)))
    return Image.alpha_composite(image, edge)


def base(base_alpha):
    """Background, logo, slogan and website: the parts every post shares."""
    picture = Image.open(BACKGROUND).convert("RGBA")
    picture = ImageOps.fit(picture, (WIDTH, HEIGHT), method=Image.Resampling.LANCZOS)
    image = veil(picture, 1.2, base_alpha)

    logo = Image.open(LOGO).convert("RGBA")
    bbox = logo.getchannel("A").getbbox()
    if bbox:
        logo = logo.crop(bbox)
    logo_w = 405
    logo = logo.resize((logo_w, round(logo.height * logo_w / logo.width)), Image.Resampling.LANCZOS)
    image.alpha_composite(logo, ((WIDTH - logo_w) // 2, 80))

    draw = ImageDraw.Draw(image)
    face = font(26, "medium")
    white, grad = "Your Vision, ", "Engineered By Zephanto"
    white_w = draw.textlength(white, font=face)
    x = round((WIDTH - white_w - draw.textlength(grad, font=face)) / 2)
    draw.text((x, 145), white, font=face, fill=WHITE, anchor="lt")
    gradient_text(image, (round(x + white_w), 145), grad, face)
    draw.text((WIDTH / 2, 1272), "zephanto.com", font=font(20, "medium"), fill=WHITE, anchor="mm")
    return image


def eyebrow(image, y, text, centre=False):
    draw = ImageDraw.Draw(image)
    face = font(20, "semi")
    x = 80
    if centre:
        width = sum(draw.textlength(c, font=face) for c in text) + 4 * (len(text) - 1)
        x = round((WIDTH - width) / 2)
    tracked_text(draw, (x, y), text, face, (*CYAN, 255), 4)


def question(image, y, text):
    draw = ImageDraw.Draw(image)
    size, lines = fit(draw, text, "semi", 900, 32, 24, 2)
    for line in lines:
        draw.text((WIDTH / 2, y), line, font=font(size, "semi"), fill=WHITE, anchor="mt")
        y += round(size * 1.3)
    face = font(25, "medium")
    gradient_text(image, (round(WIDTH / 2 - draw.textlength(PROMPT, font=face) / 2), y + 14), PROMPT, face)


def shadowed_box(image, box, outline, radius=28):
    x0, y0, x1, y1 = box
    shadow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((x0, y0 + 10, x1, y1 + 10), radius=radius, fill=(0, 0, 0, 120))
    image.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(16)))
    layer = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).rounded_rectangle(box, radius=radius, fill=PANEL_FILL, outline=outline, width=3)
    image.alpha_composite(layer)


def pill(image, x, y, label, gradient):
    """The MYTH / FACT / BEFORE / AFTER label. Returns its bottom edge."""
    draw = ImageDraw.Draw(image)
    face = font(22, "semi")
    box = (x, y, x + round(draw.textlength(label, font=face)) + 44, y + 46)
    if gradient:
        fill = horizontal_gradient((box[2] - box[0], box[3] - box[1]), (*BLUE, 255), (*CYAN, 255))
        mask = Image.new("L", fill.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, fill.width - 1, fill.height - 1), radius=23, fill=255)
        image.paste(fill, (box[0], box[1]), mask)
    else:
        draw.rounded_rectangle(box, radius=23, fill=CORAL)
    draw.text(((box[0] + box[2]) / 2, (box[1] + box[3]) / 2), label, font=face, fill=WHITE, anchor="mm")
    return box[3]


# ── formats ─────────────────────────────────────────────────────────────────

def myth_fact(post, tag):
    image = base(110)
    eyebrow(image, 250, f"{tag}  |  MYTH VS FACT")
    draw = ImageDraw.Draw(image)
    inner = 920 - 72

    m_size, m_lines = fit(draw, post["myth"], "medium", inner, 46, 32, 2)
    f_size, f_lines = fit(draw, post["fact"], "bold", inner, 46, 32, 5)
    myth_h = max(220, 34 + 46 + 28 + round(len(m_lines) * m_size * 1.28) + 40)
    fact_h = max(300, 34 + 46 + 28 + round(len(f_lines) * f_size * 1.28) + 48)

    for top, h, label, lines, size, is_fact in (
        (300, myth_h, "MYTH", m_lines, m_size, False),
        (300 + myth_h + 40, fact_h, "FACT", f_lines, f_size, True),
    ):
        shadowed_box(image, (80, top, 1000, top + h), (22, 199, 232, 200) if is_fact else (*CORAL, 150))
        y = pill(image, 116, top + 34, label, is_fact) + 28
        draw = ImageDraw.Draw(image)
        face = font(size, "bold" if is_fact else "medium")
        for line in lines:
            draw.text((116, y), line, font=face, fill=WHITE if is_fact else LIGHT_GREY, anchor="lt")
            if not is_fact:
                mid = y + size * 0.55
                draw.line((116, mid, 116 + draw.textlength(line, font=face), mid), fill=(*CORAL, 230), width=4)
            y += round(size * 1.28)

    question(image, max(1050, 300 + myth_h + 40 + fact_h + 80), post["question"])
    return image


def before_after(post, tag):
    image = base(115)
    eyebrow(image, 240, f"{tag}  |  BEFORE / AFTER")
    draw = ImageDraw.Draw(image)
    h_size = 50
    for h_size in range(50, 35, -2):
        if max(draw.textlength(t, font=font(h_size, "bold")) for t in (post["headline_top"], post["headline_bottom"])) <= 920:
            break
    draw.text((80, 282), post["headline_top"], font=font(h_size, "bold"), fill=WHITE, anchor="lt")
    gradient_text(image, (80, 282 + round(h_size * 1.15)), post["headline_bottom"], font(h_size, "bold"))

    # both panels share one text size: the largest at which both fit in 640 px
    for size in range(30, 21, -1):
        heights = []
        for items in (post["before"], post["after"]):
            lines = sum(len(wrap(draw, item, font(size, "regular"), 810)) for item in items)
            heights.append(30 + 46 + 26 + round(lines * size * 1.25 + len(items) * size * 0.45) + 20)
        if sum(heights) <= 640:
            break

    top = 420
    for (label, items, is_after), h in zip(
        (("BEFORE", post["before"], False), ("AFTER", post["after"], True)), heights
    ):
        shadowed_box(image, (80, top, 1000, top + h), (22, 199, 232, 210) if is_after else (*CORAL, 150))
        y = pill(image, 114, top + 30, label, is_after) + 26
        draw = ImageDraw.Draw(image)
        face = font(size, "medium" if is_after else "regular")
        dot = CYAN if is_after else CORAL
        for item in items:
            draw.ellipse((120, y + size * 0.35, 132, y + size * 0.35 + 12), fill=dot)
            for line in wrap(draw, item, face, 810):
                draw.text((152, y), line, font=face, fill=WHITE if is_after else LIGHT_GREY, anchor="lt")
                y += round(size * 1.25)
            y += round(size * 0.45)
        top += h + 30

    question(image, max(1140, top + 20), post["question"])
    return image


def quote(post, tag):
    image = base(125)
    eyebrow(image, 262, tag, centre=True)
    draw = ImageDraw.Draw(image)

    # the largest size at which lead + punch fit in the free space
    for size in range(66, 39, -2):
        face = font(size, "bold")
        lines = [(l, False) for l in wrap(draw, post["lead"], face, 780)]
        lines += [(l, True) for l in wrap(draw, post["punch"], face, 780)]
        needed = 44 + len(lines) * round(size * 1.18) + 2 * round(size * 0.35)
        if needed <= 590:
            break

    top = 330 + max(0, (700 - needed - 110) // 2)
    panel = (80, top, WIDTH - 80, top + needed + 110)
    shadowed_box(image, panel, (22, 199, 232, 170), radius=32)

    # a short gradient bar instead of a quote mark
    bar = horizontal_gradient((96, 8), (*BLUE, 255), (*CYAN, 255))
    mask = Image.new("L", (96, 8), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 95, 7), radius=4, fill=255)
    image.paste(bar, ((WIDTH - 96) // 2, top + 56), mask)

    draw = ImageDraw.Draw(image)
    y = top + 56 + 44
    previous = False
    for line, is_punch in lines:
        if is_punch and not previous:
            y += round(size * 0.35)
        previous = is_punch
        x = round((WIDTH - draw.textlength(line, font=face)) / 2)
        if is_punch:
            gradient_text(image, (x, y), line, face)
        else:
            draw.text((x, y), line, font=face, fill=WHITE, anchor="lt")
        y += round(size * 1.18)

    question(image, max(panel[3] + 60, 1090), post["question"])
    return image


FORMATS = {"myth_fact": myth_fact, "before_after": before_after, "quote": quote}


def render(post, out_path):
    tag = f"DAILY TECH TALK #{post['day']:02d}"
    image = FORMATS[post["format"]](post, tag)
    image.convert("RGB").save(out_path, "JPEG", quality=92)
