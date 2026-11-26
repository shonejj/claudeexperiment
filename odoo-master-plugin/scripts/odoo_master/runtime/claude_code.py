"""Claude Code adapter."""
from __future__ import annotations

from . import HarnessAdapter


class ClaudeCodeAdapter(HarnessAdapter):
    name = "claude-code"

    def workflow_command(self, workflow: str, inputs: dict, cwd: str) -> list[str]:
        args = " ".join(f'-i {k}="{v}"' for k, v in inputs.items())
        prompt = (f"/odoo-master:workflow-execution Run `odoo-master workflow start {workflow} {args}` and drive it to completion "
                  "or to the next approval gate.")
        return ["claude", "-p", prompt, "--output-format", "json"]

    def agent_reference(self, agent: str) -> str:
        return f"odoo-master:{agent}"

    def capabilities(self) -> dict:
        return {"hooks": True, "subagents": True, "skills": True, "mcp": True, "native_workflows": True, "worktrees": True,
                "headless": "claude -p"}
