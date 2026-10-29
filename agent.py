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
POST_TO_FACEBOOK = True
POST_TO_X = True

GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.5-flash-lite", "gemini-3.6-flash"]

INSTAGRAM_API_VERSION = "v26.0"
FACEBOOK_API_VERSION = "v26.0"
LINKEDIN_API_VERSION = "202609"

# =====================================================================

ROOT = Path(__file__).parent
OUTPUT_DIR = ROOT / "output"
HISTORY_FILE = ROOT / "history.json"
POST_FILE = OUTPUT_DIR / "post.json"
POSTS_DIR = ROOT / "posts"          # one file per day, committed: what was written and where it went
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

CAPTION_KEYS = ["question", "instagram_caption", "linkedin_post", "facebook_caption", "x_post"]

LINK = re.compile(r"https?://|www\.|\b[\w-]+\.(com|net|org|io|ai|co|pk|app|dev)\b", re.IGNORECASE)

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

facebook_caption:
Daily Tech Talk #09: Myth vs Fact

Myth: Automation is only for big companies. ❌
Fact: Even a 3-person team can automate lead replies, follow-ups and reminders, often with tools it already pays for. ✅

Which task would you automate first? 👇

#Automation #SmallBusiness #CRM #Zephanto

x_post:
Myth: automation is only for big companies.

Fact: even a 3-person team can automate lead replies, follow-ups and reminders, often with tools it already pays for.

Which task would you automate first? 👇

#Automation #SmallBusiness

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
    keys = ", ".join(f'"{k}": ...' for k in [*fields, *CAPTION_KEYS])
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
- "facebook_caption": first line starts with "Daily Tech Talk #{day:02d}". The idea in 2-5 short
  lines, the question followed by 👇, a blank line, 4-5 hashtags ending with #Zephanto.
  40-90 words. No links, web addresses or "link in bio".
- "x_post": the idea in 1-3 short lines, the question, then 2 hashtags. At most 250
  characters in total, emojis count as 2. No "Daily Tech Talk" label. Absolutely no
  links or web addresses.

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
    for key in [*FORMAT_FIELDS[fmt], *CAPTION_KEYS]:
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
    # a link costs 13x more on X, and Facebook limits link posts on new Pages
    for key in ("x_post", "facebook_caption"):
        if LINK.search(post[key]):
            raise ValueError(f"'{key}' mein link hai")
    if x_length(post["x_post"]) > 280:
        raise ValueError(f"'x_post' 280 se lamba hai ({x_length(post['x_post'])})")
    return post


def x_length(text):
    """Length as X counts it: most emoji and non-Latin characters count as 2."""
    return sum(1 if ord(c) <= 0x10FF or 0x2000 <= ord(c) <= 0x201F or 0x2032 <= ord(c) <= 0x2037 else 2
               for c in text)


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
    return r.json().get("id")


def post_facebook(image_url, caption):
    page_id, token = env("FACEBOOK_PAGE_ID"), env("FACEBOOK_PAGE_TOKEN")
    r = requests.post(f"https://graph.facebook.com/{FACEBOOK_API_VERSION}/{page_id}/photos", timeout=90,
                      data={"url": image_url, "message": caption, "access_token": token})
    if not r.ok:
        sys.exit(f"❌ Facebook post error: {r.status_code} {r.text}")
    post_id = r.json().get("post_id") or r.json().get("id")
    print(f"📘 Facebook pe post ho gayi (id {post_id})")
    return post_id


def post_x(image_path, text):
    from requests_oauthlib import OAuth1
    auth = OAuth1(env("X_API_KEY"), env("X_API_SECRET"), env("X_ACCESS_TOKEN"), env("X_ACCESS_SECRET"))

    media_ids = []
    with open(image_path, "rb") as f:
        up = requests.post("https://api.x.com/2/media/upload", auth=auth, timeout=120,
                           files={"media": (Path(image_path).name, f, "image/jpeg")},
                           data={"media_category": "tweet_image", "media_type": "image/jpeg"})
    if up.ok:
        body = up.json()
        media_id = (body.get("data") or {}).get("id") or body.get("media_id_string")
        if media_id:
            media_ids = [str(media_id)]
    if not media_ids:
        print(f"⚠️ X image upload nahi hui ({up.status_code} {up.text[:300]}). Sirf text post hogi.")

    payload = {"text": text}
    if media_ids:
        payload["media"] = {"media_ids": media_ids}
    r = requests.post("https://api.x.com/2/tweets", auth=auth, json=payload, timeout=60)
    if r.status_code == 402 or "credit" in r.text.lower():
        sys.exit(f"❌ X: credits khatam ya nahi hain. console.x.com → Billing → Credits. ({r.status_code} {r.text[:300]})")
    if r.status_code in (401, 403):
        sys.exit(f"❌ X: keys ghalat hain ya Access Token 'Read and write' nahi. ({r.status_code} {r.text[:300]})")
    if not r.ok:
        sys.exit(f"❌ X post error: {r.status_code} {r.text}")
    tweet_id = r.json()["data"]["id"]
    print(f"🐦 X pe post ho gayi (id {tweet_id})")
    return tweet_id


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
        return "make"
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
    return where


def save_day(post):
    POSTS_DIR.mkdir(exist_ok=True)
    (POSTS_DIR / f"{post['date']}.json").write_text(json.dumps(post, ensure_ascii=False, indent=2),
                                                    encoding="utf-8")


def cmd_generate():
    OUTPUT_DIR.mkdir(exist_ok=True)
    (ROOT / "images").mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    saved = POSTS_DIR / f"{stamp}.json"
    if saved.exists():
        # the workflow ran again today: reuse the same post, so no platform gets a second one
        post = json.loads(saved.read_text(encoding="utf-8"))
        print(f"♻️  Aaj ki post (#{post['day']:02d}) pehle se bani hui hai, wahi istemal hogi. "
              f"Pehle se post ho chuki: {', '.join(post.get('posted', {})) or 'kahin nahi'}")
    elif not DRY_RUN and any(h.get("date") == stamp for h in load_history()):
        # today's post went out before posts/ existed: don't make a second one
        print("✅ Aaj ki post pehle hi ho chuki hai. Agla run naya post banayega.")
        return
    else:
        history = load_history()
        day = next_day(history)
        fmt = FORMAT_ROTATION[(day - START_DAY) % len(FORMAT_ROTATION)]
        post = ask_gemini(build_prompt(history, day, fmt), fmt)
        post.update(day=day, format=fmt, date=stamp,
                    image=f"images/{stamp}.jpg", image_x=f"images/{stamp}-x.jpg", posted={})
        post["headline"] = summary(post)
        render.render(post, ROOT / post["image"])
        render.render(post, ROOT / post["image_x"], landscape=True)
        save_day(post)
    POST_FILE.write_text(json.dumps(post, ensure_ascii=False, indent=2), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"DAILY TECH TALK #{post['day']:02d} ({post['format']}): {post['headline']}\n" + "-" * 60)
    for label, key in (("INSTAGRAM", "instagram_caption"), ("LINKEDIN", "linkedin_post"),
                       ("FACEBOOK", "facebook_caption"), ("X", "x_post")):
        print(f"{label}:\n{post[key]}\n" + "-" * 60)


def cmd_publish():
    if not POST_FILE.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if any(h.get("date") == stamp for h in load_history()):
            print("✅ Aaj ki post pehle hi ho chuki hai, kuch nahi kiya.")
            return
        sys.exit("❌ output/post.json nahi mila. Pehle 'generate' chalao.")
    post = json.loads(POST_FILE.read_text(encoding="utf-8"))
    if DRY_RUN:
        print("🧪 DRY_RUN: kuch post nahi kiya gaya.")
        return

    repo = os.getenv("GITHUB_REPOSITORY", "")
    branch = os.getenv("GITHUB_REF_NAME", "main")
    raw = f"https://raw.githubusercontent.com/{repo}/{branch}/"
    posted, errors = post.setdefault("posted", {}), []

    def publish(name, enabled, secrets, send):
        if not enabled:
            return
        if name in posted:
            print(f"⏭️  {name}: aaj pehle hi post ho chuki, dobara nahi")
            return
        missing = [n for n in secrets if not os.getenv(n, "").strip()]
        if missing:
            print(f"⏭️  {name}: secrets nahi hain ({', '.join(missing)}), is liye chhor diya")
            return
        try:
            posted[name] = send() or "ok"
        except SystemExit as e:
            errors.append(str(e)); print(e)

    alt = f"Zephanto Daily Tech Talk #{post['day']:02d}. {post['headline']}"
    publish("instagram", POST_TO_INSTAGRAM, ["INSTAGRAM_ACCESS_TOKEN", "INSTAGRAM_USER_ID"],
            lambda: post_instagram(raw + post["image"], post["instagram_caption"]))
    publish("linkedin", POST_TO_LINKEDIN, [],
            lambda: post_linkedin(ROOT / post["image"], post["linkedin_post"], alt))
    publish("facebook", POST_TO_FACEBOOK, ["FACEBOOK_PAGE_ID", "FACEBOOK_PAGE_TOKEN"],
            lambda: post_facebook(raw + post["image"], post["facebook_caption"]))
    publish("x", POST_TO_X, ["X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_SECRET"],
            lambda: post_x(ROOT / post.get("image_x", post["image"]), post["x_post"]))

    save_day(post)
    history = [h for h in load_history() if not (h.get("date") == post["date"] and h.get("day") == post["day"])]
    history.append({"date": post["date"], "day": post["day"], "format": post["format"],
                    "headline": post["headline"], "posted": sorted(posted), "ok": not errors})
    HISTORY_FILE.write_text(json.dumps(history[-200:], ensure_ascii=False, indent=2), encoding="utf-8")
    if errors:
        sys.exit("⚠️ Kuch platforms pe post fail hui (upar dekho). Workflow dobara chalane se sirf yehi platforms chalenge.")
    print("✅ Aaj ki post mukammal!")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "generate":
        cmd_generate()
    elif cmd == "publish":
        cmd_publish()
    else:
        sys.exit("Use: python agent.py generate | publish")
