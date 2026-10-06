"""Verify development-only reload behavior in fresh Django processes."""

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import unittest


ROOT = Path(__file__).resolve().parent.parent


class BrowserReloadConfigurationTests(unittest.TestCase):
    def test_reload_is_active_only_in_development(self):
        for debug in (True, False):
            with self.subTest(debug=debug):
                env = os.environ.copy()
                env.update(
                    DJANGO_SETTINGS_MODULE="Project.settings",
                    DJANGO_SECRET_KEY=secrets.token_urlsafe(64),
                    DJANGO_DEBUG=str(debug).lower(),
                    DJANGO_ALLOWED_HOSTS="testserver",
                    PYTHON_DOTENV_DISABLED="1",
                )
                result = subprocess.run(
                    [sys.executable, "-c", """
import json
import django
django.setup()
from django.conf import settings
from django.test import Client
from django.urls import resolve, Resolver404
response = Client().get('/', secure=True)
try:
    resolve('/__reload__/events/')
    route = True
except Resolver404:
    route = False
print(json.dumps({
    'status': response.status_code,
    'app': 'django_browser_reload' in settings.INSTALLED_APPS,
    'middleware': any('django_browser_reload' in name for name in settings.MIDDLEWARE),
    'script': b'django-browser-reload/reload-listener.js' in response.content,
    'route': route,
}))
"""], cwd=ROOT, env=env, capture_output=True, text=True, timeout=30,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                actual = json.loads(result.stdout)
                self.assertEqual(actual.pop("status"), 200)
                self.assertEqual(actual, dict.fromkeys(("app", "middleware", "script", "route"), debug))
