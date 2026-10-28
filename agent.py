"""
Daily Post Agent: roz Gemini se post likhwata hai, image banata hai,
aur Instagram + LinkedIn pe post karta hai.
  python agent.py generate   -> post + image banata hai
  python agent.py publish    -> Instagram aur LinkedIn pe post karta hai
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

# =====================================================================
#  ⚙️  SETTINGS — sirf ye hissa apni marzi se badlo
# =====================================================================

BRAND_NAME = "Zephanto"

TOPIC = (
    "Technology, AI tools aur software development ke practical tips, "
    "jo small businesses aur young developers ke kaam aayen"
)

AUDIENCE = "Pakistan aur duniya bhar ke young professionals, founders aur developers"

# "English", "Roman Urdu", ya "English with a little Roman Urdu"
LANGUAGE = "English"

TONE = "friendly, helpful, confident — bina zyada hype ke"

POST_TO_INSTAGRAM = True
POST_TO_LINKEDIN = True

IMAGE_BG_COLOR = "#0B0B0F"
IMAGE_ACCENT_COLOR = "#7C5CFF"
IMAGE_TEXT_COLOR = "#FFFFFF"

GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]

INSTAGRAM_API_VERSION = "v26.0"
LINKEDIN_API_VERSION = "202609"

# =====================================================================

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"
HISTORY_FILE = ROOT / "history.json"
POST_FILE = OUTPUT_DIR / "post.json"
DRY_RUN = os.getenv("DRY_RUN") == "1"


def env(name):
    value = os.getenv(name, "").strip()
    if not value:
        sys.exit(f"❌ '{name}' set nahi hai. GitHub Secrets mein add karo.")
    return value


def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def build_prompt(history):
    recent = [h["headline"] for h in history[-30:]]
    recent_text = "\n".join(f"- {h}" for h in recent) or "- (none yet)"
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    return f"""You are the social media writer for the brand "{BRAND_NAME}".
Today is {today}.

Write ONE new post idea for today and adapt it for Instagram and LinkedIn.

Topic area: {TOPIC}
Audience: {AUDIENCE}
Language: {LANGUAGE}
Tone: {TONE}

Do NOT repeat or closely rephrase any of these recent headlines:
{recent_text}

Rules:
- Give real, specific, useful value (a tip, mini-framework, mistake to avoid, or quick how-to).
- No made-up statistics, quotes, or claims about real people or companies.
- No clickbait. Max 3 emojis on Instagram, max 2 on LinkedIn.
- "headline" goes on the image: max 8 words, punchy.
- "subline" also goes on the image: max 14 words.
- "instagram_caption": 80-150 words, hook first line, short lines, end with a question, then a blank line and 5-8 hashtags.
- "linkedin_post": 120-220 words, strong first line, short paragraphs, practical takeaway, end with a question, 2-3 hashtags at the end.

Return ONLY valid JSON with exactly these keys:
{{"headline": "...", "subline": "...", "instagram_caption": "...", "linkedin_post": "..."}}
"""


def parse_post_json(text):
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start:end + 1])
    for key in ("headline", "subline", "instagram_caption", "linkedin_post"):
        if not str(data.get(key, "")).strip():
            raise ValueError(f"'{key}' khaali hai")
        data[key] = str(data[key]).strip()
    return data


def ask_gemini(prompt):
    api_key = env("GEMINI_API_KEY")
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.9, "responseMimeType": "application/json"},
    }
    last_error = None
    for model in GEMINI_MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(3):
            try:
                r = requests.post(url, json=body, timeout=90,
                                  headers={"x-goog-api-key": api_key})
                if r.status_code == 404:
                    last_error = f"{model}: model nahi mila"
                    break
                if r.status_code in (429, 500, 503):
                    last_error = f"{model}: {r.status_code} {r.text[:200]}"
                    time.sleep(10 * (attempt + 1))
                    continue
                r.raise_for_status()
                text = r.json()["candidates"][0]["content"]["parts"][0]["text"]
                post = parse_post_json(text)
                print(f"✍️  Post likhi gayi ({model})")
                return post
            except (requests.RequestException, KeyError, ValueError) as e:
                last_error = f"{model}: {e}"
                time.sleep(5)
    sys.exit(f"❌ Gemini se post nahi bani. Aakhri error: {last_error}")


FONTS_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              "/System/Library/Fonts/Supplemental/Arial Bold.ttf"]
FONTS_REG = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
             "/System/Library/Fonts/Supplemental/Arial.ttf"]


def load_font(candidates, size):
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def wrap(draw, text, font, max_width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def make_image(headline, subline, out_path):
    W, H, pad = 1080, 1350, 96
    img = Image.new("RGB", (W, H), IMAGE_BG_COLOR)
    d = ImageDraw.Draw(img)
    d.rectangle([pad, pad, pad + 120, pad + 14], fill=IMAGE_ACCENT_COLOR)
    d.text((pad, pad + 44), BRAND_NAME.upper(), font=load_font(FONTS_BOLD, 40),
           fill=IMAGE_ACCENT_COLOR)

    max_w = W - 2 * pad
    for size in range(112, 47, -4):
        h_font = load_font(FONTS_BOLD, size)
        h_lines = wrap(d, headline, h_font, max_w)
        if len(h_lines) <= 5:
            break
    line_h = int(size * 1.15)
    s_font = load_font(FONTS_REG, 44)
    s_lines = wrap(d, subline, s_font, max_w)[:4]

    y = max(pad + 180, (H - (len(h_lines) * line_h + 60 + len(s_lines) * 60)) // 2)
    for ln in h_lines:
        d.text((pad, y), ln, font=h_font, fill=IMAGE_TEXT_COLOR)
        y += line_h
    y += 60
    for ln in s_lines:
        d.text((pad, y), ln, font=s_font, fill="#B8B8C8")
        y += 60

    d.line([pad, H - pad - 60, W - pad, H - pad - 60], fill="#2A2A35", width=2)
    d.text((pad, H - pad - 30), "Save this for later  →",
           font=load_font(FONTS_REG, 32), fill="#8A8A9A")
    img.save(out_path, "JPEG", quality=92)


def post_instagram(image_url, caption):
    token, ig_id = env("INSTAGRAM_ACCESS_TOKEN"), env("INSTAGRAM_USER_ID")
    base = f"https://graph.instagram.com/{INSTAGRAM_API_VERSION}"
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(f"{base}/{ig_id}/media", headers=headers, timeout=60,
                      data={"image_url": image_url, "caption": caption})
    if not r.ok:
        sys.exit(f"❌ Instagram container error: {r.status_code} {r.text}")
    container_id = r.json()["id"]

    for _ in range(20):
        s = requests.get(f"{base}/{container_id}", headers=headers, timeout=30,
                         params={"fields": "status_code,status"})
        status = s.json().get("status_code")
        if status == "FINISHED":
            break
        if status == "ERROR":
            sys.exit(f"❌ Instagram ne image reject ki: {s.text}")
        time.sleep(6)

    r = requests.post(f"{base}/{ig_id}/media_publish", headers=headers, timeout=60,
                      data={"creation_id": container_id})
    if not r.ok:
        sys.exit(f"❌ Instagram publish error: {r.status_code} {r.text}")
    print(f"📸 Instagram pe post ho gayi (id {r.json().get('id')})")


def linkedin_text(text):
    for ch in "\\|{}@[]()<>#*_~":
        text = text.replace(ch, "\\" + ch)
    return re.sub(r"\\#([A-Za-z0-9_\\]+)",
                  lambda m: "{hashtag|\\#|" + m.group(1).replace("\\_", "_") + "}", text)


def post_linkedin(image_path, text, alt_text):
    # --- LinkedIn PAGE via Make.com (used when MAKE_WEBHOOK_URL is set) ---
    hook = os.getenv("MAKE_WEBHOOK_URL", "").strip()
    if hook:
        repo = env("GITHUB_REPOSITORY")
        branch = os.getenv("GITHUB_REF_NAME", "main")
        rel = Path(image_path).relative_to(ROOT).as_posix()
        r = requests.post(hook, timeout=60, json={
            "text": text,
            "image_url": f"https://raw.githubusercontent.com/{repo}/{branch}/{rel}",
            "alt_text": alt_text,
        })
        if not r.ok:
            sys.exit(f"❌ Make webhook error: {r.status_code} {r.text}")
        print("💼 LinkedIn Page ke liye Make ko bhej diya")
        return
    # --- else: LinkedIn API. Company page if LINKEDIN_ORG_URN is set
    # (token needs w_organization_social), otherwise the personal profile ---
    token = env("LINKEDIN_ACCESS_TOKEN")
    author = os.getenv("LINKEDIN_ORG_URN", "").strip() or env("LINKEDIN_PERSON_URN")
    headers = {
        "Authorization": f"Bearer {token}",
        "LinkedIn-Version": LINKEDIN_API_VERSION,
        "X-Restli-Protocol-Version": "2.0.0",
        "Content-Type": "application/json",
    }
    r = requests.post("https://api.linkedin.com/rest/images?action=initializeUpload",
                      headers=headers, timeout=60,
                      json={"initializeUploadRequest": {"owner": author}})
    if r.status_code == 401:
        sys.exit("❌ LinkedIn token expire ho gaya. linkedin_token.py se naya token banao.")
    if not r.ok:
        sys.exit(f"❌ LinkedIn image init error: {r.status_code} {r.text}")
    value = r.json()["value"]
    with open(image_path, "rb") as f:
        up = requests.put(value["uploadUrl"], data=f, timeout=120,
                          headers={"Authorization": f"Bearer {token}"})
    if not up.ok:
        sys.exit(f"❌ LinkedIn image upload error: {up.status_code} {up.text}")

    time.sleep(3)
    r = requests.post("https://api.linkedin.com/rest/posts", headers=headers, timeout=60, json={
        "author": author,
        "commentary": linkedin_text(text),
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                         "thirdPartyDistributionChannels": []},
        "content": {"media": {"id": value["image"], "altText": alt_text[:4000]}},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    })
    if not r.ok:
        sys.exit(f"❌ LinkedIn post error: {r.status_code} {r.text}")
    where = "company page" if ":organization:" in author else "personal profile"
    print(f"💼 LinkedIn pe post ho gayi ({where})")


def cmd_generate():
    OUTPUT_DIR.mkdir(exist_ok=True)
    (ROOT / "images").mkdir(exist_ok=True)
    post = ask_gemini(build_prompt(load_history()))
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    post["image"], post["date"] = f"images/{stamp}.jpg", stamp
    make_image(post["headline"], post["subline"], ROOT / post["image"])
    POST_FILE.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"HEADLINE: {post['headline']}\n" + "-" * 60)
    print("INSTAGRAM:\n" + post["instagram_caption"] + "\n" + "-" * 60)
    print("LINKEDIN:\n" + post["linkedin_post"] + "\n" + "=" * 60)


def cmd_publish():
    if not POST_FILE.exists():
        sys.exit("❌ output/post.json nahi mila. Pehle 'generate' chalao.")
    post = json.loads(POST_FILE.read_text(encoding="utf-8"))
    if DRY_RUN:
        print("🧪 DRY_RUN: kuch post nahi kiya gaya.")
        return

    errors = []
    if POST_TO_INSTAGRAM:
        repo = env("GITHUB_REPOSITORY")
        branch = os.getenv("GITHUB_REF_NAME", "main")
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{post['image']}"
        try:
            post_instagram(url, post["instagram_caption"])
        except SystemExit as e:
            errors.append(str(e)); print(e)
    if POST_TO_LINKEDIN:
        try:
            post_linkedin(ROOT / post["image"], post["linkedin_post"],
                          f"{post['headline']}. {post['subline']}")
        except SystemExit as e:
            errors.append(str(e)); print(e)

    history = load_history()
    history.append({"date": post["date"], "headline": post["headline"], "ok": not errors})
    HISTORY_FILE.write_text(json.dumps(history[-200:], ensure_ascii=False, indent=2),
                            encoding="utf-8")
    if errors:
        sys.exit("⚠️ Kuch platforms pe post fail hui (upar dekho).")
    print("✅ Aaj ki post mukammal!")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "generate":
        cmd_generate()
    elif cmd == "publish":
        cmd_publish()
    else:
        sys.exit("Use: python agent.py generate | publish")
