from app.services.ai.openai_client import get_client
from app.core.config import settings

SYSTEM = """You are writing a short teaser summary for a curated Christian newsletter that highlights important articles about technology, culture, and faith.
Your goal is to briefly explain:
• what the article is about
• what trend, issue, or development it explores
• why the topic matters for faith, ethics, culture, or society

Do NOT give a full explanation.
The summary should create curiosity and encourage readers to click the original article.

Write the teaser so that it feels like a thoughtful introduction to the article, not a full analysis."""

def build_prompt(audience: str, tone: str, title: str, url: str, content: str) -> str:
    return f"""Audience: {audience}
Tone: {tone}

Task: Write a brief, engaging summary of the article provided.
Follow this general flow:

Length
• 80-100 words
• One paragraph only
• 2–4 sentences

Sentence 1 — Introduce the topic or situation
Sentence 2 — Explain what the article explores or argues
Sentence 3 — Highlight a tension, implication, or ethical question
Sentence 4 (optional) — Suggest the broader significance

Editorial Perspective
Whenever possible, frame the topic through themes such as:
• technology and faith
• AI and ministry
• digital culture
• ethics of technology
• cultural change affecting Christianity

Avoid
• preaching or moralizing
• stating what Christians “should” do
• excessive detail or statistics
• quoting the article
• using first-person language
• multiple paragraphs

Also generate a short headline for the teaser.

Headline guidelines:
• 5–10 words
• Clear and intriguing
• Often highlights a tension, question, or surprising idea
• Avoid clickbait

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
