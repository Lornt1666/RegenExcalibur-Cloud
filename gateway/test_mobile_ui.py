import pathlib
import unittest


class MobileGatewayUITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (pathlib.Path(__file__).parent / "web" / "index.html").read_text(encoding="utf-8")

    def test_mobile_viewport_and_accessible_status_are_present(self):
        self.assertIn('name="viewport"', self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn('@media(min-width:620px)', self.html)

    def test_ui_does_not_persist_access_token_in_browser_storage(self):
        self.assertNotIn("localStorage", self.html)
        self.assertNotIn("sessionStorage", self.html)
        self.assertIn('credentials:"omit"', self.html)
        self.assertIn('cache:"no-store"', self.html)

    def test_user_controlled_values_are_rendered_as_text_not_html(self):
        self.assertIn("$(id).textContent", self.html)
        self.assertNotIn("innerHTML", self.html)

    def test_ui_explicitly_disclaims_provider_dispatch_and_production_auth(self):
        self.assertIn("never executes provider operations", self.html)
        self.assertIn("development/testing only", self.html)
        self.assertIn("does not supply an identity provider", self.html)


if __name__ == "__main__":
    unittest.main()
