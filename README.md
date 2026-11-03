# Marketing funnel agent

Paste a product page. The agent reads it, finds the competitors and the angle none of them own, writes a launch kit (Meta, Google and LinkedIn ads, a landing page hero, a three-email sequence), shows every piece to a panel of five synthetic buyers, and rewrites what they reject.

Every piece is drawn as a mockup of where it would run. You can edit any of them in place and the panel reads your version again.

## How the agent works

1. **Read the page.** The page is fetched (private and local addresses are refused) and reduced to its title, headings and text. If a site blocks it, paste the text instead.
2. **Brief.** One call pulls out the product, audience, offer and proof, using only what's on the page.
3. **Market.** Web search (Tavily) for the category, a call to pick real competitors, and each competitor's own home page read directly. One call places everyone on two axes and names the gap. The gap has to come with a quote from the product's page, and code checks the quote is really there.
4. **Panel.** Five buyers built from the page, deliberately different (including a sceptic and a partial fit). They are spread across different models so the panel doesn't think with one brain.
5. **Drafts.** One call writes all seven pieces. Length limits are checked in code: anything over gets one fix-up call, then a hard trim on a word boundary. A Google headline can't come back longer than 30 characters.
6. **Reactions.** Each buyer reads every piece and says whether they'd click, a score and the objection in their own voice. Buyers run in parallel and stream in as they finish.
7. **Rewrite.** Pieces averaging under the bar (6 by default) are rewritten by a separate call to answer the objections, using facts from the page, then scored again by the same panel.

All of this is a plain Python loop (`backend/app/agent.py`), no agent framework. Every step streams to the browser as a server-sent event.

## Stack

- `backend/`: FastAPI, httpx. Models: Gemini 3.5 Flash Lite and Groq-hosted models (GPT-OSS, Qwen) through one OpenAI-format adapter with fallbacks (`providers.py`). Prompts are all in `prompts.py`.
- `frontend/`: Next.js 15, React 19, no UI library. The mockups are plain HTML and CSS.

## Run it locally

```bash
cd backend
python -m venv .venv && .venv/bin/pip install -r requirements.txt -r requirements-dev.txt
ENABLE_MOCK_MODEL=1 .venv/bin/uvicorn app.main:app --port 8000   # no keys needed
.venv/bin/pytest

cd ../frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev
```

With real models, set `GEMINI_API_KEY` and/or `GROQ_API_KEY`, and `TAVILY_API_KEY` for competitor search. See `backend/.env.example`.

## Limits

The buyers are simulations. They're useful for finding vague or unconvincing copy, not for predicting real click rates. Each visitor gets a few runs a day so the free model quotas last.
