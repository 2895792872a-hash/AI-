"""Security module — blacklist validation + AST syntax checking.

Two-layer defense for Agent-generated browser actions:
  1. Blacklist: pattern-match dangerous URLs, selectors, actions, code keywords.
  2. AST check:  static analysis of any Python/JS code snippet the Agent produces,
     blocking imports, exec/eval, dangerous attribute access, etc.

Used by:
  - task_parsing node: validate steps right after LLM generation.
  - browser_ops node:   re-validate each step before Playwright execution.
"""

from __future__ import annotations

import re
import ast
from typing import Optional

from app.agent.state import BrowserStep
from app.core.logging import logger

# ════════════════════════════════════════════════════════════════
# Layer 1 — Blacklists
# ════════════════════════════════════════════════════════════════

# Actions the browser executor supports (everything else is blocked)
ALLOWED_ACTIONS: frozenset[str] = frozenset({
    "navigate", "click", "type", "scroll", "extract", "screenshot",
})

# URL patterns that are *never* safe for automation
BLOCKED_URL_PATTERNS: list[str] = [
    r"^file://",
    r"^chrome://",
    r"^about:",
    r"^javascript:",
    r"^data:",
    r"localhost",
    r"127\.0\.0\.1",
    r"0\.0\.0\.0",
    r"^ftp://",
    r"\.internal$",
]

# Selector patterns suggesting path traversal or system access
BLOCKED_SELECTOR_PATTERNS: list[str] = [
    r"\.\./",
    r"/etc/",
    r"/proc/",
    r"/sys/",
    r"C:\\Windows",
    r"/var/",
]

# Forbidden substrings in any input_value (case-insensitive)
FORBIDDEN_KEYWORDS: frozenset[str] = frozenset({
    "eval", "exec", "__import__",
    "os.system", "subprocess",
    "open(", "file(",
    "<script", "javascript:",
    "rm -rf", "del /",
})


def check_blacklist(step: BrowserStep) -> tuple[bool, Optional[str]]:
    """Run blacklist checks on a single BrowserStep.

    Returns:
        (is_safe, error_message) — error_message is None when safe.
    """
    action = step.get("action", "")

    # 1. Action type whitelist
    if action not in ALLOWED_ACTIONS:
        return False, f"Action '{action}' is not in allowed set: {sorted(ALLOWED_ACTIONS)}"

    # 2. URL checks (for navigate action)
    url = step.get("url")
    if url:
        for pattern in BLOCKED_URL_PATTERNS:
            if re.search(pattern, url, re.IGNORECASE):
                return False, f"URL '{url}' matches blocked pattern '{pattern}'"

    # 3. Selector checks
    selector = step.get("target_selector")
    if selector:
        for pattern in BLOCKED_SELECTOR_PATTERNS:
            if re.search(pattern, selector, re.IGNORECASE):
                return False, f"Selector matches blocked pattern '{pattern}'"

    # 4. Input value keyword checks
    value = step.get("input_value")
    if value:
        value_lower = value.lower()
        for kw in FORBIDDEN_KEYWORDS:
            if kw.lower() in value_lower:
                return False, f"Input value contains forbidden keyword '{kw}'"

    return True, None


def validate_all_steps(steps: list[BrowserStep]) -> list[BrowserStep]:
    """Validate every step; drop blocked ones with a warning.

    Returns:
        List of only safe steps.
    """
    safe: list[BrowserStep] = []
    for step in steps:
        ok, err = check_blacklist(step)
        if ok:
            safe.append(step)
        else:
            logger.warning(
                "Security blocked step %d (%s): %s",
                step.get("step_id", "?"),
                step.get("action", "?"),
                err,
            )
    dropped = len(steps) - len(safe)
    if dropped:
        logger.info("Dropped %d/%d steps due to security checks", dropped, len(steps))
    return safe


# ════════════════════════════════════════════════════════════════
# Layer 2 — Python AST Checker
# ════════════════════════════════════════════════════════════════

FORBIDDEN_FUNCTION_NAMES: frozenset[str] = frozenset({
    "eval", "exec", "compile",
    "open", "__import__",
    "getattr", "setattr", "delattr",
    "globals", "locals", "vars",
})

FORBIDDEN_MODULE_PREFIXES: frozenset[str] = frozenset({
    "os", "subprocess", "sys", "shutil",
    "socket", "requests", "urllib",
    "pickle", "marshal",
    "ctypes", "multiprocessing",
    "pathlib",
})

DANGEROUS_DUNDER_ATTRIBUTES: frozenset[str] = frozenset({
    "__subclasses__", "__bases__", "__mro__",
    "__class__", "__globals__", "__code__",
    "__builtins__",
})


def validate_python_code(code: str) -> tuple[bool, Optional[str]]:
    """Check Python code for dangerous constructs via AST analysis.

    Returns:
        (is_safe, error_message)
    """
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return False, f"Python syntax error: {exc}"

    for node in ast.walk(tree):
        # --- Imports ---
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = node.names if isinstance(node, ast.Import) else [node]
            for alias in names:
                top = alias.name.split(".")[0] if alias.name else ""
                if top in FORBIDDEN_MODULE_PREFIXES:
                    return False, f"Forbidden import: {alias.name}"

        # --- Direct dangerous calls ---
        if isinstance(node, ast.Call):
            name = _get_call_name(node)
            if name and name in FORBIDDEN_FUNCTION_NAMES:
                return False, f"Forbidden function: {name}()"

        # --- Dangerous dunder attributes ---
        if isinstance(node, ast.Attribute):
            if node.attr in DANGEROUS_DUNDER_ATTRIBUTES:
                full = _get_full_attr_name(node)
                return False, f"Forbidden attribute access: {full}"

    return True, None


def _get_call_name(node: ast.Call) -> Optional[str]:
    """Best-effort function name extraction from a Call node."""
    if isinstance(node.func, ast.Name):
        return node.func.id
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    return None


def _get_full_attr_name(node: ast.expr) -> str:
    """Reconstruct a dotted attribute name like 'foo.bar.__class__'."""
    parts: list[str] = []
    current: ast.expr = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if isinstance(current, ast.Name):
        parts.append(current.id)
    return ".".join(reversed(parts))
