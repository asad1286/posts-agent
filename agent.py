"""
Daily Post Agent: roz Gemini se Zephanto ki "Daily Tech Talk" post likhwata hai,
usi series design mein image banata hai (render.py), aur Instagram + LinkedIn
pe post karta hai.
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

import render

# =====================================================================
#  ⚙️  SETTINGS — sirf ye hissa apni marzi se badlo
# =====================================================================

BRAND_NAME = "Zephanto"

SERVICES = (
    "custom software, web and mobile apps, CRM setup and migration (HubSpot, "
    "GoHighLevel, Zoho), workflow automation (Zapier, n8n, Make), AI integrations, "
    "cloud and DevOps, UI/UX design, technical consulting"
)

AUDIENCE = "small and growing business owners, founders, agencies and operations teams"

TONE = "friendly, practical and confident, without hype"

# Formats ek ke baad ek chalte hain: #12 myth_fact, #13 before_after, #14 quote, #15 myth_fact ...
FORMAT_ROTATION = ["myth_fact", "before_after", "quote"]

# history.json mein koi numbered post na ho to series yahan se shuru hogi
START_DAY = 12

# Jo posts pehle hath se ban chuki hain (Day 1-11): inhein dobara nahi likhna
PAST_POSTS = [
    "5 tasks your business should stop doing by hand",
    "5 signs your CRM is leaking leads",
    "GoodHire case study: a hiring platform for HR teams",
    "5 signs your website is losing you customers",
    "5 ways AI can save your team hours every week",
    "5 questions to ask before hiring a software company",
    "5 things to prepare before you build an app",
    "5 ways to cut your cloud bill this month",
    "Myth vs Fact: automation is only for big companies",
    "Before / After: same lead, two very different outcomes (manual vs automated follow-up)",
    "Quote: the best software doesn't add steps, it removes the ones nobody wanted to do",
]

POST_TO_INSTAGRAM = True
POST_TO_LINKEDIN = True

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


def next_day(history):
    days = [h["day"] for h in history if isinstance(h.get("day"), int)]
    return max(days) + 1 if days else START_DAY


# What goes on the image for each format, with the limits that keep it inside its box
FORMAT_FIELDS = {
    "myth_fact": {
        "myth": "the common belief, one short sentence, max 60 characters",
        "fact": "the truth, specific and practical, max 130 characters",
    },
    "before_after": {
        "headline_top": "short first line, max 22 characters, e.g. \"Same lead.\"",
        "headline_bottom": "second line, max 32 characters, e.g. \"Two very different outcomes.\"",
        "before": "list of exactly 4 short steps (max 40 characters each) showing the slow, manual way",
        "after": "list of exactly 4 short steps (max 40 characters each) showing the same thing done well",
    },
    "quote": {
        "lead": "first half of one strong original statement, max 45 characters",
        "punch": "second half that lands the point, max 55 characters",
    },
}

LIMITS = {"myth": 75, "fact": 160, "headline_top": 28, "headline_bottom": 40,
          "lead": 55, "punch": 65, "question": 60}

STYLE_EXAMPLES = """Example (Daily Tech Talk #09, myth_fact):

instagram_caption:
Daily Tech Talk #09: Myth vs Fact

Myth: Automation is only for big companies. ❌
Fact: Even a 3-person team can automate lead replies, follow-ups and reminders, often with tools it already pays for. ✅

Most small businesses already have a CRM, a form and an email tool. Connecting them properly is usually the cheapest "new hire" they'll ever make.

Which task would you automate first? Tell us in the comments 👇

#Zephanto #DailyTechTalk #MythVsFact #Automation #SmallBusiness #CRM #Zapier #n8n #Productivity

linkedin_post:
"Automation is for big companies with big budgets."

I hear this a lot, and it's rarely true.

Most small teams already pay for the pieces: a CRM, a website form, an email tool, a calendar. What's missing is the connection between them.

Connect those four, and a 3-person team can:
→ reply to every new lead within seconds,
→ follow up automatically until someone answers,
→ remind customers about bookings without anyone typing a message.

No new software. Just the tools you have, finally working together.

Which task would you automate first?

#Automation #SmallBusiness #CRM #Operations

Example (Daily Tech Talk #11, quote):

instagram_caption:
Daily Tech Talk #11 💡

The best software doesn't add steps. It removes the ones nobody wanted to do.

Every tool we build starts with one question: what is your team doing by hand, every day, that they wish they didn't have to?

Copying data. Chasing replies. Building the same report every Monday. That's where good software starts.

Agree or disagree? Tell us in the comments 👇

#Zephanto #DailyTechTalk #SoftwareDevelopment #Automation #Productivity #ProductDesign #SmallBusiness #TechQuotes"""


def summary(post):
    """One line describing the post, for history.json and the image's alt text."""
    if post["format"] == "myth_fact":
        return f"Myth vs Fact: {post['myth']}"
    if post["format"] == "before_after":
        return f"Before / After: {post['headline_top']} {post['headline_bottom']}"
    return f"Quote: {post['lead']} {post['punch']}"


def build_prompt(history, day, fmt):
    done = PAST_POSTS + [h["headline"] for h in history[-40:]]
    done_text = "\n".join(f"- {h}" for h in done)
    fields = FORMAT_FIELDS[fmt]
    field_text = "\n".join(f'- "{k}": {v}' for k, v in fields.items())
    keys = ", ".join(f'"{k}": ...' for k in [*fields, "question", "instagram_caption", "linkedin_post"])
    today = datetime.now(timezone.utc).strftime("%A, %d %B %Y")
    return f"""You write the daily social media post for {BRAND_NAME}, a software company.
Services: {SERVICES}.
Audience: {AUDIENCE}.
Tone: {TONE}. Language: English.
Today is {today}. This is "Daily Tech Talk #{day:02d}", format: {fmt}.

Pick ONE fresh topic connected to one of the services. It must not repeat or closely
rephrase any earlier post:
{done_text}

Text for the image:
{field_text}
- "question": a short question for the audience under the image, max 50 characters

Captions:
- "instagram_caption": first line starts with "Daily Tech Talk #{day:02d}". Then the post's idea in
  short lines, 2-3 sentences of practical context, the question followed by
  "Tell us in the comments 👇", a blank line, and 8-10 hashtags starting with
  #Zephanto #DailyTechTalk. Max 4 emojis. Only if the topic is about CRM or
  automation, you may add one line before the hashtags:
  "Free 30-minute CRM & automation audit, link in bio."
- "linkedin_post": no "Daily Tech Talk" label. A strong first line, short paragraphs,
  one concrete takeaway, written by a practitioner, ends with the question, then 3-4
  hashtags. 100-200 words. Max 1 emoji. No links.

Rules:
- Specific and useful, not generic. No clickbait.
- No made-up statistics, percentages, quotes, client names or claims about real people.
- No numbered "5 tips" lists: that series is over.
- Never mention the company's city or country.

{STYLE_EXAMPLES}

Return ONLY valid JSON with exactly these keys:
{{{keys}}}
"""


def parse_post_json(text, fmt):
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start:end + 1])
    post = {}
    for key in [*FORMAT_FIELDS[fmt], "question", "instagram_caption", "linkedin_post"]:
        value = data.get(key)
        if key in ("before", "after"):
            if not isinstance(value, list) or not 3 <= len(value) <= 4:
                raise ValueError(f"'{key}' mein 3-4 items chahiye")
            value = [str(v).strip() for v in value]
            if any(not v or len(v) > 50 for v in value):
                raise ValueError(f"'{key}' ke items khaali ya bohat lambe hain")
        else:
            value = str(value or "").strip()
            if not value:
                raise ValueError(f"'{key}' khaali hai")
            if len(value) > LIMITS.get(key, 10_000):
                raise ValueError(f"'{key}' bohat lamba hai ({len(value)} characters)")
        post[key] = value
    return post


def ask_gemini(prompt, fmt):
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
                post = parse_post_json(text, fmt)
                print(f"✍️  Post likhi gayi ({model})")
                return post
            except (requests.RequestException, KeyError, ValueError) as e:
                last_error = f"{model}: {e}"
                time.sleep(5)
    sys.exit(f"❌ Gemini se post nahi bani. Aakhri error: {last_error}")


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
        # Make passes the text to LinkedIn as-is, so it needs the same escaping
        r = requests.post(hook, timeout=60, json={
            "text": linkedin_text(text),
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
    history = load_history()
    day = next_day(history)
    fmt = FORMAT_ROTATION[(day - START_DAY) % len(FORMAT_ROTATION)]
    post = ask_gemini(build_prompt(history, day, fmt), fmt)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    post.update(day=day, format=fmt, date=stamp, image=f"images/{stamp}.jpg")
    post["headline"] = summary(post)
    render.render(post, ROOT / post["image"])
    POST_FILE.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"DAILY TECH TALK #{day:02d} ({fmt}): {post['headline']}\n" + "-" * 60)
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
                          f"Zephanto Daily Tech Talk #{post['day']:02d}. {post['headline']}")
        except SystemExit as e:
            errors.append(str(e)); print(e)

    history = load_history()
    history.append({"date": post["date"], "day": post["day"], "format": post["format"],
                    "headline": post["headline"], "ok": not errors})
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
