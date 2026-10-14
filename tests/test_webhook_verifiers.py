"""Check the webhook verifiers agree on a known signature.

    python3 -m unittest discover -s tests
"""

import hashlib
import hmac
import importlib.util
import json
import os
import shutil
import subprocess
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(ROOT, "plugins", "frisbii", "skills", "frisbii-webhooks", "scripts")

SECRET = "webhook-secret-for-tests"
PAYLOAD = {"id": "8ab4b56439944e62ababca7954355578", "timestamp": "2015-06-25T12:10:00.64Z",
           "event_type": "invoice_settled", "invoice": "order-1001"}
PAYLOAD["signature"] = hmac.new(SECRET.encode(), (PAYLOAD["timestamp"] + PAYLOAD["id"]).encode(),
                                hashlib.sha256).hexdigest()


def load_py():
    spec = importlib.util.spec_from_file_location("verify_webhook", os.path.join(SCRIPTS, "verify_webhook.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class VerifierTest(unittest.TestCase):
    def test_python(self):
        v = load_py()
        self.assertTrue(v.verify_frisbii_webhook(PAYLOAD, SECRET))
        self.assertFalse(v.verify_frisbii_webhook({**PAYLOAD, "id": "x"}, SECRET))
        self.assertFalse(v.verify_frisbii_webhook({**PAYLOAD, "signature": "0" * 64}, SECRET))
        self.assertFalse(v.verify_frisbii_webhook({"id": "x"}, SECRET))

    @unittest.skipUnless(shutil.which("node"), "node not installed")
    def test_node(self):
        code = (f"const v=require({json.dumps(os.path.join(SCRIPTS, 'verify_webhook.js'))});"
                f"const p={json.dumps(PAYLOAD)};"
                f"process.exit(v.verifyFrisbiiWebhook(p,{json.dumps(SECRET)}) && "
                f"!v.verifyFrisbiiWebhook({{...p,id:'x'}},{json.dumps(SECRET)}) ? 0 : 1)")
        self.assertEqual(subprocess.run(["node", "-e", code]).returncode, 0)

    @unittest.skipUnless(shutil.which("php"), "php not installed")
    def test_php(self):
        code = (f"require {json.dumps(os.path.join(SCRIPTS, 'verify_webhook.php'))};"
                f"$p=json_decode({json.dumps(json.dumps(PAYLOAD))},true);"
                f"exit(verify_frisbii_webhook($p,{json.dumps(SECRET)})?0:1);")
        self.assertEqual(subprocess.run(["php", "-r", code]).returncode, 0)


if __name__ == "__main__":
    unittest.main()
