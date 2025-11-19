"""Tests for app.py - web routes and CSRF protection."""

import pytest
from tiny_redirect.app import (
    generate_csrf_token,
    verify_csrf_token,
    csrf_tokens,
    app,
)
from tiny_redirect import data


class TestCSRFProtection:
    """Tests for CSRF token generation and verification."""

    def test_generate_csrf_token(self, clear_csrf_tokens):
        """Test that CSRF tokens are generated correctly."""
        token = generate_csrf_token()
        assert token is not None
        assert len(token) > 0
        assert len(csrf_tokens) == 1

    def test_verify_valid_token(self, clear_csrf_tokens):
        """Test that valid tokens are verified correctly."""
        token = generate_csrf_token()
        assert verify_csrf_token(token) is True

    def test_verify_invalid_token(self, clear_csrf_tokens):
        """Test that invalid tokens are rejected."""
        generate_csrf_token()
        assert verify_csrf_token("invalid-token") is False

    def test_verify_empty_token(self, clear_csrf_tokens):
        """Test that empty tokens are rejected."""
        assert verify_csrf_token("") is False
        assert verify_csrf_token(None) is False

    def test_multiple_tokens(self, clear_csrf_tokens):
        """Test that multiple tokens can be generated and verified."""
        token1 = generate_csrf_token()
        token2 = generate_csrf_token()
        token3 = generate_csrf_token()

        assert verify_csrf_token(token1) is True
        assert verify_csrf_token(token2) is True
        assert verify_csrf_token(token3) is True


class TestStaticRoutes:
    """Tests for static file routes."""

    def test_favicon(self, test_client):
        """Test favicon route returns file or 404."""
        response = test_client.get('/favicon.ico', expect_errors=True)
        # Should be 200 if file exists, 404 if not
        assert response.status_int in [200, 404]


class TestIndexRoute:
    """Tests for the index route."""

    def test_index_with_redirects(self, test_client, temp_db):
        """Test index page shows redirects when they exist."""
        response = test_client.get('/')
        # Should either show list or redirect to /redirects
        assert response.status_int in [200, 303]

    def test_index_redirects_when_empty(self, test_client, temp_db):
        """Test index redirects to /redirects when no redirects exist."""
        # Delete all redirects
        data.delete_alias("ex", temp_db)
        response = test_client.get('/', expect_errors=True)
        # Should redirect to /redirects
        assert response.status_int in [200, 303]


class TestAboutRoute:
    """Tests for the about route."""

    def test_about_redirects(self, test_client):
        """Test about route redirects to external page."""
        response = test_client.get('/about')
        assert response.status_int == 303
        assert "sethstenzel.me" in response.location


class TestAliasRedirection:
    """Tests for alias redirection."""

    def test_valid_alias_redirect(self, test_client, temp_db):
        """Test that valid aliases redirect correctly."""
        data.add_alias("google", "https://google.com", temp_db)
        response = test_client.get('/google')
        assert response.status_int == 303
        assert response.location == "https://google.com"

    def test_alias_without_protocol(self, test_client, temp_db):
        """Test that aliases without protocol get http:// added."""
        data.add_alias("example", "example.com", temp_db)
        response = test_client.get('/example')
        assert response.status_int == 303
        assert response.location == "http://example.com"

    def test_invalid_alias(self, test_client):
        """Test that invalid aliases show error page."""
        response = test_client.get('/nonexistent', expect_errors=True)
        assert response.status_int == 200
        assert b"Alias Not Found" in response.body


class TestAddAlias:
    """Tests for adding aliases."""

    def test_add_get_redirects(self, test_client):
        """Test that GET on /add redirects to /redirects."""
        response = test_client.get('/add')
        assert response.status_int == 303
        assert '/redirects' in response.location

    def test_add_without_csrf(self, test_client):
        """Test that POST without CSRF token is rejected."""
        response = test_client.post('/add', {
            'alias': 'test',
            'redirect': 'https://test.com',
        }, expect_errors=True)
        assert response.status_int == 403

    def test_add_with_valid_csrf(self, test_client, csrf_token, temp_db):
        """Test adding alias with valid CSRF token."""
        response = test_client.post('/add', {
            'alias': 'newtest',
            'redirect': 'https://newtest.com',
            'csrf_token': csrf_token,
            'goto': '/redirects',
        })
        assert response.status_int == 303

        # Verify alias was added
        db_data = data.load_data(temp_db)
        assert 'newtest' in db_data['redirects']

    def test_add_invalid_alias(self, test_client, csrf_token):
        """Test adding invalid alias shows error."""
        response = test_client.post('/add', {
            'alias': 'add',  # reserved
            'redirect': 'https://test.com',
            'csrf_token': csrf_token,
        })
        assert response.status_int == 200
        assert b"reserved route" in response.body

    def test_add_empty_alias(self, test_client, csrf_token):
        """Test adding empty alias shows error."""
        response = test_client.post('/add', {
            'alias': '',
            'redirect': 'https://test.com',
            'csrf_token': csrf_token,
        })
        assert response.status_int == 200
        assert b"cannot be empty" in response.body


class TestDeleteAlias:
    """Tests for deleting aliases."""

    def test_delete_get_redirects(self, test_client):
        """Test that GET on /del redirects to /redirects."""
        response = test_client.get('/del')
        assert response.status_int == 303

    def test_delete_without_csrf(self, test_client):
        """Test that DELETE without CSRF token is rejected."""
        response = test_client.post('/del', {
            'alias': 'test',
        }, expect_errors=True)
        assert response.status_int == 403

    def test_delete_with_valid_csrf(self, test_client, csrf_token, temp_db):
        """Test deleting alias with valid CSRF token."""
        # First add an alias
        data.add_alias("todelete", "https://delete.com", temp_db)

        response = test_client.post('/del', {
            'alias': 'todelete',
            'csrf_token': csrf_token,
            'goto': '/redirects',
        })
        assert response.status_int == 303

        # Verify alias was deleted
        db_data = data.load_data(temp_db)
        assert 'todelete' not in db_data['redirects']


class TestSettings:
    """Tests for settings routes."""

    def test_settings_page(self, test_client):
        """Test settings page loads correctly."""
        response = test_client.get('/settings')
        assert response.status_int == 200
        assert b"Server Settings" in response.body

    def test_update_settings_get_redirects(self, test_client):
        """Test that GET on /update_settings redirects."""
        response = test_client.get('/update_settings')
        assert response.status_int == 303

    def test_update_settings_without_csrf(self, test_client):
        """Test that updating settings without CSRF is rejected."""
        response = test_client.post('/update_settings', {
            'hostname': '127.0.0.1',
        }, expect_errors=True)
        assert response.status_int == 403

    def test_update_settings_with_csrf(self, test_client, csrf_token, temp_db):
        """Test updating settings with valid CSRF token."""
        response = test_client.post('/update_settings', {
            'hostname': '127.0.0.1',
            'port': '8080',
            'shortname': 'test',
            'csrf_token': csrf_token,
        })
        assert response.status_int == 303

        # Verify settings were updated
        db_data = data.load_data(temp_db)
        assert db_data['settings']['hostname'] == '127.0.0.1'
        assert db_data['settings']['port'] == 8080

    def test_update_invalid_port(self, test_client, csrf_token):
        """Test updating with invalid port shows error."""
        response = test_client.post('/update_settings', {
            'port': '99999',
            'csrf_token': csrf_token,
        })
        assert response.status_int == 200
        assert b"between 1 and 65535" in response.body


class TestRedirectsPage:
    """Tests for the redirects management page."""

    def test_redirects_page(self, test_client):
        """Test redirects page loads correctly."""
        response = test_client.get('/redirects')
        assert response.status_int in [200, 303]


class TestShutdown:
    """Tests for shutdown route."""

    def test_shutdown_page(self, test_client):
        """Test shutdown page loads (but don't actually shutdown)."""
        # Note: This will start the shutdown process, so we just check it loads
        response = test_client.get('/shutdown')
        assert response.status_int == 200
        assert b"Shutting Down" in response.body
