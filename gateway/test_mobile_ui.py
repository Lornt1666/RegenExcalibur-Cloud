import pathlib
import unittest


class MobileGatewayUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = pathlib.Path(__file__).parent / "web"
        cls.html = (root / "index.html").read_text(encoding="utf-8")
        cls.js = (root / "app.js").read_text(encoding="utf-8")
        cls.css = (root / "style.css").read_text(encoding="utf-8")

    def test_mobile_viewport_and_accessible_status_are_present(self):
        self.assertIn('name="viewport"', self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn('@media(min-width:620px)', self.css)

    def test_strict_csp_and_no_browser_storage_for_tokens(self):
        self.assertIn("script-src 'self'", self.html)
        self.assertIn("style-src 'self'", self.html)
        csp = self.html.split("Content-Security-Policy", 1)[1].split(">", 1)[0]
        self.assertNotIn("unsafe-inline", csp)
        self.assertNotIn("localStorage", self.html + self.js)
        self.assertNotIn("sessionStorage", self.html + self.js)
        self.assertIn('credentials:"omit"', self.js)
        self.assertIn('cache:"no-store"', self.js)
        self.assertIn('rel="stylesheet" href="style.css"', self.html)

    def test_user_controlled_values_are_rendered_as_text_not_html(self):
        self.assertIn("$(id).textContent", self.js)
        self.assertNotIn("innerHTML", self.html + self.js)

    def test_ui_explicitly_disclaims_provider_dispatch_and_production_auth(self):
        self.assertIn("never executes provider operations", self.html)
        self.assertIn("development/testing only", self.html)
        self.assertIn("does not supply an identity provider", self.html)


if __name__ == "__main__":
    unittest.main()
