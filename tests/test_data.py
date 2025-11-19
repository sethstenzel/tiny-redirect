"""Tests for data.py - validation and database operations."""

import pytest
from tiny_redirect.data import (
    ValidationError,
    str_to_bool,
    validate_alias,
    validate_redirect,
    validate_port,
    validate_hostname,
    validate_shortname,
    add_alias,
    delete_alias,
    update_setting,
    load_data,
    database_init,
)


class TestStrToBool:
    """Tests for str_to_bool function."""

    def test_true_string(self):
        assert str_to_bool("True") is True
        assert str_to_bool("true") is True
        assert str_to_bool("TRUE") is True

    def test_false_string(self):
        assert str_to_bool("False") is False
        assert str_to_bool("false") is False
        assert str_to_bool("") is False

    def test_boolean_passthrough(self):
        assert str_to_bool(True) is True
        assert str_to_bool(False) is False

    def test_numeric_strings(self):
        assert str_to_bool("1") is True
        assert str_to_bool("0") is False

    def test_yes_no(self):
        assert str_to_bool("yes") is True
        assert str_to_bool("no") is False


class TestValidateAlias:
    """Tests for alias validation."""

    def test_valid_alias(self):
        assert validate_alias("myalias") is True
        assert validate_alias("my-alias") is True
        assert validate_alias("my_alias") is True
        assert validate_alias("my.alias") is True
        assert validate_alias("alias123") is True

    def test_empty_alias(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_alias("")

    def test_none_alias(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_alias(None)

    def test_too_long_alias(self):
        with pytest.raises(ValidationError, match="100 characters or less"):
            validate_alias("a" * 101)

    def test_invalid_characters(self):
        with pytest.raises(ValidationError, match="can only contain"):
            validate_alias("my alias")  # space
        with pytest.raises(ValidationError, match="can only contain"):
            validate_alias("my@alias")  # special char
        with pytest.raises(ValidationError, match="can only contain"):
            validate_alias("my/alias")  # slash

    def test_reserved_routes(self):
        reserved = ['add', 'del', 'settings', 'shutdown', 'about', 'redirects']
        for route in reserved:
            with pytest.raises(ValidationError, match="reserved route"):
                validate_alias(route)

    def test_reserved_routes_case_insensitive(self):
        with pytest.raises(ValidationError, match="reserved route"):
            validate_alias("ADD")
        with pytest.raises(ValidationError, match="reserved route"):
            validate_alias("Settings")


class TestValidateRedirect:
    """Tests for redirect URL validation."""

    def test_valid_redirect(self):
        assert validate_redirect("https://example.com") is True
        assert validate_redirect("http://192.168.1.1") is True
        assert validate_redirect("example.com") is True

    def test_empty_redirect(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_redirect("")

    def test_too_long_redirect(self):
        with pytest.raises(ValidationError, match="2000 characters or less"):
            validate_redirect("https://example.com/" + "a" * 2000)


class TestValidatePort:
    """Tests for port validation."""

    def test_valid_ports(self):
        assert validate_port(80) == 80
        assert validate_port("8080") == 8080
        assert validate_port(1) == 1
        assert validate_port(65535) == 65535

    def test_port_too_low(self):
        with pytest.raises(ValidationError, match="between 1 and 65535"):
            validate_port(0)

    def test_port_too_high(self):
        with pytest.raises(ValidationError, match="between 1 and 65535"):
            validate_port(65536)

    def test_invalid_port(self):
        with pytest.raises(ValidationError, match="valid number"):
            validate_port("abc")
        with pytest.raises(ValidationError, match="valid number"):
            validate_port(None)


class TestValidateHostname:
    """Tests for hostname validation."""

    def test_valid_hostnames(self):
        assert validate_hostname("localhost") is True
        assert validate_hostname("0.0.0.0") is True
        assert validate_hostname("192.168.1.1") is True
        assert validate_hostname("my-server.local") is True

    def test_empty_hostname(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_hostname("")

    def test_too_long_hostname(self):
        with pytest.raises(ValidationError, match="255 characters or less"):
            validate_hostname("a" * 256)

    def test_invalid_hostname(self):
        with pytest.raises(ValidationError, match="Invalid hostname"):
            validate_hostname("my server")  # space
        with pytest.raises(ValidationError, match="Invalid hostname"):
            validate_hostname("server@domain")  # special char


class TestValidateShortname:
    """Tests for shortname validation."""

    def test_valid_shortnames(self):
        assert validate_shortname("r") is True
        assert validate_shortname("redirect") is True
        assert validate_shortname("my-short") is True

    def test_empty_shortname(self):
        with pytest.raises(ValidationError, match="cannot be empty"):
            validate_shortname("")

    def test_too_long_shortname(self):
        with pytest.raises(ValidationError, match="50 characters or less"):
            validate_shortname("a" * 51)


class TestDatabaseOperations:
    """Tests for database CRUD operations."""

    def test_database_init(self, temp_db):
        """Test that database initializes correctly."""
        data = load_data(temp_db)
        assert data["settings"] is not None
        assert data["settings"]["hostname"] == "0.0.0.0"
        assert data["settings"]["port"] == 80
        # Check example redirect exists
        assert "ex" in data["redirects"]

    def test_add_alias(self, temp_db):
        """Test adding a new alias."""
        add_alias("test", "https://test.com", temp_db)
        data = load_data(temp_db)
        assert "test" in data["redirects"]
        assert data["redirects"]["test"] == "https://test.com"

    def test_add_duplicate_alias(self, temp_db):
        """Test that adding duplicate alias raises error."""
        add_alias("dup", "https://first.com", temp_db)
        with pytest.raises(ValidationError, match="already exists"):
            add_alias("dup", "https://second.com", temp_db)

    def test_delete_alias(self, temp_db):
        """Test deleting an alias."""
        add_alias("todelete", "https://delete.com", temp_db)
        data = load_data(temp_db)
        assert "todelete" in data["redirects"]

        delete_alias("todelete", temp_db)
        data = load_data(temp_db)
        assert "todelete" not in data["redirects"]

    def test_update_setting_hostname(self, temp_db):
        """Test updating hostname setting."""
        update_setting("hostname", "127.0.0.1", temp_db)
        data = load_data(temp_db)
        assert data["settings"]["hostname"] == "127.0.0.1"

    def test_update_setting_port(self, temp_db):
        """Test updating port setting."""
        update_setting("port", "8080", temp_db)
        data = load_data(temp_db)
        assert data["settings"]["port"] == 8080

    def test_update_setting_boolean(self, temp_db):
        """Test updating boolean settings."""
        update_setting("bottle-debug", "True", temp_db)
        data = load_data(temp_db)
        assert data["settings"]["bottle-debug"] == "True"

        update_setting("bottle-debug", "", temp_db)
        data = load_data(temp_db)
        assert data["settings"]["bottle-debug"] == "False"

    def test_update_invalid_setting(self, temp_db):
        """Test that updating invalid setting raises error."""
        with pytest.raises(ValidationError, match="Invalid setting"):
            update_setting("invalid-setting", "value", temp_db)

    def test_update_setting_with_invalid_port(self, temp_db):
        """Test that invalid port value raises error."""
        with pytest.raises(ValidationError, match="between 1 and 65535"):
            update_setting("port", "99999", temp_db)


class TestSQLInjectionPrevention:
    """Tests to verify SQL injection prevention."""

    def test_alias_with_sql_injection(self, temp_db):
        """Test that SQL injection in alias is prevented."""
        # This should fail validation, not execute SQL
        with pytest.raises(ValidationError):
            add_alias("'; DROP TABLE redirects; --", "https://evil.com", temp_db)

    def test_redirect_with_quotes(self, temp_db):
        """Test that redirects with quotes work safely."""
        # Quotes in redirect should be handled safely
        add_alias("quoted", "https://example.com/?q='test'", temp_db)
        data = load_data(temp_db)
        assert "quoted" in data["redirects"]
