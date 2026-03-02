"""Render stack argv templates.

We support a tiny expression language inside braces, evaluated with a safe
evaluator. Example:

    "{net.bind_host}:{net.cmd_base + axis_index}"

The evaluator supports:
- literals, + - * // / %
- attribute access on namespaces (net, rig, stack)
- names: axis, axis_index, len(...)

If a rendered arg produces a list, it is spliced into argv.
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Iterable, List

_BRACE_RE = re.compile(r"\{([^{}]+)\}")


@dataclass(frozen=True)
class RenderContext:
    stack: Any
    net: Any
    rig: Any
    axis: str | None = None
    axis_index: int | None = None


def _csv(xs: Any) -> str:
    if xs is None:
        return ""
    if isinstance(xs, (list, tuple)):
        return ",".join([str(x) for x in xs])
    return str(xs)


def _repeat(flag: str, xs: Any) -> list:
    """Return argv fragments that repeat a flag for every element.

    Example: repeat('--axis', ['Anton','Debby']) ->
      ['--axis','Anton','--axis','Debby']
    """
    out: list = []
    if xs is None:
        return out
    if not isinstance(xs, (list, tuple)):
        xs = [xs]
    for x in xs:
        out.append(flag)
        out.append(x)
    return out


_SAFE_FUNCS = {"len": len, "int": int, "str": str, "csv": _csv, "repeat": _repeat}


class _SafeEval(ast.NodeVisitor):
    def __init__(self, names: dict[str, Any]):
        self.names = names

    def visit(self, node: ast.AST):  # type: ignore[override]
        return super().visit(node)

    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant):
        return node.value

    def visit_Name(self, node: ast.Name):
        if node.id in self.names:
            return self.names[node.id]
        raise ValueError(f"Unknown name: {node.id}")

    def visit_Attribute(self, node: ast.Attribute):
        base = self.visit(node.value)
        try:
            return getattr(base, node.attr)
        except Exception as e:
            raise ValueError(f"Bad attribute access: {node.attr}") from e

    def visit_BinOp(self, node: ast.BinOp):
        left = self.visit(node.left)
        right = self.visit(node.right)
        op = node.op
        if isinstance(op, ast.Add):
            return left + right
        if isinstance(op, ast.Sub):
            return left - right
        if isinstance(op, ast.Mult):
            return left * right
        if isinstance(op, ast.Div):
            return left / right
        if isinstance(op, ast.FloorDiv):
            return left // right
        if isinstance(op, ast.Mod):
            return left % right
        raise ValueError(f"Operator not allowed: {type(op).__name__}")

    def visit_UnaryOp(self, node: ast.UnaryOp):
        operand = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return +operand
        if isinstance(node.op, ast.USub):
            return -operand
        raise ValueError(f"Unary operator not allowed: {type(node.op).__name__}")

    def visit_Call(self, node: ast.Call):
        fn = self.visit(node.func)
        if fn not in _SAFE_FUNCS.values():
            raise ValueError("Only safe functions allowed")
        args = [self.visit(a) for a in node.args]
        if node.keywords:
            raise ValueError("Keyword args not allowed")
        return fn(*args)

    def generic_visit(self, node: ast.AST):  # pragma: no cover
        raise ValueError(f"Expression not allowed: {type(node).__name__}")


def _ns(obj: Any) -> Any:
    if isinstance(obj, SimpleNamespace):
        return obj
    if isinstance(obj, dict):
        return SimpleNamespace(**{k: _ns(v) for k, v in obj.items()})
    if isinstance(obj, list):
        return [_ns(v) for v in obj]
    return obj


def eval_expr(expr: str, ctx: RenderContext) -> Any:
    """Evaluate a single brace expression."""
    names = {
        "stack": ctx.stack,
        "net": ctx.net,
        "rig": ctx.rig,
        "axis": ctx.axis,
        "axis_index": ctx.axis_index,
        **_SAFE_FUNCS,
    }
    tree = ast.parse(expr, mode="eval")
    return _SafeEval(names).visit(tree)


def render_arg(template: Any, ctx: RenderContext) -> Any:
    """Render one argument template (string or other TOML literal)."""
    if not isinstance(template, str):
        return template

    # If string has no braces, return as-is.
    if "{" not in template:
        return template

    # Special case: template is exactly one brace expression -> return typed value.
    m = _BRACE_RE.fullmatch(template.strip())
    if m:
        return eval_expr(m.group(1).strip(), ctx)

    # Otherwise do string interpolation.
    def repl(match: re.Match[str]) -> str:
        val = eval_expr(match.group(1).strip(), ctx)
        return str(val)

    return _BRACE_RE.sub(repl, template)


def render_argv(args: Iterable[Any], ctx: RenderContext) -> List[str]:
    """Render args list to argv; list-valued args are spliced."""
    out: List[str] = []
    for a in args:
        r = render_arg(a, ctx)
        if r is None:
            continue
        if isinstance(r, list):
            out.extend([str(x) for x in r])
        else:
            out.append(str(r))
    return out


def make_context(
    *, stack: dict, net: dict, rig: dict, axis: str | None, axis_index: int | None
) -> RenderContext:
    return RenderContext(
        stack=_ns(stack), net=_ns(net), rig=_ns(rig), axis=axis, axis_index=axis_index
    )
