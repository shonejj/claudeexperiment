"""Safe condition expressions for workflow `when:` / `auto_approve_when:`.

Allowed: literals, names `ctx` / `inputs` / `config`, attribute-free subscripts (ctx['risk']),
`.get(key[, default])` calls on those dicts, comparisons, `in`/`not in`, and/or/not, len().
Anything else raises ValueError, so workflow files can never execute arbitrary code.
"""
from __future__ import annotations

import ast
from typing import Any

_ALLOWED_NODES = (ast.Expression, ast.BoolOp, ast.And, ast.Or, ast.UnaryOp, ast.Not, ast.Compare, ast.Eq, ast.NotEq,
                  ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.In, ast.NotIn, ast.Is, ast.IsNot, ast.Constant, ast.Name,
                  ast.Load, ast.Subscript, ast.Tuple, ast.List, ast.Dict, ast.Call, ast.Attribute, ast.Slice)


def _check(node: ast.AST, names: set[str]) -> None:
    for n in ast.walk(node):
        if not isinstance(n, _ALLOWED_NODES):
            raise ValueError(f"expression element not allowed: {type(n).__name__}")
        if isinstance(n, ast.Name) and n.id not in names and n.id not in ("len", "True", "False", "None"):
            raise ValueError(f"unknown name: {n.id}")
        if isinstance(n, ast.Attribute) and n.attr != "get":
            raise ValueError("only .get() attribute access is allowed")
        if isinstance(n, ast.Call):
            f = n.func
            if not ((isinstance(f, ast.Attribute) and f.attr == "get") or (isinstance(f, ast.Name) and f.id == "len")):
                raise ValueError("only .get() and len() calls are allowed")


def evaluate(expr: str | bool | None, **names: Any) -> bool:
    if expr is None or expr == "":
        return True
    if isinstance(expr, bool):
        return expr
    tree = ast.parse(str(expr), mode="eval")
    _check(tree, set(names))
    return bool(eval(compile(tree, "<when>", "eval"), {"__builtins__": {"len": len}}, dict(names)))  # noqa: S307 - AST whitelisted
