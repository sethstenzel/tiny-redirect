"""Pytest fixtures for TinyRedirect tests."""

import pytest
import tempfile
import os
from tiny_redirect import data
from tiny_redirect.app import app, generate_csrf_token, csrf_tokens


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Initialize the database
    data.database_init(db_path)

    yield db_path

    # Cleanup
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def test_client(temp_db):
    """Create a test client with a temporary database."""
    import tiny_redirect.app as app_module

    # Set the database path for the app
    original_db_path = app_module.db_path
    app_module.db_path = temp_db

    # Create test client
    from webtest import TestApp
    client = TestApp(app)

    yield client

    # Restore original db path
    app_module.db_path = original_db_path


@pytest.fixture
def csrf_token():
    """Generate a valid CSRF token for testing."""
    token = generate_csrf_token()
    return token


@pytest.fixture
def clear_csrf_tokens():
    """Clear all CSRF tokens before test."""
    csrf_tokens.clear()
    yield
    csrf_tokens.clear()
