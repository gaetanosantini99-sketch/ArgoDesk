"""Agent-loop hardening (2026-06-08 session):

- Tool output that can carry external / attacker-controllable content (shell,
  fetched pages, file/email/API bodies, MCP tools) is fenced as UNTRUSTED DATA
  before being fed back to the model, so an in-output prompt-injection payload
  is treated as data, not a command. Our own status-message tools are excluded
  to avoid bloating every round.
- The RAG tool-retrieval budget K scales with the model's context window so
  small local models aren't drowned by tool schemas.

Imports `src.agent_loop` (needs the app deps installed).
"""

import pytest


# ── untrusted tool-output classification ───────────────────────────

@pytest.mark.parametrize("tool", [
    "bash", "python", "web_search", "web_fetch", "read_file",
    "api_call", "app_api", "read_email", "list_emails", "search_chats",
])
def test_external_output_tools_are_untrusted(tool):
    from src.agent_loop import _is_untrusted_output_tool
    assert _is_untrusted_output_tool(tool) is True


def test_mcp_namespaced_tools_are_untrusted():
    from src.agent_loop import _is_untrusted_output_tool
    # MCP tools are "server__tool" — caught by the "__" namespace check.
    assert _is_untrusted_output_tool("filesystem__read_file") is True
    assert _is_untrusted_output_tool("sdi_connector__fetch_invoice") is True


def test_malformed_tool_name_fails_closed():
    from src.agent_loop import _is_untrusted_output_tool
    assert _is_untrusted_output_tool(None) is True
    assert _is_untrusted_output_tool(123) is True


@pytest.mark.parametrize("tool", [
    "create_document", "update_document", "edit_document",
    "manage_settings", "manage_memory", "manage_tasks", "manage_skills",
    "ui_control", "generate_image", "list_models",
])
def test_internal_status_tools_are_not_wrapped(tool):
    # These only emit our own success/status text; wrapping them every round
    # would bloat context for no security gain.
    from src.agent_loop import _is_untrusted_output_tool
    assert _is_untrusted_output_tool(tool) is False


# ── context-aware tool budget ──────────────────────────────────────

def test_tool_budget_scales_with_context_window():
    from src.agent_loop import _tool_budget_for_context
    # Tiny local models get a tight budget; large models get more tools.
    assert _tool_budget_for_context(4096) == 3
    assert _tool_budget_for_context(8192) == 3
    assert _tool_budget_for_context(16384) == 6
    assert _tool_budget_for_context(32768) == 6
    assert _tool_budget_for_context(65536) == 8
    assert _tool_budget_for_context(131072) == 12


def test_tool_budget_unknown_window_keeps_default():
    from src.agent_loop import _tool_budget_for_context
    # 0 / unknown / malformed -> historical default of 8 (no regression).
    assert _tool_budget_for_context(0) == 8
    assert _tool_budget_for_context(-1) == 8
    assert _tool_budget_for_context(None) == 8
