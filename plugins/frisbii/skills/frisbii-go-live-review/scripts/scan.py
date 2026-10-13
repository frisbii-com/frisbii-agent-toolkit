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
     re.compile(r"webhook_?secret\w*\W{0,4}[:=]\s*['\"][^'\"]{16,}['\"]", re.I), True),
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
]

FRISBII_MARKERS = re.compile(r"api\.reepay\.com|checkout-api\.reepay\.com|checkout\.reepay\.com|frisbii", re.I)
WEBHOOK_MARKERS = re.compile(r"event_type|invoice_settled|subscription_(created|expired|renewal)")
SIGNATURE_MARKERS = re.compile(r"hmac|HmacSHA256|hash_hmac|createHmac|HMACSHA256|verify_frisbii_webhook|verifyFrisbiiWebhook", re.I)
TIMEOUT_MARKERS = re.compile(r"timeout", re.I)


def is_test_path(path: str) -> bool:
    p = path.lower()
    return any(t in p for t in ("/test", "/tests", "/spec", "__tests__", "_test.", ".test.", ".spec."))


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
        for lineno, line in enumerate(text.splitlines(), 1):
            for rule_id, severity, desc, rx, redact in LINE_RULES:
                if rule_id == "test-card-number" and is_test_path(rel):
                    continue
                if rx.search(line):
                    findings.append({
                        "rule": rule_id, "severity": severity, "file": rel, "line": lineno,
                        "description": desc,
                        "snippet": None if redact else line.strip()[:160],
                    })
        if WEBHOOK_MARKERS.search(text) and not SIGNATURE_MARKERS.search(text) and not is_test_path(rel):
            webhook_files_without_sig.append(rel)
        if uses_frisbii and not TIMEOUT_MARKERS.search(text) and re.search(r"(reepay|frisbii)\.com", text):
            findings.append({
                "rule": "no-timeout", "severity": "warning", "file": rel, "line": None,
                "description": "File calls Frisbii API but no timeout is visible; set explicit HTTP timeouts",
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
