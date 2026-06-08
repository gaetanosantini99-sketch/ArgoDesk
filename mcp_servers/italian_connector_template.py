"""
italian_connector_template.py

TEMPLATE — per-client placeholder, NOT wired into the product by default.

ArgoDesk integrations toward Italian business systems (fatturazione elettronica /
SDI, PEC, gestionali, CRM) are built *su misura* for each client deployment,
because they need that client's real API endpoints, credentials and flows
(firma digitale, trasmissione SDI, ecc.). This file is a copy-me scaffold that
shows the shape of such an MCP connector; it is intentionally inert:

  - It is NOT listed in src/builtin_mcp.py `_BUILTIN_SERVERS`, so it never starts
    on its own and adds no tools to the agent until a client build wires it.
  - Every tool returns a clear "not configured" placeholder instead of calling a
    real service, so nothing breaks if it is ever launched by mistake.

To turn this into a real connector for a client:
  1. Copy this file to e.g. `mcp_servers/<cliente>_gestionale_server.py`.
  2. Rename the `Server("italian-connector")` instance.
  3. Fill in `inputSchema` for the real operations and implement `call_tool` to
     call the client's API (read credentials from env / secret_storage, never
     hard-code secrets).
  4. Register it: add it to `_BUILTIN_SERVERS` in src/builtin_mcp.py, or add it
     at runtime via the MCP admin UI (POST /api/mcp/servers).

Run standalone for a smoke test:  python mcp_servers/italian_connector_template.py
"""

import asyncio
import os
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

server = Server("italian-connector")

# Set this (per client) once the connector is implemented. While False, every
# tool answers with a placeholder so the agent gets an explicit "non configurato"
# instead of a crash or a silent no-op.
_CONFIGURED = False

# Env var names a real implementation would read its credentials from. Listed
# here as documentation; the template never dereferences live secrets.
_EXPECTED_ENV = ("ARGODESK_CONNECTOR_BASE_URL", "ARGODESK_CONNECTOR_API_KEY")


def _placeholder(operation: str) -> str:
    missing = [k for k in _EXPECTED_ENV if not os.environ.get(k)]
    return (
        f"[connettore italiano — template non configurato]\n"
        f"Operazione richiesta: {operation}\n"
        f"Questo è un connettore placeholder da sviluppare su misura per il cliente.\n"
        f"Variabili d'ambiente attese (mancanti: {', '.join(missing) or 'nessuna'}): "
        f"{', '.join(_EXPECTED_ENV)}.\n"
        f"Vedi le istruzioni in cima a mcp_servers/italian_connector_template.py."
    )


@server.list_tools()
async def list_tools() -> list[Tool]:
    # Representative operations for an Italian business connector. Schemas are
    # deliberately generic; a real build tightens them per the client's API.
    return [
        Tool(
            name="connector_fattura_lookup",
            description=(
                "Placeholder: cerca/recupera una fattura nel gestionale del "
                "cliente. Da implementare su misura (es. Fatture in Cloud / SDI)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "numero": {"type": "string", "description": "Numero fattura o identificativo documento"},
                    "anno": {"type": "string", "description": "Anno/esercizio di riferimento"},
                },
                "required": [],
            },
        ),
        Tool(
            name="connector_pec_send",
            description=(
                "Placeholder: invia un messaggio via PEC tramite il provider del "
                "cliente. Da implementare su misura (gestione ricevute/firma)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "destinatario": {"type": "string", "description": "Indirizzo PEC destinatario"},
                    "oggetto": {"type": "string"},
                    "corpo": {"type": "string"},
                },
                "required": ["destinatario", "oggetto"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if not _CONFIGURED:
        return [TextContent(type="text", text=_placeholder(name))]
    # A real implementation dispatches on `name` here and calls the client API.
    return [TextContent(type="text", text=f"[italian-connector] operazione '{name}' non implementata.")]


async def _amain() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(_amain())
