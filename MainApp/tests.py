from pathlib import Path

from django.conf import settings
from django.template.loader import get_template
from django.test import SimpleTestCase


class HomePageTests(SimpleTestCase):
    def test_home_uses_the_shared_layout_and_namespaced_page(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "base.html")
        self.assertTemplateUsed(response, "MainApp/home.html")
        self.assertEqual(
            Path(get_template("base.html").origin.name),
            settings.BASE_DIR / "templates" / "base.html",
        )
