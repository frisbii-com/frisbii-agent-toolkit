"""Heuristic pre-go-live scan of a codebase integrating Frisbii Billing / Pay.

    python3 scan.py <repo-path> [--json]

Flags candidates for human/agent review. Never prints secret values: matches on
secret patterns are reported as file:line only. Standard library only.
"""

import argparse
import json
import os
import re
import sys

SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv", "venv", "__pycache__", ".next", "target"}
CODE_EXT = {
    ".py", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".php", ".rb", ".java", ".kt", ".cs", ".go",
    ".env", ".yml", ".yaml", ".json", ".properties", ".ini", ".toml", ".html", ".vue", ".svelte",
}
MAX_BYTES = 1_000_000

# (id, severity, description, regex, redact)
LINE_RULES = [
    ("hardcoded-private-key", "blocking",
     "Frisbii private key literal in source; load from secret store instead",
     re.compile(r"priv_[0-9a-f]{32}"), True),
    ("hardcoded-webhook-secret", "blocking",
     "Webhook secret assigned a literal; load from secret store instead",
     re.compile(r"webhook_?secret\w*\W{0,4}[:=]\s*['\"][^'\"]{16,}['\"]|webhook_secret_[0-9a-f]{32}", re.I), True),
    ("test-card-number", "warning",
     "Test card number outside tests",
     re.compile(r"\b4111[ -]?1111[ -]?1111[ -]?1111\b"), False),
    ("float-money", "blocking",
     "Possible float arithmetic on money (amount * 100 / parseFloat / round)",
     re.compile(r"(amount|price|total)\w*\s*\*\s*100(\.0)?\b|parseFloat\([^)]*(amount|price|total)", re.I), False),
    ("random-handle", "blocking",
     "Random/time-based handle for charges or orders; retries may double-charge",
     re.compile(r"handle\W{0,6}[:=]\s*[^,\n]*(uuid|random|Math\.random|Date\.now|time\(\)|now\(\))", re.I), False),
    ("accept-url-trust", "warning",
     "accept_url handler may mark orders paid from query parameters; confirm server-side",
     re.compile(r"(accept|success)\w*.*(mark\w*paid|status\s*=\s*['\"]paid|set_paid|fulfil)", re.I), False),
    ("activate-on-subscription-created", "warning",
     "Access may be granted on subscription_created; grant it on a settled invoice or active state",
     re.compile(r"subscription_created.{0,80}(activat|grant|provision|unlock|paid)"
                r"|(activat|grant|provision|unlock)\w*.{0,80}subscription_created", re.I), False),
    ("bearer-auth", "warning",
     "Frisbii uses HTTP Basic auth (private key as username, empty password), not Bearer",
     re.compile(r"Bearer\b.{0,60}(priv_|reepay|frisbii)|(priv_|reepay|frisbii)\w*.{0,60}\bBearer\b", re.I), True),
    ("email-as-handle", "warning",
     "Email address used as a handle; handles end up in URLs, use your own customer ID",
     re.compile(r"handle\W{0,6}[:=]\s*[^,\n]*\bemail", re.I), False),
    ("empty-alternative-return-url", "warning",
     "alternative_return_url set to an empty string; use the app's URL scheme or omit it",
     re.compile(r"alternative_return_url\W{0,6}[:=]\s*(''|\"\")", re.I), False),
    ("internal-card-endpoint", "warning",
     "References Checkout's internal card host; confirm no card numbers are sent from your code",
     re.compile(r"card\.reepay\.com", re.I), False),
]

# Applied only to files that handle webhook events.
WEBHOOK_LINE_RULES = [
    ("strict-webhook-schema", "warning",
     "Webhook payload validated strictly; new fields Frisbii adds would be rejected, ignore unknown fields",
     re.compile(r"additionalProperties['\"]?\s*:\s*false|\.strict\(\)|FAIL_ON_UNKNOWN_PROPERTIES\W+true"
                r"|extra\s*=\s*['\"]forbid|DisallowUnknownFields|MissingMemberHandling\.Error", re.I), False),
]

# A line matching any of these is never printed, whichever rule flagged it.
SECRET_MARKERS = [rx for _, _, _, rx, redact in LINE_RULES if redact]

CHARGE_SESSION_MARKERS = re.compile(r"session/charge|ChargeSession|charge_session", re.I)
SETTLE_MARKERS = re.compile(r"\bsettle\b", re.I)
FRISBII_MARKERS = re.compile(r"api\.reepay\.com|checkout-api\.reepay\.com|checkout\.reepay\.com|frisbii", re.I)
# Frisbii event names mark a webhook handler on their own; a bare event_type only
# counts in files that reference Frisbii (other providers use the same field name).
FRISBII_EVENT_MARKERS = re.compile(r"invoice_(settled|authorized)|subscription_(created|expired|renewal)")
EVENT_TYPE_MARKER = re.compile(r"event_type")
SIGNATURE_MARKERS = re.compile(r"hmac|HmacSHA256|hash_hmac|createHmac|HMACSHA256|verify_frisbii_webhook|verifyFrisbiiWebhook", re.I)
TIMEOUT_MARKERS = re.compile(r"timeout", re.I)
# Hosts that take API calls. checkout.frisbii.com (the JS) and app.frisbii.com (admin) do not.
API_HOSTS = re.compile(r"\b(api|checkout-api|customer-portal-api)\.(reepay|frisbii)\.com", re.I)
# Configuration files name the host but make no HTTP calls, so the timeout check skips them.
CONFIG_EXT = {".env", ".yml", ".yaml", ".json", ".properties", ".ini", ".toml"}

SLASH_COMMENT_EXT = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".php", ".java", ".kt", ".cs", ".go",
                     ".vue", ".svelte"}
HASH_COMMENT_EXT = {".py", ".rb", ".yml", ".yaml", ".toml", ".ini", ".properties", ".php"}
BLOCK_COMMENT = re.compile(r"/\*.*?\*/", re.S)
LINE_COMMENT = re.compile(r"(?<![:\w\"'`])//[^\n]*")
HASH_COMMENT = re.compile(r"(?m)(^|\s)#[^\n]*")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)


def strip_comments(text: str, name: str) -> str:
    """Drop comments so file-level checks look at code, not prose about it."""
    ext = os.path.splitext(name)[1].lower()
    if ext in SLASH_COMMENT_EXT:
        text = LINE_COMMENT.sub("", BLOCK_COMMENT.sub("", text))
    if ext in HASH_COMMENT_EXT or name.startswith(".env"):
        text = HASH_COMMENT.sub(r"\1", text)
    if ext in {".html", ".vue", ".svelte", ".php"}:
        text = HTML_COMMENT.sub("", text)
    return text


def is_test_path(path: str) -> bool:
    # Leading slash so a top-level tests/ or spec/ directory matches too.
    p = "/" + path.lower().replace(os.sep, "/")
    return any(t in p for t in ("/test", "/tests", "/spec", "__tests__", "_test.", ".test.", ".spec."))


def is_config_file(name: str) -> bool:
    return os.path.splitext(name)[1].lower() in CONFIG_EXT or name.startswith(".env")


def iter_files(root: str):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            ext = os.path.splitext(name)[1].lower()
            if ext in CODE_EXT or name.startswith(".env"):
                path = os.path.join(dirpath, name)
                try:
                    if os.path.getsize(path) <= MAX_BYTES:
                        yield path
                except OSError:
                    continue


def scan(root: str) -> dict:
    findings = []
    frisbii_files = []
    webhook_files_without_sig = []
    for path in iter_files(root):
        rel = os.path.relpath(path, root)
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                text = f.read()
        except OSError:
            continue
        uses_frisbii = bool(FRISBII_MARKERS.search(text))
        if uses_frisbii:
            frisbii_files.append(rel)
        name = os.path.basename(path)
        code = strip_comments(text, name)
        handles_webhooks = (bool(FRISBII_EVENT_MARKERS.search(code))
                            or (uses_frisbii and bool(EVENT_TYPE_MARKER.search(code)))) and not is_test_path(rel)
        rules = LINE_RULES + (WEBHOOK_LINE_RULES if handles_webhooks else [])
        for lineno, line in enumerate(text.splitlines(), 1):
            has_secret = any(rx.search(line) for rx in SECRET_MARKERS)
            for rule_id, severity, desc, rx, redact in rules:
                if rule_id == "test-card-number" and is_test_path(rel):
                    continue
                if rx.search(line):
                    findings.append({
                        "rule": rule_id, "severity": severity, "file": rel, "line": lineno,
                        "description": desc,
                        "snippet": None if redact or has_secret else line.strip()[:160],
                    })
        if handles_webhooks and not SIGNATURE_MARKERS.search(code):
            webhook_files_without_sig.append(rel)
        if API_HOSTS.search(code) and not TIMEOUT_MARKERS.search(code) and not is_config_file(name):
            findings.append({
                "rule": "no-timeout", "severity": "warning", "file": rel, "line": None,
                "description": "File calls Frisbii API but no timeout is visible; set explicit HTTP timeouts",
                "snippet": None,
            })
        if CHARGE_SESSION_MARKERS.search(code) and not SETTLE_MARKERS.search(code) and not is_test_path(rel):
            findings.append({
                "rule": "charge-session-without-settle", "severity": "warning", "file": rel, "line": None,
                "description": "Creates charge sessions but never sets settle; set it explicitly (false for physical goods)",
                "snippet": None,
            })
    for rel in webhook_files_without_sig:
        findings.append({
            "rule": "webhook-without-signature-check", "severity": "blocking", "file": rel, "line": None,
            "description": "Handles webhook events but no HMAC verification found in this file; confirm verification happens upstream",
            "snippet": None,
        })
    return {"root": os.path.abspath(root), "frisbii_files": sorted(frisbii_files), "findings": findings}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    result = scan(a.root)
    if a.json:
        json.dump(result, sys.stdout, indent=2)
        print()
        return
    print(f"Files referencing Frisbii: {len(result['frisbii_files'])}")
    for f in result["frisbii_files"][:50]:
        print(f"  {f}")
    order = {"blocking": 0, "warning": 1}
    print(f"\nFindings: {len(result['findings'])} (heuristic: confirm each by reading the code)")
    for x in sorted(result["findings"], key=lambda x: (order.get(x["severity"], 9), x["file"], x["line"] or 0)):
        loc = f"{x['file']}:{x['line']}" if x["line"] else x["file"]
        print(f"[{x['severity'].upper()}] {x['rule']} {loc}\n    {x['description']}")
        if x["snippet"]:
            print(f"    > {x['snippet']}")


if __name__ == "__main__":
    main()
