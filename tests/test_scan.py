"""Check the go-live scanner flags known mistakes and stays quiet on clean code.

    python3 -m unittest discover -s tests
"""

import importlib.util
import os
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCAN = os.path.join(ROOT, "plugins", "frisbii", "skills", "frisbii-go-live-review", "scripts", "scan.py")


def load_scan():
    spec = importlib.util.spec_from_file_location("scan", SCAN)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def rules_for(files):
    scan = load_scan()
    with tempfile.TemporaryDirectory() as root:
        for rel, text in files.items():
            path = os.path.join(root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        return {x["rule"] for x in scan.scan(root)["findings"]}


class ScanTest(unittest.TestCase):
    def test_flags_new_mistakes(self):
        found = rules_for({
            "app/payments.js": (
                "const client = axios.create({ baseURL: 'https://api.frisbii.com', timeout: 5000,\n"
                "  headers: { Authorization: `Bearer ${process.env.FRISBII_KEY}` } });\n"
                "const customer = { handle: user.email };\n"
                "const session = { alternative_return_url: '' };\n"
                "post('https://checkout-api.reepay.com/v1/session/charge', session);\n"
                "post('https://card.reepay.com/v1/token', pan);\n"
            ),
            "app/webhooks.py": (
                "class Event(BaseModel):\n"
                "    model_config = ConfigDict(extra='forbid')\n"
                "def handle(event):\n"
                "    if event.event_type == 'subscription_created': grant_access(event.customer)\n"
                "    verify_frisbii_webhook(event)\n"
            ),
        })
        for rule in ("bearer-auth", "email-as-handle", "empty-alternative-return-url",
                     "charge-session-without-settle", "internal-card-endpoint",
                     "strict-webhook-schema", "activate-on-subscription-created"):
            self.assertIn(rule, found)

    def test_clean_code_has_no_new_findings(self):
        found = rules_for({
            "app/payments.js": (
                "const client = axios.create({ baseURL: 'https://api.frisbii.com', timeout: 5000,\n"
                "  auth: { username: process.env.FRISBII_KEY, password: '' } });\n"
                "const customer = { handle: `cust-${user.id}` };\n"
                "const session = { settle: false, alternative_return_url: 'myapp://return' };\n"
                "post('https://checkout-api.reepay.com/v1/session/charge', session);\n"
            ),
            "app/webhooks.py": (
                "def handle(event):\n"
                "    verify_frisbii_webhook(event)\n"
                "    if event.event_type == 'invoice_settled': queue(event.invoice)\n"
            ),
        })
        self.assertEqual(found, set())

    def test_strict_schema_only_flagged_in_webhook_files(self):
        found = rules_for({"app/forms.ts": "const Signup = z.object({ name: z.string() }).strict();\n"})
        self.assertNotIn("strict-webhook-schema", found)

    def test_bearer_finding_hides_snippet(self):
        scan = load_scan()
        with tempfile.TemporaryDirectory() as root:
            with open(os.path.join(root, "a.py"), "w") as f:
                f.write("h = {'Authorization': 'Bearer priv_0123456789abcdef0123456789abcdef'}\n")
            findings = scan.scan(root)["findings"]
        self.assertTrue(findings)
        self.assertTrue(all(x["snippet"] is None for x in findings if x["rule"] in ("bearer-auth", "hardcoded-private-key")))


if __name__ == "__main__":
    unittest.main()
