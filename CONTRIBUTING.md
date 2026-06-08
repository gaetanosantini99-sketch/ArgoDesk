# Developing ArgoDesk

ArgoDesk is a closed-source commercial product maintained by an internal team.
This document covers local setup, testing, and the conventions used for internal
changes. The project moves quickly, so the best changes are focused, easy to
review, and easy to test.

## Before You Start

- Check existing internal tickets before starting new work.
- Prefer one bug fix or feature per change.
- Avoid broad rewrites, formatting-only changes, or moving many files unless the
  task is specifically about structure.
- For a large feature, write up the approach first and align with the team.

## Setup

Docker is the recommended path for normal testing:

```bash
cp .env.example .env
docker compose up -d --build
```

Manual development uses Python 3.11+:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 7000
```

Windows is not actively tested. Docker on Linux or a Linux/macOS manual install
is the safer path for now.

## Running Checks

Run the smallest relevant checks for your change:

```bash
python -m pytest
python -m py_compile app.py routes/*.py src/*.py
node --check static/js/<file-you-changed>.js
```

For Docker-related changes:

```bash
docker compose config
docker compose up -d --build
docker compose logs --tail=120 argodesk
```

Note what you ran in your change description. If you could not run a check, say so.

## Change Reviews

Good changes usually include:

- A short explanation of the bug or feature.
- The files or areas changed.
- Manual test steps or automated test results from running the actual app, not
  just the test suite.
- Screenshots or short recordings for UI changes.
- Links to the related internal ticket.

Please keep changes small. Large changes that mix unrelated cleanup, formatting,
refactors, and behavior changes are much harder to review.

> **Auto-generated changes.** If you are running an LLM agent (Devin, Cursor,
> OpenHands, Claude Code, etc.) against this codebase: describe the problem and
> approach first. Bulk agent-generated changes that don't match the project's
> visual style or conventions will be sent back for rework, even when the
> underlying fix is correct.

## Style and visual changes

ArgoDesk has an intentional visual style. Changes that ignore it will be sent
back, no matter how correct the underlying code is.

Before submitting any change that affects what the app looks like — buttons,
icons, fonts, colors, spacing, layout, CSS, HTML, SVG, or any `static/js/`
module that draws to the DOM — please:

1. **Run the app locally** and view the change in a browser. Type-checks and
   unit tests are not enough.
2. **Attach a screenshot or short clip** of the change in the running app. Add a
   mobile screenshot too if the change affects mobile.
3. **Match the existing visual language.** Specifically:
   - Reuse existing CSS variables (`--red`, `--fg`, `--bg`, `--card`, `--border`, …).
     Do not introduce new color values, font sizes, or spacing units.
   - Reuse existing button, input, card, and border classes. Don't invent
     parallel styling for similar widgets.
   - **No Unicode emoji in UI or code.** Use inline SVG (matching the monochrome
     icon style already in `static/index.html`) or plain text.
   - Monospaced font (`Fira Code`) for primary UI text. Don't override.
   - Dark theme is the default; any light-mode work goes through the existing
     theme system, not hard-coded.
4. **Don't add parallel components.** If a similar widget already exists in the
   app, extend it instead of writing a new one.

If you are unsure whether a change is "visual," it is. Default to attaching a
screenshot.

## Bug Reports

For bugs, include:

- Install method: Docker, manual Python, WSL, etc.
- OS, browser, and device if relevant.
- Exact steps to reproduce.
- Expected behavior and actual behavior.
- Logs, screenshots, or terminal output.

For model-serving issues, include:

- Backend: Ollama, vLLM, SGLang, llama.cpp, LM Studio, etc.
- Model name.
- GPU/CPU and operating system.
- Cookbook task logs or server logs.

## Security

Do not post secrets, API keys, private logs, personal documents, or public IPs
in tickets or change descriptions.

For security reports, follow [SECURITY.md](SECURITY.md).
