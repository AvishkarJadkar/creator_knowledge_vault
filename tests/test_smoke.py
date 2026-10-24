"""Smoke tests for Vaulty.

Uses only the standard library, so it runs on a clean checkout with nothing
but ``requirements.txt`` installed:

    python -m unittest discover -s tests -v

Every test runs against a throwaway SQLite database and AI calls are mocked,
so the suite is offline, fast, and never touches ``instance/vault.db`` or
your API quota.
"""

import io
import os
import re
import shutil
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

# Configure the app *before* importing it.
_TMP_DIR = tempfile.mkdtemp(prefix="vaulty-tests-")
os.environ["FLASK_ENV"] = "development"
os.environ["SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "sqlite:///" + os.path.join(_TMP_DIR, "test.db").replace("\\", "/")

from app import app, init_db_schema  # noqa: E402
from extensions import db  # noqa: E402
from models import Content  # noqa: E402


class VaultySmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config.update(TESTING=True)
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.engine.dispose()
        shutil.rmtree(_TMP_DIR, ignore_errors=True)

    def setUp(self):
        # Lazy init runs on the first request; exercise it, then reset tables
        # so each test starts from an empty vault.
        with app.app_context():
            init_db_schema()
            db.drop_all()
            db.create_all()
        self.user_id = "test-user"
        self.login()

    # ---------- helpers ----------

    def login(self, user_id=None):
        self.user_id = user_id or self.user_id
        with self.client.session_transaction() as sess:
            sess["user_id"] = self.user_id
            sess["user_name"] = "Tester"
        page = self.client.get("/dashboard")
        match = re.search(r'name="csrf-token" content="([^"]+)"', page.get_data(as_text=True))
        self.assertIsNotNone(match, "dashboard should expose a CSRF meta tag")
        self.token = match.group(1)
        self.auth = {"X-CSRFToken": self.token}

    def post(self, path, data=None, **kwargs):
        payload = dict(data or {})
        payload.setdefault("csrf_token", self.token)
        return self.client.post(path, data=payload, **kwargs)

    def add_note(self, title="Test note", body="some body text"):
        with mock.patch("content.get_embedding", return_value=[0.1, 0.2, 0.3]):
            response = self.post(
                "/add",
                data={"title": title, "content_type": "note", "body": body, "youtube_url": ""},
            )
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            return Content.query.filter_by(user_id=self.user_id, title=title).first()

    # ---------- infrastructure ----------

    def test_health_reports_ok(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_health_reports_database_failure(self):
        with mock.patch.object(db.session, "execute", side_effect=RuntimeError("db down")):
            with self.assertLogs("app", level="ERROR"):
                response = self.client.get("/health")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["database"], "unavailable")

    def test_security_headers_present(self):
        headers = self.client.get("/login").headers
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["X-Frame-Options"], "DENY")

    def test_error_pages(self):
        response = self.client.get("/no-such-page")
        self.assertEqual(response.status_code, 404)
        self.assertIn("Page not found", response.get_data(as_text=True))

        response = self.client.get("/no-such-page", headers={"X-Requested-With": "XMLHttpRequest"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.get_json())

    def test_csrf_is_enforced(self):
        response = self.client.post("/add", data={"title": "x"})
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/add", data={"title": "x"}, headers={"X-Requested-With": "XMLHttpRequest"}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    # ---------- public + authenticated pages ----------

    def test_public_pages_render(self):
        anonymous = app.test_client()
        for path in ("/", "/login", "/signup"):
            with self.subTest(path=path):
                self.assertEqual(anonymous.get(path).status_code, 200)

    def test_home_redirects_logged_in_users(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])

    def test_protected_pages_redirect_anonymous(self):
        anonymous = app.test_client()
        response = anonymous.get("/dashboard")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])

    def test_authenticated_pages_render(self):
        for path in ("/dashboard", "/add", "/search", "/explore", "/chat", "/settings", "/onboarding"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    # ---------- content ----------

    def test_add_and_view_content(self):
        content = self.add_note(title="My first note", body="hello vault")
        self.assertIsNotNone(content)

        response = self.client.get(f"/content/{content.id}")
        self.assertEqual(response.status_code, 200)
        page = response.get_data(as_text=True)
        self.assertIn("My first note", page)
        self.assertIn("badge-note", page)

    def test_add_rejects_unknown_content_type(self):
        response = self.post(
            "/add",
            data={"title": "Bad", "content_type": "<script>", "body": "x", "youtube_url": ""},
        )
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertIsNone(Content.query.filter_by(title="Bad").first())

    def test_add_rejects_corrupt_pdf_without_500(self):
        response = self.post(
            "/add",
            data={
                "title": "Broken PDF",
                "content_type": "pdf",
                "body": "",
                "youtube_url": "",
                "file": (io.BytesIO(b"not a real pdf"), "broken.pdf"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            self.assertIsNone(Content.query.filter_by(title="Broken PDF").first())

    def test_add_accepts_non_utf8_text_file(self):
        with mock.patch("content.get_embedding", return_value=[0.1, 0.2, 0.3]):
            response = self.post(
                "/add",
                data={
                    "title": "Latin-1 note",
                    "content_type": "note",
                    "body": "",
                    "youtube_url": "",
                    "file": (io.BytesIO(b"caf\xe9 au lait"), "latin1.txt"),
                },
                content_type="multipart/form-data",
            )
        self.assertEqual(response.status_code, 302)
        with app.app_context():
            content = Content.query.filter_by(title="Latin-1 note").first()
        self.assertIsNotNone(content)
        self.assertIn("café", content.body)

    def test_restore_all_validates_payload(self):
        content = self.add_note()
        with app.app_context():
            db.session.get(Content, content.id).is_deleted = True
            db.session.commit()

        response = self.client.post(
            "/content/restore_all", json={"content_ids": "not-a-list"}, headers=self.auth
        )
        self.assertEqual(response.status_code, 400)

        response = self.client.post(
            "/content/restore_all", json={"content_ids": [content.id]}, headers=self.auth
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])
        with app.app_context():
            self.assertFalse(db.session.get(Content, content.id).is_deleted)

    # ---------- search ----------

    def test_search_snippets_are_centred_on_the_match(self):
        self.add_note(title="Snippet note", body=("A" * 400) + " needle here " + ("B" * 400))

        with mock.patch("search.get_embedding", return_value=None):
            page = self.client.get("/search?q=needle").get_data(as_text=True)
            self.assertIn("needle here", page)
            self.assertIn("...", page)

            response = self.client.post(
                "/search",
                data={"query": "needle"},
                headers={"X-Requested-With": "XMLHttpRequest", **self.auth},
            )
        self.assertEqual(response.status_code, 200)
        results = response.get_json()["results"]
        self.assertTrue(results)
        snippet = results[0]["body_snippet"]
        self.assertIn("needle", snippet)
        self.assertTrue(snippet.startswith("..."))

    # ---------- onboarding / settings ----------

    def test_onboarding_redirects_to_dashboard_when_requested(self):
        with mock.patch("settings.resolve_channel_id", return_value="UC123"):
            response = self.post(
                "/settings/add-profile",
                data={"platform": "youtube", "profile_url": "https://youtube.com/@tester",
                      "next": "dashboard"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])

    def test_settings_redirect_after_profile_without_next(self):
        with mock.patch("settings.resolve_channel_id", return_value="UC123"):
            response = self.post(
                "/settings/add-profile",
                data={"platform": "youtube", "profile_url": "https://youtube.com/@tester"},
            )
        self.assertEqual(response.status_code, 302)
        self.assertIn("/settings", response.headers["Location"])

    # ---------- auth ----------

    def test_logout_requires_post_and_csrf(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)
        self.assertEqual(self.client.post("/logout", data={}).status_code, 400)

        response = self.client.post("/logout", data={"csrf_token": self.token})
        self.assertEqual(response.status_code, 302)
        with self.client.session_transaction() as sess:
            self.assertNotIn("user_id", sess)


if __name__ == "__main__":
    unittest.main(verbosity=2)
