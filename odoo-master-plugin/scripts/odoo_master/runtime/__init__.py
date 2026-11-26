"""Harness adapters. The core (odoo, workflow, mcp, reporting, integrations) never imports these.

An adapter turns a harness-neutral request — "run workflow X with inputs Y" or "dispatch agent A with
brief B" — into the concrete invocation of one agent runtime. Only Claude Code is implemented; the
interface is what other harnesses (Codex, Hermes, Pi, custom runtimes) would implement.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class HarnessAdapter(ABC):
    name = "abstract"

    @abstractmethod
    def workflow_command(self, workflow: str, inputs: dict, cwd: str) -> list[str]:
        """Command line that starts a headless run executing `workflow` with `inputs`."""

    @abstractmethod
    def agent_reference(self, agent: str) -> str:
        """How the harness addresses a specialist agent (e.g. 'odoo-master:code-reviewer')."""

    @abstractmethod
    def capabilities(self) -> dict:
        """Which plugin features the harness supports natively (hooks, subagents, skills, mcp, workflows)."""


def get_adapter(name: str = "claude-code") -> HarnessAdapter:
    if name == "claude-code":
        from .claude_code import ClaudeCodeAdapter
        return ClaudeCodeAdapter()
    raise NotImplementedError(f"no adapter for harness {name!r} yet (see docs/architecture.md#portability)")
