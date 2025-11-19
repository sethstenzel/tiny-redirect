import sqlite3
import re
from os.path import exists


class ValidationError(Exception):
    """Custom exception for validation errors"""
    pass


def dict_factory(cursor, row):
    dictionary = {}
    for idx, col in enumerate(cursor.description):
        dictionary[col[0]] = row[idx]
    return dictionary


def str_to_bool(value):
    """Safely convert string to boolean without using eval()"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ('true', '1', 'yes')
    return bool(value)


def validate_alias(alias):
    """Validate alias input - alphanumeric, dash, underscore, dot only"""
    if not alias:
        raise ValidationError("Alias cannot be empty")
    if len(alias) > 100:
        raise ValidationError("Alias must be 100 characters or less")
    if not re.match(r'^[A-Za-z0-9\-_\.]+$', alias):
        raise ValidationError("Alias can only contain letters, numbers, dashes, underscores, and dots")
    # Prevent reserved routes
    reserved = ['add', 'del', 'delete', 'settings', 'update_settings', 'shutdown',
                'about', 'redirects', 'img', 'js', 'css', 'favicon.ico']
    if alias.lower() in reserved:
        raise ValidationError(f"'{alias}' is a reserved route name")
    return True


def validate_redirect(redirect):
    """Validate redirect URL input"""
    if not redirect:
        raise ValidationError("Redirect URL cannot be empty")
    if len(redirect) > 2000:
        raise ValidationError("Redirect URL must be 2000 characters or less")
    # Basic URL validation - allow URLs with or without protocol
    return True


def validate_port(port):
    """Validate port number"""
    try:
        port_num = int(port)
        if port_num < 1 or port_num > 65535:
            raise ValidationError("Port must be between 1 and 65535")
        return port_num
    except (ValueError, TypeError):
        raise ValidationError("Port must be a valid number")


def validate_hostname(hostname):
    """Validate hostname/IP address"""
    if not hostname:
        raise ValidationError("Hostname cannot be empty")
    if len(hostname) > 255:
        raise ValidationError("Hostname must be 255 characters or less")
    # Basic validation - allow IP addresses and hostnames
    if not re.match(r'^[A-Za-z0-9\-\.]+$', hostname):
        raise ValidationError("Invalid hostname format")
    return True


def validate_shortname(shortname):
    """Validate shortname for hostfile entry"""
    if not shortname:
        raise ValidationError("Shortname cannot be empty")
    if len(shortname) > 50:
        raise ValidationError("Shortname must be 50 characters or less")
    if not re.match(r'^[A-Za-z0-9\-_\.]+$', shortname):
        raise ValidationError("Shortname can only contain letters, numbers, dashes, underscores, and dots")
    return True


def load_settings(data, db_path="redirects.db"):
    connection = sqlite3.connect(db_path)
    connection.row_factory = dict_factory
    cursor = connection.cursor()
    sql_query = "SELECT * FROM settings"

    cursor.execute(sql_query)
    data["settings"] = cursor.fetchone()
    connection.close()
    return data


def load_redirects(data, db_path="redirects.db"):
    connection = sqlite3.connect(db_path)
    connection.row_factory = dict_factory
    cursor = connection.cursor()
    sql_query = "SELECT * FROM redirects"

    cursor.execute(sql_query)
    for redirect in cursor.fetchall():
        data["redirects"].update({redirect["alias"]: redirect["redirect"]})
    connection.close()
    return data


def load_data(db_path="redirects.db"):
    data = {
        "settings": {},
        "redirects": {},
    }
    data = load_settings(data, db_path)
    data = load_redirects(data, db_path)
    return data


def add_alias(alias, redirect, db_path="redirects.db"):
    """Add a new alias redirect with parameterized query"""
    # Validate inputs
    validate_alias(alias)
    validate_redirect(redirect)

    connection = sqlite3.connect(db_path)
    add_sql = 'INSERT INTO redirects (alias, redirect) VALUES (?, ?)'
    try:
        cursor = connection.cursor()
        cursor.execute(add_sql, (alias, redirect))
        connection.commit()
    except sqlite3.IntegrityError:
        connection.rollback()
        raise ValidationError(f"Alias '{alias}' already exists")
    except sqlite3.OperationalError as error:
        connection.rollback()
        raise error
    finally:
        connection.close()


def delete_alias(alias, db_path="redirects.db"):
    """Delete an alias with parameterized query"""
    connection = sqlite3.connect(db_path)
    deletion_sql = 'DELETE FROM redirects WHERE alias = ?'
    try:
        cursor = connection.cursor()
        cursor.execute(deletion_sql, (alias,))
        connection.commit()
    except sqlite3.OperationalError as error:
        connection.rollback()
        raise error
    finally:
        connection.close()


def update_setting(setting, new_value, db_path="redirects.db"):
    """Update a setting with parameterized query - simplified without current_value check"""
    # Validate based on setting type
    if setting == 'port':
        new_value = str(validate_port(new_value))
    elif setting == 'hostname':
        validate_hostname(new_value)
    elif setting == 'shortname':
        validate_shortname(new_value)
    elif setting in ('bottle-debug', 'bottle-reloader', 'hide-console'):
        # Normalize boolean values
        new_value = 'True' if str_to_bool(new_value) else 'False'

    connection = sqlite3.connect(db_path)
    # Use parameterized query - setting name is from our code, not user input
    valid_settings = ['hostname', 'port', 'shortname', 'bottle-debug',
                      'bottle-reloader', 'bottle-engine', 'theme', 'hide-console']
    if setting not in valid_settings:
        raise ValidationError(f"Invalid setting: {setting}")

    update_sql = f'UPDATE settings SET "{setting}" = ?'
    try:
        cursor = connection.cursor()
        cursor.execute(update_sql, (new_value,))
        connection.commit()
    except sqlite3.OperationalError as error:
        connection.rollback()
        raise error
    finally:
        connection.close()


def database_init(db_path="redirects.db"):
    if not exists(db_path):
        connection = sqlite3.connect(db_path)
        cursor = connection.cursor()
        cursor.execute(
            """
            CREATE TABLE "settings" (
                "hostname"	TEXT DEFAULT '127.0.0.1',
                "port"	INTEGER DEFAULT 80,
                "shortname"	TEXT DEFAULT 'r',
                "bottle-debug"	TEXT DEFAULT 'True',
                "bottle-reloader"	TEXT DEFAULT 'True',
                "bottle-engine"	TEXT DEFAULT 'wsgiref',
                "theme"	TEXT DEFAULT 'Light',
                "hide-console"	TEXT DEFAULT 'False'
            );
            """
        )

        cursor.execute('INSERT INTO settings (hostname) VALUES("127.0.0.1");')
        cursor.execute(
            """
            CREATE TABLE "redirects" (
            "alias"	TEXT UNIQUE,
            "redirect"	TEXT
            );
            """
        )

        cursor.execute(
            'INSERT INTO redirects (alias, redirect) VALUES (?, ?)',
            ("ex", "https://example.com")
        )

        connection.commit()
        connection.close()
    return exists(db_path)


if __name__ == "__main__":
    from pprint import pprint as print

    data = load_data()
    print(data)
