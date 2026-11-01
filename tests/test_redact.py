from __future__ import annotations

import os
import time
import unittest

from edlib.redact import redact


class RedactTests(unittest.TestCase):
    def test_aws_access_key(self):
        fake_key = "AKIA" + "IOSFODNN7EXAMPLE"
        s = redact("id " + fake_key + " extra")
        self.assertIn("[REDACTED:aws_access_key]", s)
        self.assertNotIn(fake_key, s)

    def test_aws_secret(self):
        fake_sec = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        s = redact("aws_secret_access_key = " + fake_sec)
        self.assertIn("[REDACTED:aws_secret]", s)

    def test_github_token(self):
        fake_tok = "ghp_" + "abcdefghijklmnopqrstuvwxyz0123456789"
        s = redact("tok " + fake_tok)
        self.assertIn("[REDACTED:github_token]", s)

    def test_github_pat(self):
        fake_pat = "github_pat_" + "abcdefghijklmnopqrstuvwxyz0123456789ABCD"
        s = redact(fake_pat)
        self.assertIn("[REDACTED:github_pat]", s)

    def test_openai_key(self):
        fake_key = "sk-" + "abcdefghijklmnopqrstuvwxyz0123456789ABCD"
        s = redact(fake_key)
        self.assertIn("[REDACTED:openai_key]", s)

    def test_anthropic_key(self):
        fake_key = "sk-ant-" + "abcdefghijklmnopqrstuvwxyz0123456789"
        s = redact(fake_key)
        self.assertIn("[REDACTED:anthropic_key]", s)

    def test_slack_token(self):
        fake_tok = "xoxb-" + "1234567890-abcdefghijk"
        s = redact(fake_tok)
        self.assertIn("[REDACTED:slack_token]", s)

    def test_stripe_key(self):
        fake_key = "sk_live_" + "abcdefghijklmnopqrstuv"
        s = redact(fake_key)
        self.assertIn("[REDACTED:stripe_key]", s)

    def test_google_api_key(self):
        s = redact("AIzaSyA" + ("a" * 29) + "12345")
        # AIza + 35 chars
        key = "AIza" + ("B" * 35)
        s = redact("use " + key)
        self.assertIn("[REDACTED:google_api_key]", s)

    def test_jwt(self):
        s = redact("eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0In0.abc_def-ghi")
        self.assertIn("[REDACTED:jwt]", s)

    def test_auth_bearer(self):
        s = redact("Authorization: Bearer abcdefghijklmnop")
        self.assertIn("[REDACTED:auth_header]", s)
        self.assertNotIn("abcdefghijklmnop", s)

    def test_pem_private(self):
        pem = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKABCNOTAREALKEY\n-----END RSA PRIVATE KEY-----"
        s = redact(pem)
        self.assertIn("[REDACTED:pem_private]", s)

    def test_url_password(self):
        s = redact("https://user:supersecret@example.com/x")
        self.assertIn("[REDACTED:url_password]", s)
        self.assertNotIn("supersecret", s)

    def test_key_value(self):
        s = redact("password=hunter2plus")
        self.assertIn("[REDACTED:key_value]", s)
        self.assertNotIn("hunter2plus", s)

    def test_env_value(self):
        os.environ["ED_TEST_SECRET_XYZ"] = "uniquesecretvalue99"
        try:
            s = redact("leak uniquesecretvalue99 here")
            self.assertIn("[REDACTED:env]", s)
            self.assertNotIn("uniquesecretvalue99", s)
        finally:
            del os.environ["ED_TEST_SECRET_XYZ"]

    def test_no_raise_random_bytes(self):
        blob = bytes(range(256)).decode("latin1")
        out = redact(blob)
        self.assertIsInstance(out, str)

    def test_linear_time_1mb(self):
        # adversarial-ish: lots of password= prefixes and near-JWTs
        chunk = "password=" + ("a" * 100) + " eyJaaaa." * 10 + " AKIA" + "Z" * 20
        text = chunk * (1024 * 1024 // len(chunk) + 1)
        text = text[: 1024 * 1024]
        t0 = time.time()
        out = redact(text)
        dt = time.time() - t0
        self.assertIsInstance(out, str)
        self.assertLess(dt, 5.0)


if __name__ == "__main__":
    unittest.main()
