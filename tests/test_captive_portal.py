"""Tests for captive portal redirect behavior."""

import pytest

from lichtkrant.config import Config
from lichtkrant.web import create_app


@pytest.fixture
def config():
    return Config()


@pytest.fixture
def portal_app(config):
    """Flask app with captive portal enabled."""
    app = create_app(config, portal_ip="10.42.0.1")
    app.config["TESTING"] = True
    return app


@pytest.fixture
def no_portal_app(config):
    """Flask app without captive portal (--no-wifi mode)."""
    app = create_app(config)
    app.config["TESTING"] = True
    return app


class TestCaptivePortalRedirect:
    def test_foreign_host_redirects_to_welcome(self, portal_app):
        """Request with a foreign Host header should redirect to /welcome."""
        with portal_app.test_client() as client:
            response = client.get(
                "/", headers={"Host": "captive.apple.com"}
            )
            assert response.status_code == 302
            assert response.headers["Location"] == "http://10.42.0.1:8080/welcome"

    def test_android_generate204_redirects_to_welcome(self, portal_app):
        """Android connectivity check should redirect to /welcome."""
        with portal_app.test_client() as client:
            response = client.get(
                "/generate_204",
                headers={"Host": "connectivitycheck.gstatic.com"},
            )
            assert response.status_code == 302
            assert response.headers["Location"] == "http://10.42.0.1:8080/welcome"

    def test_portal_ip_host_passes_through(self, portal_app):
        """Request with the portal IP as Host should not redirect."""
        with portal_app.test_client() as client:
            response = client.get("/", headers={"Host": "10.42.0.1:8080"})
            assert response.status_code == 200

    def test_localhost_passes_through(self, portal_app):
        """Request with localhost Host should not redirect."""
        with portal_app.test_client() as client:
            response = client.get("/", headers={"Host": "localhost:8080"})
            assert response.status_code == 200

    def test_loopback_passes_through(self, portal_app):
        """Request with 127.0.0.1 Host should not redirect."""
        with portal_app.test_client() as client:
            response = client.get("/", headers={"Host": "127.0.0.1:8080"})
            assert response.status_code == 200

    def test_portal_disabled_no_redirect(self, no_portal_app):
        """With portal_ip=None, no redirects should happen."""
        with no_portal_app.test_client() as client:
            response = client.get(
                "/", headers={"Host": "captive.apple.com"}
            )
            assert response.status_code == 200

    def test_windows_ncsi_redirects(self, portal_app):
        """Windows NCSI probe should redirect."""
        with portal_app.test_client() as client:
            response = client.get(
                "/ncsi.txt",
                headers={"Host": "www.msftncsi.com"},
            )
            assert response.status_code == 302

    def test_welcome_page_renders(self, portal_app):
        """The /welcome page renders with a link to the dashboard."""
        with portal_app.test_client() as client:
            response = client.get(
                "/welcome", headers={"Host": "10.42.0.1:8080"}
            )
            assert response.status_code == 200
            html = response.data.decode()
            assert 'href="/"' in html
            assert "Lichtkrant" in html

    def test_welcome_accessible_without_portal(self, no_portal_app):
        """The /welcome page works even without captive portal."""
        with no_portal_app.test_client() as client:
            response = client.get("/welcome")
            assert response.status_code == 200

    def test_firefox_redirect(self, portal_app):
        """Firefox captive portal detection should redirect."""
        with portal_app.test_client() as client:
            response = client.get(
                "/success.txt",
                headers={"Host": "detectportal.firefox.com"},
            )
            assert response.status_code == 302
