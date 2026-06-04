"""ArgoDesk branded report export ("brain to PDF").

Turns a chat session into a structured, client-ready document — a consulting
summary, meeting minutes, or technical report — rendered as a self-contained,
company-branded HTML page. The HTML can be printed to PDF or saved to Documents
client-side (the frontend already ships html2pdf.js / DOCX export), so this
module adds no heavy server-side PDF/DOCX dependencies.
"""

import html as _html
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# report_type -> (human label, LLM instruction). Italian-first since the product
# targets Italian SMEs; the model still mirrors the conversation's language.
REPORT_TYPES: Dict[str, Tuple[str, str]] = {
    "consulenza": (
        "Riepilogo consulenza",
        "Produci un riepilogo professionale della consulenza per il cliente: "
        "contesto, punti discussi, raccomandazioni e prossimi passi (action items).",
    ),
    "verbale": (
        "Verbale riunione",
        "Produci un verbale di riunione: partecipanti (se noti), ordine del giorno, "
        "decisioni prese, e action items con eventuali responsabili e scadenze.",
    ),
    "relazione": (
        "Relazione tecnica",
        "Produci una relazione tecnica strutturata: obiettivo, analisi, risultati, "
        "criticità e conclusioni con raccomandazioni operative.",
    ),
}
DEFAULT_REPORT_TYPE = "consulenza"


def _company_brand() -> Dict[str, str]:
    """Branding for the report header, from settings with safe defaults."""
    try:
        from src.settings import get_setting
        name = get_setting("company_name") or "ArgoDesk"
        logo = get_setting("company_logo_url") or ""
    except Exception:
        name, logo = "ArgoDesk", ""
    return {"name": str(name), "logo": str(logo)}


def _build_messages(report_label: str, instruction: str, history: List[Dict]) -> List[Dict]:
    system = (
        "Sei un assistente che redige documenti professionali a partire da una "
        f"conversazione. {instruction}\n\n"
        "Formato: Markdown con intestazioni di sezione (##), elenco puntato per gli "
        "action items, conciso e adatto a essere inviato a un cliente. Inizia con un "
        f"titolo di primo livello (#) appropriato per un '{report_label}'. "
        "Rispondi nella stessa lingua della conversazione (italiano se la "
        "conversazione è in italiano). Non inventare fatti non presenti."
    )
    # Flatten the conversation into a single transcript user message.
    lines = []
    for m in history:
        role = m.get("role", "")
        if role not in ("user", "assistant"):
            continue
        content = m.get("content", "")
        if not isinstance(content, str):
            content = str(content)
        who = "Utente" if role == "user" else "Assistente"
        lines.append(f"{who}: {content}")
    transcript = "\n\n".join(lines)
    if len(transcript) > 20000:
        transcript = transcript[:20000] + "\n[...troncato...]"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Conversazione da sintetizzare:\n\n{transcript}"},
    ]


async def generate_report_markdown(history: List[Dict], report_type: str, owner: Optional[str]) -> str:
    """Ask the configured utility LLM to structure the conversation into a report."""
    from src.endpoint_resolver import resolve_endpoint
    from src.llm_core import llm_call_async

    label, instruction = REPORT_TYPES.get(report_type, REPORT_TYPES[DEFAULT_REPORT_TYPE])
    endpoint_url, model, headers = resolve_endpoint("utility", owner=owner)
    if not endpoint_url or not model:
        raise ValueError("Nessun modello configurato — imposta un modello di default nelle Impostazioni.")
    messages = _build_messages(label, instruction, history)
    text = await llm_call_async(
        endpoint_url, model, messages, temperature=0.3, max_tokens=2000, headers=headers,
    )
    return (text or "").strip()


def render_report_html(markdown_text: str, report_type: str) -> Tuple[str, str]:
    """Render branded, self-contained HTML. Returns (title, html)."""
    from src.visual_report import _md_to_html, strip_thinking, _extract_report_title

    label, _ = REPORT_TYPES.get(report_type, REPORT_TYPES[DEFAULT_REPORT_TYPE])
    markdown_text = strip_thinking(markdown_text or "")
    title, body_md = _extract_report_title(markdown_text, label)
    body_html = _md_to_html(body_md)

    brand = _company_brand()
    logo_html = (
        f'<img src="{_html.escape(brand["logo"], quote=True)}" alt="" class="brand-logo">'
        if brand["logo"] else ""
    )
    date_str = datetime.now().strftime("%d/%m/%Y")
    safe_title = _html.escape(title)
    safe_label = _html.escape(label)
    safe_company = _html.escape(brand["name"])

    page = f"""<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{safe_title} — {safe_company}</title>
<style>
  :root {{ color-scheme: light; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    max-width: 800px; margin: 0 auto; padding: 40px 24px; color: #1a1a1a; line-height: 1.6; }}
  .report-head {{ display:flex; align-items:center; justify-content:space-between;
    border-bottom: 3px solid #2563eb; padding-bottom: 16px; margin-bottom: 28px; }}
  .brand-logo {{ max-height: 48px; max-width: 200px; }}
  .report-company {{ font-size: 20px; font-weight: 700; color: #2563eb; }}
  .report-kind {{ font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: #666; }}
  .report-date {{ font-size: 13px; color: #666; }}
  h1 {{ font-size: 26px; margin: 0 0 24px; }}
  h2 {{ font-size: 19px; margin-top: 28px; border-bottom: 1px solid #e5e7eb; padding-bottom: 4px; }}
  ul, ol {{ padding-left: 22px; }}
  .report-footer {{ margin-top: 40px; padding-top: 16px; border-top: 1px solid #e5e7eb;
    font-size: 11px; color: #999; text-align: center; }}
  @media print {{ body {{ padding: 0; }} .report-head {{ page-break-after: avoid; }} }}
</style>
</head>
<body>
  <div class="report-head">
    <div>
      <div class="report-company">{safe_company}</div>
      <div class="report-kind">{safe_label}</div>
    </div>
    <div style="text-align:right;">
      {logo_html}
      <div class="report-date">{date_str}</div>
    </div>
  </div>
  <h1>{safe_title}</h1>
  {body_html}
  <div class="report-footer">Generato da {safe_company} · {date_str}</div>
</body>
</html>"""
    return title, page
