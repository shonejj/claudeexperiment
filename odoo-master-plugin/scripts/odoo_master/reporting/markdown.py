"""Dependency-free Markdown -> HTML converter covering what our templates use:
frontmatter, headings, paragraphs, emphasis, inline code, links, ordered/unordered (nested) lists,
task lists, tables, fenced code (```mermaid becomes <pre class="mermaid">), blockquotes, rules.
Uses python-markdown instead when it is installed.
"""
from __future__ import annotations

import html
import re

from ..util import yaml


def split_frontmatter(text: str) -> tuple[dict, str]:
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            fm_text = text[4:end]
            body = text[end + 4:].lstrip("\n")
            try:
                fm = yaml.safe_load(fm_text) if yaml else {}
            except Exception:
                fm = {}
            return (fm or {}), body
    return {}, text


def _inline(s: str) -> str:
    codes = []

    def keep(m):
        codes.append(f"<code>{html.escape(m.group(1))}</code>")
        return f"\x00{len(codes) - 1}\x00"
    s = re.sub(r"`([^`]+)`", keep, s)
    s = html.escape(s, quote=False)
    s = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: f'<a href="{html.escape(m.group(2))}">{m.group(1)}</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"<em>\1</em>", s)
    s = re.sub(r"(?<![\w_])_([^_\n]+)_(?![\w_])", r"<em>\1</em>", s)
    return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)


def to_html(md: str) -> str:
    try:
        import markdown as _md  # type: ignore
        return _md.markdown(md, extensions=["tables", "fenced_code", "sane_lists"])
    except ImportError:
        pass
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    list_stack: list[tuple[str, int]] = []

    def close_lists(to_indent=-1):
        while list_stack and list_stack[-1][1] > to_indent:
            out.append(f"</{list_stack.pop()[0]}>")

    while i < len(lines):
        ln = lines[i]
        if ln.strip().startswith("```"):
            close_lists()
            lang = ln.strip()[3:].strip()
            buf = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            code = html.escape("\n".join(buf))
            out.append(f'<pre class="mermaid">{code}</pre>' if lang == "mermaid" else f'<pre><code class="lang-{html.escape(lang)}">{code}</code></pre>')
            i += 1
            continue
        if re.match(r"^\s*\|.*\|\s*$", ln) and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{2,}", lines[i + 1]):
            close_lists()
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            out.append("<table><thead><tr>" + "".join(f"<th>{_inline(c)}</th>" for c in head) + "</tr></thead><tbody>")
            i += 2
            while i < len(lines) and re.match(r"^\s*\|.*\|\s*$", lines[i]):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                out.append("<tr>" + "".join(f"<td>{_inline(c)}</td>" for c in cells) + "</tr>")
                i += 1
            out.append("</tbody></table>")
            continue
        m = re.match(r"^(#{1,6})\s+(.*)$", ln)
        if m:
            close_lists()
            n = len(m.group(1))
            out.append(f"<h{n}>{_inline(m.group(2))}</h{n}>")
            i += 1
            continue
        if re.match(r"^\s*(---|\*\*\*)\s*$", ln):
            close_lists()
            out.append("<hr/>")
            i += 1
            continue
        m = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", ln)
        if m:
            indent = len(m.group(1))
            kind = "ol" if m.group(2)[0].isdigit() else "ul"
            if not list_stack or indent > list_stack[-1][1]:
                out.append(f"<{kind}>")
                list_stack.append((kind, indent))
            else:
                close_lists(indent)
                if not list_stack:
                    out.append(f"<{kind}>")
                    list_stack.append((kind, indent))
            item = m.group(3)
            tm = re.match(r"^\[([ xX])\]\s+(.*)$", item)
            if tm:
                item = ("☑ " if tm.group(1).lower() == "x" else "☐ ") + tm.group(2)
            out.append(f"<li>{_inline(item)}</li>")
            i += 1
            continue
        if ln.startswith(">"):
            close_lists()
            buf = []
            while i < len(lines) and lines[i].startswith(">"):
                buf.append(lines[i].lstrip("> "))
                i += 1
            out.append(f"<blockquote>{_inline(' '.join(buf))}</blockquote>")
            continue
        if not ln.strip():
            close_lists()
            i += 1
            continue
        close_lists()
        buf = [ln]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^(#{1,6}\s|```|\s*[-*+]\s|\s*\d+[.)]\s|>|\s*\|)", lines[i]):
            buf.append(lines[i])
            i += 1
        out.append(f"<p>{_inline(' '.join(s.strip() for s in buf))}</p>")
    close_lists()
    return "\n".join(out)
