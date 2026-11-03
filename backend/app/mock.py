"""A stand-in model for local development and tests, so the app runs without API keys.

Answers are deterministic and shaped like the real ones, including some flaws
the agent has to handle: a Google headline that's too long, low scores that
trigger a rewrite, and buyers who disagree.
"""

import hashlib
import re


def _h(*parts: str) -> int:
    return int(hashlib.sha1("|".join(parts).encode()).hexdigest()[:8], 16)


def _product(messages: list[dict]) -> str:
    text = messages[-1]["content"]
    m = re.search(r'"product":\s*"([^"]+)"', text) or re.search(r"Title:\s*(.+)", text)
    if m:
        return re.split(r"[|:\-–—]", m.group(1))[0].strip()[:40] or "Acme"
    return "Acme"


def _quote(messages: list[dict]) -> str:
    text = messages[-1]["content"]
    m = re.search(r"Text:\n(.+)", text)
    return m.group(1)[:120] if m else ""


def mock_answer(task: str, messages: list[dict]) -> dict:
    name = _product(messages)
    if task == "brief":
        return {
            "product": name,
            "one_liner": f"{name} helps small teams send cold email that lands in the inbox",
            "category": "cold email tool",
            "audience": "Founders and small sales teams doing their own outbound",
            "offer": "14-day free trial, plans from $29 a month",
            "proof": ["Used by 4,000 teams", "Average 62% open rate across customers"],
            "tone": "plain, confident, practical",
            "queries": ["cold email software for small teams", "email deliverability tool for startups"],
        }
    if task == "pick":
        return {"competitors": [{"name": "Northwind", "url": "https://northwind.example.com"}]}
    if task == "market":
        return {
            "competitors": [
                {"name": "Northwind", "claim": "Scale outbound to thousands of leads a day", "target": "Sales teams of 20+", "price": "from $99 a month"},
                {"name": "Brightlane", "claim": "AI writes every cold email for you", "target": "Agencies", "price": "not shown"},
                {"name": "Clearpath", "claim": "All-in-one sales engagement platform", "target": "Mid-market revenue teams", "price": "demo only"},
            ],
            "axes": {"x": {"low": "do it yourself", "high": "done for you"}, "y": {"low": "solo", "high": "large team"}},
            "positions": {"product": {"x": 0.3, "y": 0.2}, "competitors": [{"x": 0.6, "y": 0.85}, {"x": 0.85, "y": 0.5}, {"x": 0.55, "y": 0.75}]},
            "gap": {
                "angle": "The cold email tool built for founders who send it themselves, not for sales floors",
                "why": "Everyone else leads with volume, AI writing or platform breadth for big teams",
                "evidence": _quote(messages) or "not found",
            },
        }
    if task == "panel":
        return {
            "buyers": [
                {"name": "Maya", "role": "Founder of a 6-person B2B SaaS", "cares": "Getting meetings without hiring a sales rep", "uses_today": "Gmail and a spreadsheet", "doubt": "Will this get my domain blacklisted?", "style": "skims, stops for numbers"},
                {"name": "Tomas", "role": "Agency owner running outbound for clients", "cares": "Managing many inboxes cheaply", "uses_today": "Northwind", "doubt": "Switching costs and per-seat pricing", "style": "price-first, compares tabs"},
                {"name": "Priya", "role": "First sales hire at a seed startup", "cares": "Hitting her meeting quota this quarter", "uses_today": "Clearpath trial", "doubt": "Another tool the founder won't pay for", "style": "reads the subject line only"},
                {"name": "Daniel", "role": "Ops lead, sceptical of sales tools", "cares": "Security and not annoying prospects", "uses_today": "nothing", "doubt": "Cold email is spam with better branding", "style": "sceptical, looks for proof"},
                {"name": "Lena", "role": "Freelance designer finding clients", "cares": "Something simple that doesn't feel salesy", "uses_today": "LinkedIn messages", "doubt": "Too complex and too expensive for one person", "style": "emotional, judges the tone"},
            ]
        }
    if task == "drafts":
        return {
            "meta": {"angle": "founder-led outbound", "primary": f"You're the founder and the sales team. {name} keeps your cold email out of spam so your first 100 meetings come from you.", "headline": "Cold email for founders", "cta": "Sign up"},
            "google": {"angle": "deliverability", "headlines": [f"{name} Cold Email", "Land In The Inbox, Not Spam For Real", "14-Day Free Trial"], "descriptions": ["Built for founders who send their own outbound. Warmup, sending limits and replies in one place.", "Plans from $29 a month. Used by 4,000 teams."]},
            "linkedin": {"angle": "proof", "intro": "4,000 small teams send their cold email with us, with a 62% average open rate. Built for people who do outbound themselves.", "headline": f"{name}: cold email for small teams", "cta": "Try now"},
            "hero": {"angle": "founder-led outbound", "headline": "Cold email that founders can run themselves", "subline": "Warm up your domain, send at safe limits and keep every reply in one inbox. No sales ops team needed.", "cta": "Start free trial", "proof": "Used by 4,000 teams, 62% average open rate"},
            "email1": {"angle": "problem", "subject": "Your cold email is probably in spam", "preview": "Most founder outbound never gets seen. Here's why.", "body": f"Hi,\n\nIf you send cold email yourself, a lot of it lands in spam before anyone reads it.\n\n{name} warms up your domain and keeps you under safe limits so it doesn't.\n\nThe {name} team"},
            "email2": {"angle": "proof", "subject": "62% open rate, from teams like yours", "preview": "What 4,000 small teams changed.", "body": f"Hi,\n\nTeams on {name} average a 62% open rate. Most of them are founders doing their own outbound.\n\nThe {name} team"},
            "email3": {"angle": "offer", "subject": "Your trial is waiting", "preview": "14 days free, no card needed to look around.", "body": f"Hi,\n\nTry {name} free for 14 days and send your next campaign with it.\n\nThe {name} team"},
        }
    if task == "shorten":
        return {"google": {"headlines": [f"{name[:18]} Cold Email", "Land In The Inbox", "14-Day Free Trial"]}}
    if task == "buyer":
        system = messages[0]["content"]
        who = re.search(r"You are (\w+)", system)
        buyer = who.group(1) if who else "x"
        pieces = re.findall(r"Piece id: (\w+)", messages[-1]["content"])
        lines = [
            "Every tool says it saves time. Show me how.",
            "I'd need to see pricing before I click.",
            "This feels written for a bigger team than mine.",
            "The number is good, but whose number is it?",
            "Clear and specific. I'd at least look.",
        ]
        out = []
        for p in pieces:
            s = 3 + _h(buyer, p, messages[-1]["content"]) % 7
            out.append({"piece": p, "click": s >= 7, "score": s, "objection": lines[_h(p, buyer) % len(lines)], "reason": "mock reaction"})
        return {"reactions": out}
    if task == "rewrite":
        text = messages[-1]["content"]
        ids = re.findall(r"^## (\w+) \(", text, re.M)
        out = {}
        for p in ids:
            if p.startswith("email"):
                out[p] = {"subject": "Will this get my domain blacklisted? No.", "preview": "How warmup and safe limits protect you.", "body": f"Hi,\n\nThe worry with cold email is your domain. {name} warms it up first and caps sends per day.\n\nThe {name} team", "addresses": "fear of the domain being blacklisted"}
            elif p == "google":
                out[p] = {"headlines": ["Cold Email Without Spam", "From $29 A Month", "Built For Founders"], "descriptions": ["Warmup and safe sending limits keep your domain clean. Used by 4,000 teams.", "Try it free for 14 days."], "addresses": "pricing and spam worries"}
            elif p == "meta":
                out[p] = {"primary": f"Doing outbound yourself? {name} warms up your domain and caps daily sends, so your emails reach the inbox. From $29 a month.", "headline": "Cold email, minus the spam", "addresses": "pricing and spam worries"}
            elif p == "linkedin":
                out[p] = {"intro": "Founders and first sales hires use us to run outbound without a sales ops team. Plans from $29 a month.", "headline": "Outbound you can run yourself", "addresses": "built for a bigger team"}
            else:
                out[p] = {"headline": "Run outbound yourself, without landing in spam", "subline": "Warmup, safe limits and one inbox for replies. Plans from $29 a month.", "addresses": "pricing and spam worries"}
        return {"rewrites": out}
    return {}
