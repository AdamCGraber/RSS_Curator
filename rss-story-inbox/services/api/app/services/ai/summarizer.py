from app.services.ai.openai_client import get_client
from app.core.config import settings

SYSTEM = """You are an editorial assistant. Be accurate, grounded, and concise.
No hype. No fluff. If details are missing, say so plainly."""

def build_prompt(audience: str, tone: str, title: str, url: str, content: str) -> str:
    return f"""Audience: {audience}
Tone: {tone}

Task: Write a summary of the article below in under 300 words. Avoid hype.
Use this exact structure:

Executive Summary (2–4 sentences)

Key Points (bullets)

Pros (bullets)
Cons (bullets)

Implications + Practical Takeaways (bullets)

Article Title: {title}
URL: {url}

Article Content:
{content}
""".strip()

def generate_summary(audience: str, tone: str, title: str, url: str, content: str) -> str:
    client = get_client()
    prompt = build_prompt(audience, tone, title, url, content)
    resp = client.chat.completions.create(
        model=settings.openai_model,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    return resp.choices[0].message.content.strip()
