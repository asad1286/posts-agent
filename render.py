"""
Zephanto "Daily Tech Talk" images in the same series style as Day 1-11
(background, logo, slogan, eyebrow, question, zephanto.com):

  portrait   1080 x 1350 (4:5)   Instagram, Facebook, LinkedIn
  landscape  1600 x 900  (16:9)  X

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

NAVY = (7, 11, 26)
WHITE = (255, 255, 255)
LIGHT_GREY = (187, 199, 218)
BLUE = (22, 139, 255)
CYAN = (22, 199, 232)
CORAL = (255, 107, 107)
PANEL_FILL = (10, 23, 47, 225)
CYAN_OUTLINE = (22, 199, 232, 205)
CORAL_OUTLINE = (*CORAL, 150)
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


def tracked_width(draw, text, face, tracking):
    return sum(draw.textlength(c, font=face) for c in text) + tracking * (len(text) - 1)


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


def paste_logo(image, x, y, width):
    logo = Image.open(LOGO).convert("RGBA")
    bbox = logo.getchannel("A").getbbox()
    if bbox:
        logo = logo.crop(bbox)
    logo = logo.resize((width, round(logo.height * width / logo.width)), Image.Resampling.LANCZOS)
    image.alpha_composite(logo, (x, y))


def slogan(image, x, y, size, centre_width=None):
    draw = ImageDraw.Draw(image)
    face = font(size, "medium")
    white, grad = "Your Vision, ", "Engineered By Zephanto"
    white_w = draw.textlength(white, font=face)
    if centre_width is not None:
        x = round((centre_width - white_w - draw.textlength(grad, font=face)) / 2)
    draw.text((x, y), white, font=face, fill=WHITE, anchor="lt")
    gradient_text(image, (round(x + white_w), y), grad, face)


def portrait_base(base_alpha):
    """Background, logo, slogan and website for the 4:5 image."""
    picture = ImageOps.fit(Image.open(BACKGROUND).convert("RGBA"), (1080, 1350), method=Image.Resampling.LANCZOS)
    image = veil(picture, 1.2, base_alpha)
    paste_logo(image, (1080 - 405) // 2, 80, 405)
    slogan(image, 0, 145, 26, centre_width=1080)
    ImageDraw.Draw(image).text((540, 1272), "zephanto.com", font=font(20, "medium"), fill=WHITE, anchor="mm")
    return image


def landscape_base(base_alpha):
    """Background, logo and slogan for the 16:9 image (logo top-left, as on the old X posts)."""
    picture = ImageOps.fit(Image.open(BACKGROUND).convert("RGBA"), (1600, 900), method=Image.Resampling.LANCZOS,
                           centering=(0.5, 0.42))
    image = veil(picture, 0.75, base_alpha)
    paste_logo(image, 90, 64, 300)
    slogan(image, 90, 116, 20)
    ImageDraw.Draw(image).text((1510, 818), "zephanto.com", font=font(20, "medium"), fill=WHITE, anchor="rt")
    return image


def eyebrow(image, x, y, text, size=20, centre_width=None):
    draw = ImageDraw.Draw(image)
    face = font(size, "semi")
    if centre_width is not None:
        x = round((centre_width - tracked_width(draw, text, face, 4)) / 2)
    tracked_text(draw, (x, y), text, face, (*CYAN, 255), 4)


def question_centred(image, y, text):
    """Question + "Tell us in the comments", centred (portrait)."""
    draw = ImageDraw.Draw(image)
    size, lines = fit(draw, text, "semi", 900, 32, 24, 2)
    for line in lines:
        draw.text((540, y), line, font=font(size, "semi"), fill=WHITE, anchor="mt")
        y += round(size * 1.3)
    face = font(25, "medium")
    gradient_text(image, (round(540 - draw.textlength(PROMPT, font=face) / 2), y + 14), PROMPT, face)


def question_left(image, x, y, text):
    """Question + "Tell us in the comments", left-aligned on one line (landscape)."""
    draw = ImageDraw.Draw(image)
    size = 30
    while size > 20 and draw.textlength(text, font=font(size, "semi")) > 1150:
        size -= 1
    draw.text((x, y), text, font=font(size, "semi"), fill=WHITE, anchor="lt")
    gradient_text(image, (x, y + size + 16), PROMPT, font(23, "medium"))


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


# ── shared blocks ───────────────────────────────────────────────────────────

CARD_TOP = 34 + 46 + 28      # pill offset + pill + gap before the text


def statement_card(image, box, label, lines, size, is_fact):
    """A MYTH (grey, crossed out) or FACT (white, bold) card with its text already wrapped."""
    x0, y0 = box[0], box[1]
    shadowed_box(image, box, CYAN_OUTLINE if is_fact else CORAL_OUTLINE)
    y = pill(image, x0 + 36, y0 + 34, label, is_fact) + 28
    draw = ImageDraw.Draw(image)
    face = font(size, "bold" if is_fact else "medium")
    for line in lines:
        draw.text((x0 + 36, y), line, font=face, fill=WHITE if is_fact else LIGHT_GREY, anchor="lt")
        if not is_fact:
            mid = y + size * 0.55
            draw.line((x0 + 36, mid, x0 + 36 + draw.textlength(line, font=face), mid), fill=(*CORAL, 230), width=4)
        y += round(size * 1.28)


def fit_in_card(draw, text, weight, box, start, smallest):
    """Largest size at which the text fits inside a fixed card."""
    width, height = box[2] - box[0] - 72, box[3] - box[1] - CARD_TOP - 30
    for size in range(start, smallest - 1, -2):
        lines = wrap(draw, text, font(size, weight), width)
        if len(lines) * round(size * 1.28) <= height:
            return size, lines
    return smallest, wrap(draw, text, font(smallest, weight), width)


def list_height(draw, items, size, width):
    lines = sum(len(wrap(draw, item, font(size, "regular"), width)) for item in items)
    return 30 + 46 + 26 + round(lines * size * 1.25 + len(items) * size * 0.45) + 20


def list_panel(image, box, label, items, is_after, size):
    x0, y0, x1 = box[0], box[1], box[2]
    shadowed_box(image, box, CYAN_OUTLINE if is_after else CORAL_OUTLINE)
    y = pill(image, x0 + 34, y0 + 30, label, is_after) + 26
    draw = ImageDraw.Draw(image)
    face = font(size, "medium" if is_after else "regular")
    dot = CYAN if is_after else CORAL
    for item in items:
        draw.ellipse((x0 + 40, y + size * 0.35, x0 + 52, y + size * 0.35 + 12), fill=dot)
        for line in wrap(draw, item, face, x1 - x0 - 110):
            draw.text((x0 + 72, y), line, font=face, fill=WHITE if is_after else LIGHT_GREY, anchor="lt")
            y += round(size * 1.25)
        y += round(size * 0.45)


def two_line_headline(image, x, y, top, bottom, start, max_width):
    draw = ImageDraw.Draw(image)
    size = start
    while size > 30 and max(draw.textlength(t, font=font(size, "bold")) for t in (top, bottom)) > max_width:
        size -= 2
    draw.text((x, y), top, font=font(size, "bold"), fill=WHITE, anchor="lt")
    gradient_text(image, (x, y + round(size * 1.15)), bottom, font(size, "bold"))


def quote_lines(draw, post, width, start, max_height):
    """Size and lines for lead + punch, plus the height they need (bar included)."""
    for size in range(start, 37, -2):
        face = font(size, "bold")
        lines = [(l, False) for l in wrap(draw, post["lead"], face, width)]
        lines += [(l, True) for l in wrap(draw, post["punch"], face, width)]
        needed = 44 + len(lines) * round(size * 1.18) + 2 * round(size * 0.35)
        if needed <= max_height:
            break
    return size, lines, needed


def draw_quote(image, x, y, width, size, lines, centre):
    """A short gradient bar (instead of a quote mark), the lead in white, the punch in gradient."""
    bar = horizontal_gradient((96, 8), (*BLUE, 255), (*CYAN, 255))
    mask = Image.new("L", (96, 8), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, 95, 7), radius=4, fill=255)
    image.paste(bar, (x + (width - 96) // 2 if centre else x, y), mask)
    draw = ImageDraw.Draw(image)
    face = font(size, "bold")
    y += 44
    previous = False
    for line, is_punch in lines:
        if is_punch and not previous:
            y += round(size * 0.35)
        previous = is_punch
        lx = round(x + (width - draw.textlength(line, font=face)) / 2) if centre else x
        if is_punch:
            gradient_text(image, (lx, y), line, face)
        else:
            draw.text((lx, y), line, font=face, fill=WHITE, anchor="lt")
        y += round(size * 1.18)


# ── portrait (Instagram, Facebook, LinkedIn) ────────────────────────────────

def myth_fact_portrait(post, tag):
    image = portrait_base(110)
    eyebrow(image, 80, 250, f"{tag}  |  MYTH VS FACT")
    draw = ImageDraw.Draw(image)
    m_size, m_lines = fit(draw, post["myth"], "medium", 848, 46, 32, 2)
    f_size, f_lines = fit(draw, post["fact"], "bold", 848, 46, 32, 5)
    myth_h = max(220, CARD_TOP + round(len(m_lines) * m_size * 1.28) + 40)
    fact_h = max(300, CARD_TOP + round(len(f_lines) * f_size * 1.28) + 48)
    statement_card(image, (80, 300, 1000, 300 + myth_h), "MYTH", m_lines, m_size, False)
    fact_top = 300 + myth_h + 40
    statement_card(image, (80, fact_top, 1000, fact_top + fact_h), "FACT", f_lines, f_size, True)
    question_centred(image, max(1050, fact_top + fact_h + 80), post["question"])
    return image


def before_after_portrait(post, tag):
    image = portrait_base(115)
    eyebrow(image, 80, 240, f"{tag}  |  BEFORE / AFTER")
    two_line_headline(image, 80, 282, post["headline_top"], post["headline_bottom"], 50, 920)
    draw = ImageDraw.Draw(image)
    # both panels share one text size: the largest at which both fit in 640 px
    for size in range(30, 21, -1):
        heights = [list_height(draw, items, size, 810) for items in (post["before"], post["after"])]
        if sum(heights) <= 640:
            break
    top = 420
    for (label, items, is_after), h in zip((("BEFORE", post["before"], False), ("AFTER", post["after"], True)), heights):
        list_panel(image, (80, top, 1000, top + h), label, items, is_after, size)
        top += h + 30
    question_centred(image, max(1140, top + 20), post["question"])
    return image


def quote_portrait(post, tag):
    image = portrait_base(125)
    eyebrow(image, 0, 262, tag, centre_width=1080)
    draw = ImageDraw.Draw(image)
    size, lines, needed = quote_lines(draw, post, 780, 66, 590)
    top = 330 + max(0, (700 - needed - 110) // 2)
    panel = (80, top, 1000, top + needed + 110)
    shadowed_box(image, panel, (22, 199, 232, 170), radius=32)
    draw_quote(image, 150, top + 56, 780, size, lines, centre=True)
    question_centred(image, max(panel[3] + 60, 1090), post["question"])
    return image


# ── landscape (X) ───────────────────────────────────────────────────────────

def myth_fact_landscape(post, tag):
    image = landscape_base(125)
    eyebrow(image, 90, 200, f"{tag}  |  MYTH VS FACT", size=19)
    draw = ImageDraw.Draw(image)
    myth_box, fact_box = (90, 250, 760, 690), (820, 250, 1510, 690)
    m_size, m_lines = fit_in_card(draw, post["myth"], "medium", myth_box, 44, 28)
    f_size, f_lines = fit_in_card(draw, post["fact"], "bold", fact_box, 40, 26)
    statement_card(image, myth_box, "MYTH", m_lines, m_size, False)
    statement_card(image, fact_box, "FACT", f_lines, f_size, True)
    question_left(image, 90, 740, post["question"])
    return image


def before_after_landscape(post, tag):
    image = landscape_base(130)
    eyebrow(image, 90, 196, f"{tag}  |  BEFORE / AFTER", size=19)
    two_line_headline(image, 90, 232, post["headline_top"], post["headline_bottom"], 44, 1420)
    draw = ImageDraw.Draw(image)
    for size in range(27, 19, -1):
        if max(list_height(draw, items, size, 580) for items in (post["before"], post["after"])) <= 360:
            break
    list_panel(image, (90, 360, 780, 720), "BEFORE", post["before"], False, size)
    list_panel(image, (820, 360, 1510, 720), "AFTER", post["after"], True, size)
    question_left(image, 90, 760, post["question"])
    return image


def quote_landscape(post, tag):
    image = landscape_base(130)
    eyebrow(image, 90, 200, tag, size=19)
    draw = ImageDraw.Draw(image)
    size, lines, _ = quote_lines(draw, post, 1000, 62, 470)
    draw_quote(image, 90, 250, 1000, size, lines, centre=False)
    question_left(image, 90, 760, post["question"])
    return image


FORMATS = {
    "myth_fact": (myth_fact_portrait, myth_fact_landscape),
    "before_after": (before_after_portrait, before_after_landscape),
    "quote": (quote_portrait, quote_landscape),
}


def render(post, out_path, landscape=False):
    tag = f"DAILY TECH TALK #{post['day']:02d}"
    image = FORMATS[post["format"]][1 if landscape else 0](post, tag)
    image.convert("RGB").save(out_path, "JPEG", quality=92)
