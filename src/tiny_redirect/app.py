from tiny_redirect import data
from tiny_redirect.data import ValidationError, str_to_bool
from bottle import Bottle, request, redirect, template, static_file, response, TEMPLATE_PATH
from threading import Thread
from loguru import logger
import signal
import time
import os
import sys
import sqlite3
import webbrowser as wb
import secrets
import hashlib
import requests
import tempfile
import subprocess
import atexit

# Global variable to store log directory path for crash handler
_log_dir = None


def get_log_path():
    """
    Determine the appropriate log file path based on platform.
    Windows: temp directory
    Linux/Unix: /var/log/tinyredirect or fallback to user directory
    """
    global _log_dir

    if sys.platform == 'win32':
        # Use temp directory on Windows
        _log_dir = os.path.join(tempfile.gettempdir(), 'TinyRedirect')
    else:
        # Try standard Linux log location first
        standard_log_dir = '/var/log/tinyredirect'
        try:
            os.makedirs(standard_log_dir, exist_ok=True)
            # Test if we can write to it
            test_file = os.path.join(standard_log_dir, '.write_test')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            _log_dir = standard_log_dir
        except (PermissionError, OSError):
            # Fall back to user's home directory
            _log_dir = os.path.join(os.path.expanduser('~'), '.tinyredirect', 'logs')

    os.makedirs(_log_dir, exist_ok=True)
    return os.path.join(_log_dir, 'tinyredirect.log')


def setup_logging(enable_info_logging=False):
    """
    Configure loguru logging with file output and crash handling.

    Args:
        enable_info_logging: If True, log INFO level to file. If False, only WARNING and above to file.
    """
    log_file = get_log_path()

    # Remove default logger
    logger.remove()

    # Add console logger only if stderr is available (not available in PyInstaller windowed mode)
    if sys.stderr is not None:
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
            level="INFO"
        )

    # Determine file log level based on flag
    file_log_level = "DEBUG" if enable_info_logging else "WARNING"

    # Add file logger with rotation
    logger.add(
        log_file,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        level=file_log_level,
        rotation="10 MB",
        retention="7 days",
        compression="zip"
    )

    if enable_info_logging:
        logger.info(f"Logging initialized with INFO level enabled. Log file: {log_file}")
    else:
        logger.warning(f"Logging initialized (file: WARNING+ only, use --info for detailed logs). Log file: {log_file}")

    return log_file


def open_log_folder_on_crash():
    """Open the log folder when the app crashes (Windows only)."""
    global _log_dir
    if sys.platform == 'win32' and _log_dir and os.path.exists(_log_dir):
        try:
            subprocess.Popen(['explorer', _log_dir])
            logger.info(f"Opened log folder for crash inspection: {_log_dir}")
        except Exception as e:
            logger.error(f"Failed to open log folder: {e}")
            print(f"Failed to open log folder: {e}", file=sys.stderr)


def handle_exception(exc_type, exc_value, exc_traceback):
    """Global exception handler to log crashes and open log folder on Windows."""
    if issubclass(exc_type, KeyboardInterrupt):
        # Don't log keyboard interrupts as crashes
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return

    logger.opt(exception=(exc_type, exc_value, exc_traceback)).critical("Unhandled exception - application crashed!")

    # Open log folder on Windows
    if sys.platform == 'win32':
        open_log_folder_on_crash()

    sys.__excepthook__(exc_type, exc_value, exc_traceback)

# Get the package directory for static files and templates
PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(PACKAGE_DIR, "static")
VIEWS_DIR = os.path.join(PACKAGE_DIR, "views")

# Add views directory to Bottle template path
TEMPLATE_PATH.insert(0, VIEWS_DIR)

app = Bottle()
MAIN_APP_PID = os.getpid()

# CSRF token storage (in production, use a proper session store)
csrf_tokens = {}

# Global reference to tray icon for cleanup
tray_icon = None
server_url = None

# Database path (can be overridden for testing)
db_path = "redirects.db"


def get_db_path():
    """
    Determine the appropriate database path.
    Priority: 1) TINYREDIRECT_DB_PATH env var, 2) local directory, 3) platform-specific app data
    Returns the path to use for the database.
    """
    # Check for environment variable first (useful for Docker)
    env_db_path = os.environ.get('TINYREDIRECT_DB_PATH')
    if env_db_path:
        # Ensure directory exists
        db_dir = os.path.dirname(env_db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        return env_db_path

    local_db = "redirects.db"

    # Try local directory first
    try:
        # Check if we can write to the local directory
        if os.path.exists(local_db):
            # Database exists locally, try to open it
            with open(local_db, 'a'):
                pass
            return local_db
        else:
            # Try to create the database locally
            with open(local_db, 'w') as f:
                pass
            # Clean up the test file
            os.remove(local_db)
            return local_db
    except (PermissionError, OSError):
        pass

    # Fall back to platform-specific app data location
    if sys.platform == 'win32':
        # Use LOCALAPPDATA for application data
        app_data = os.environ.get('LOCALAPPDATA')
        if not app_data:
            app_data = os.path.join(os.environ.get('USERPROFILE', ''), 'AppData', 'Local')

        app_dir = os.path.join(app_data, 'TinyRedirect')
    else:
        # For non-Windows, use user's home directory
        app_dir = os.path.join(os.path.expanduser('~'), '.tinyredirect')

    # Create the application directory if it doesn't exist
    try:
        os.makedirs(app_dir, exist_ok=True)
    except OSError as e:
        # Can't use logger here as this may be called before logging is set up
        print(f"Error creating application directory: {e}", file=sys.stderr)
        # Last resort: use temp directory
        app_dir = tempfile.gettempdir()

    return os.path.join(app_dir, 'redirects.db')


def generate_csrf_token():
    """Generate a CSRF token for form protection"""
    token = secrets.token_urlsafe(32)
    # Store hash of token for verification
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    csrf_tokens[token_hash] = time.time()
    # Clean up old tokens (older than 1 hour)
    current_time = time.time()
    expired = [k for k, v in csrf_tokens.items() if current_time - v > 3600]
    for k in expired:
        del csrf_tokens[k]
    return token


def verify_csrf_token(token):
    """Verify a CSRF token is valid"""
    if not token:
        return False
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    return token_hash in csrf_tokens


# System Tray Functions
def create_tray_icon(shortname, port):
    """Create and run the system tray icon (Windows only)"""
    global tray_icon, server_url

    logger.info(f"create_tray_icon: Starting tray icon creation (shortname={shortname}, port={port})")

    # Skip tray icon on non-Windows platforms (e.g., Docker)
    if sys.platform != 'win32':
        logger.info("System tray icon not available on non-Windows platform")
        return

    try:
        logger.info("create_tray_icon: Importing pystray and PIL...")
        import pystray
        from PIL import Image

        server_url = f"http://{shortname}:{port}/"
        logger.info(f"create_tray_icon: Server URL set to {server_url}")

        # Try to load the app icon, fall back to a generated one
        icon_path = os.path.join(STATIC_DIR, "img", "favicon.ico")
        logger.info(f"create_tray_icon: Looking for icon at {icon_path}")
        if os.path.exists(icon_path):
            logger.info(f"create_tray_icon: Loading icon from {icon_path}")
            image = Image.open(icon_path)
        else:
            logger.info("create_tray_icon: Icon not found, creating default green icon")
            # Create a simple green icon if favicon not found
            image = Image.new('RGB', (64, 64), color=(106, 153, 118))

        def on_open_browser(_icon, _item):
            """Open the web interface in browser"""
            logger.info(f"on_open_browser: Opening {server_url}")
            try:
                wb.open_new_tab(server_url)
            except Exception as e:
                logger.error(f"on_open_browser: Failed to open browser: {e}")

        def on_open_redirects(_icon, _item):
            """Open the redirects management page"""
            url = f"{server_url}redirects"
            logger.info(f"on_open_redirects: Opening {url}")
            try:
                wb.open_new_tab(url)
            except Exception as e:
                logger.error(f"on_open_redirects: Failed to open browser: {e}")

        def on_open_settings(_icon, _item):
            """Open the settings page"""
            url = f"{server_url}settings"
            logger.info(f"on_open_settings: Opening {url}")
            try:
                wb.open_new_tab(url)
            except Exception as e:
                logger.error(f"on_open_settings: Failed to open browser: {e}")

        def on_open_logs(_icon, _item):
            """Open the log directory in file explorer"""
            global _log_dir
            logger.info(f"on_open_logs: Opening log directory {_log_dir}")
            if _log_dir and os.path.exists(_log_dir):
                try:
                    subprocess.Popen(['explorer', _log_dir])
                    logger.info("on_open_logs: Explorer opened successfully")
                except Exception as e:
                    logger.error(f"on_open_logs: Failed to open explorer: {e}")
            else:
                logger.warning(f"on_open_logs: Log directory not found or not set: {_log_dir}")

        def on_stop_server(icon, _item):
            """Stop the server and exit"""
            logger.info("on_stop_server: User requested shutdown from tray icon")
            shutdown_server()
            logger.info("on_stop_server: Stopping tray icon...")
            icon.stop()
            

        # Create the menu
        menu = pystray.Menu(
            pystray.MenuItem("Open TinyRedirect", on_open_browser, default=True),
            pystray.MenuItem("Manage Redirects", on_open_redirects),
            pystray.MenuItem("Settings", on_open_settings),
            pystray.MenuItem("Open Log Folder", on_open_logs),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Stop Server && Exit", on_stop_server)
        )

        # Create and run the icon
        logger.info("create_tray_icon: Creating pystray Icon object...")
        tray_icon = pystray.Icon(
            "TinyRedirect",
            image,
            "TinyRedirect",
            menu
        )

        logger.info("create_tray_icon: Starting tray icon (this will block until icon is closed)...")
        tray_icon.run()
        logger.info("create_tray_icon: Tray icon has been stopped")

    except ImportError as e:
        logger.warning(f"Could not create system tray icon - ImportError: {e}")
        logger.warning("Install pystray and pillow for system tray support: pip install pystray pillow")
    except Exception as e:
        logger.error(f"System tray icon error: {e}", exc_info=True)


def stop_tray_icon():
    """Stop the tray icon if running"""
    global tray_icon
    if tray_icon:
        try:
            logger.info("stop_tray_icon: Stopping tray icon...")
            tray_icon.stop()
            logger.info("stop_tray_icon: Tray icon stopped successfully")
        except Exception as e:
            logger.warning(f"stop_tray_icon: Error stopping tray icon: {e}")
    else:
        logger.info("stop_tray_icon: No tray icon to stop")


# Static File Routes
@app.route("/img/<filename>")
def serve_img(filename):
    return static_file(filename, root=os.path.join(STATIC_DIR, "img"))


@app.route("/js/<filename>")
def serve_js(filename):
    return static_file(filename, root=os.path.join(STATIC_DIR, "js"))


@app.route("/css/<filename>")
def serve_css(filename):
    return static_file(filename, root=os.path.join(STATIC_DIR, "css"))


@app.get("/favicon.ico")
def get_favicon():
    return static_file("favicon.ico", root=os.path.join(STATIC_DIR, "img"))


# App Routes
@app.route("/")
def index():
    app_database_data = data.load_data(db_path)
    if app_database_data["redirects"]:
        page_data = {
            "title": "TinyRedirect - List Redirects",
            "redirects": app_database_data["redirects"].items(),
        }
        return template("root", page_data)
    return redirect("/redirects", 303)


@app.route("/about")
def about():
    return redirect("https://sethstenzel.me/portfolio/tinyredirect/", 303)


@app.route("/<alias>")
def alias_redirection(alias):
    app_database_data = data.load_data(db_path)
    alias_redirect = app_database_data["redirects"].get(alias)
    if not alias_redirect:
        page_data = {"title": "TinyRedirect - Alias Not Found!", "alias": alias}
        return template("noalias", page_data)
    if "://" not in alias_redirect:
        alias_redirect = "http://" + alias_redirect
    return redirect(alias_redirect, 303)


@app.route("/add", method="GET")
def add_alias_form():
    """Show the add alias form (GET request)"""
    return redirect("/redirects", 303)


@app.route("/add", method="POST")
def add_alias():
    """Add a new alias (POST request with CSRF protection)"""
    csrf_token = request.forms.get("csrf_token")
    if not verify_csrf_token(csrf_token):
        response.status = 403
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": "Invalid or expired form submission. Please try again."
        })

    new_alias = request.forms.get("alias", "").strip()
    new_redirect = request.forms.get("redirect", "").strip()
    goto = request.forms.get("goto", "/")

    try:
        data.add_alias(new_alias, new_redirect, db_path)
    except ValidationError as e:
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": str(e)
        })
    except Exception as e:
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": f"Failed to add alias: {str(e)}"
        })

    if goto:
        return redirect(goto, 303)
    return redirect("/", 303)


@app.route("/del", method="GET")
def delete_alias_form():
    """Redirect GET requests to the redirects page"""
    return redirect("/redirects", 303)


@app.route("/del", method="POST")
def delete_alias():
    """Delete an alias (POST request with CSRF protection)"""
    csrf_token = request.forms.get("csrf_token")
    if not verify_csrf_token(csrf_token):
        response.status = 403
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": "Invalid or expired form submission. Please try again."
        })

    del_alias = request.forms.get("alias", "").strip()
    goto = request.forms.get("goto", "/")

    try:
        data.delete_alias(del_alias, db_path)
    except Exception as e:
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": f"Failed to delete alias: {str(e)}"
        })

    if goto:
        return redirect(goto, 303)
    return redirect("/", 303)


@app.route("/edit", method="GET")
def edit_alias_form():
    """Redirect GET requests to the redirects page"""
    return redirect("/redirects", 303)


@app.route("/edit", method="POST")
def edit_alias():
    """Edit an alias or URL (POST request with CSRF protection)"""
    csrf_token = request.forms.get("csrf_token")
    if not verify_csrf_token(csrf_token):
        response.status = 403
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": "Invalid or expired form submission. Please try again."
        })

    old_alias = request.forms.get("old_alias", "").strip()
    new_alias = request.forms.get("new_alias", "").strip()
    new_redirect = request.forms.get("new_redirect", "").strip()
    goto = request.forms.get("goto", "/redirects")

    try:
        # Load current data to get the existing redirect URL
        app_database_data = data.load_data(db_path)
        current_redirect = app_database_data["redirects"].get(old_alias)

        if not current_redirect:
            return template("error", {
                "title": "TinyRedirect - Error",
                "error": f"Alias '{old_alias}' not found."
            })

        # If alias changed, delete old and add new
        if new_alias and new_alias != old_alias:
            data.delete_alias(old_alias, db_path)
            data.add_alias(new_alias, new_redirect if new_redirect else current_redirect, db_path)
        # If only redirect URL changed, update the existing alias
        elif new_redirect and new_redirect != current_redirect:
            data.delete_alias(old_alias, db_path)
            data.add_alias(old_alias, new_redirect, db_path)

    except ValidationError as e:
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": str(e)
        })
    except Exception as e:
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": f"Failed to edit alias: {str(e)}"
        })

    if goto:
        return redirect(goto, 303)
    return redirect("/redirects", 303)


@app.route("/settings")
def settings():
    app_database_data = data.load_data(db_path)

    page_data = {
        "title": "TinyRedirect - Server Settings",
        "current_host": app_database_data["settings"]["hostname"],
        "current_port": app_database_data["settings"]["port"],
        "current_debug": str_to_bool(app_database_data["settings"]["bottle-debug"]),
        "current_reloader": str_to_bool(app_database_data["settings"]["bottle-reloader"]),
        "current_console": str_to_bool(app_database_data["settings"]["hide-console"]),
        "current_shortname": app_database_data["settings"]["shortname"],
        "csrf_token": generate_csrf_token(),
    }
    return template("settings", page_data)


@app.route("/update_settings", method="GET")
def update_settings_form():
    """Redirect GET requests to settings page"""
    return redirect("/settings", 303)


@app.route("/update_settings", method="POST")
def update_setting():
    """Update settings (POST request with CSRF protection)"""
    csrf_token = request.forms.get("csrf_token")
    if not verify_csrf_token(csrf_token):
        response.status = 403
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": "Invalid or expired form submission. Please try again."
        })

    try:
        update_hostname = request.forms.get("hostname", "").strip()
        if update_hostname:
            data.update_setting("hostname", update_hostname, db_path)

        update_port = request.forms.get("port", "").strip()
        if update_port:
            data.update_setting("port", update_port, db_path)

        update_shortname = request.forms.get("shortname", "").strip()
        if update_shortname:
            data.update_setting("shortname", update_shortname, db_path)

        # Handle boolean settings - checkbox sends value if checked, empty if not
        update_debug = request.forms.get("debug", "")
        data.update_setting("bottle-debug", update_debug, db_path)

        update_reloader = request.forms.get("reloader", "")
        data.update_setting("bottle-reloader", update_reloader, db_path)

        update_console = request.forms.get("console", "")
        data.update_setting("hide-console", update_console, db_path)

    except ValidationError as e:
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": str(e)
        })
    except Exception as e:
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": f"Failed to update settings: {str(e)}"
        })

    return redirect("/settings", 303)


@app.route("/redirects")
def redirects():
    app_database_data = data.load_data(db_path)
    csrf_token = generate_csrf_token()

    if app_database_data["redirects"]:
        page_data = {
            "title": "TinyRedirect - Modify Redirects",
            "redirects": app_database_data["redirects"].items(),
            "csrf_token": csrf_token,
        }
        return template("redirects", page_data)

    # If no redirects, add the example one
    try:
        data.add_alias("ex", "https://example.com", db_path)
    except:
        pass  # Ignore if already exists

    return redirect("/redirects", 303)


@app.route("/export_redirects")
def export_redirects():
    """Export all redirects to tredirects.json file"""
    try:
        json_data = data.export_redirects(db_path)

        # Set headers for file download
        response.content_type = 'application/json'
        response.headers['Content-Disposition'] = 'attachment; filename="tredirects.json"'

        return json_data
    except Exception as e:
        logger.error(f"Export failed: {e}")
        return template("error", {
            "title": "TinyRedirect - Export Error",
            "error": f"Failed to export redirects: {str(e)}"
        })


@app.route("/import_redirects", method="GET")
def import_redirects_form():
    """Redirect GET requests to settings page"""
    return redirect("/settings", 303)


@app.route("/import_redirects", method="POST")
def import_redirects():
    """Import redirects from uploaded tredirects.json file"""
    csrf_token = request.forms.get("csrf_token")
    if not verify_csrf_token(csrf_token):
        response.status = 403
        return template("error", {
            "title": "TinyRedirect - Error",
            "error": "Invalid or expired form submission. Please try again."
        })

    # Get the uploaded file
    upload = request.files.get('import_file')
    if not upload:
        return template("error", {
            "title": "TinyRedirect - Import Error",
            "error": "No file uploaded"
        })

    # Get replace mode checkbox
    replace_mode = request.forms.get("replace_mode", "") == "on"

    try:
        # Read the file content
        json_data = upload.file.read().decode('utf-8')

        # Import the redirects
        stats = data.import_redirects(json_data, db_path, replace=replace_mode)

        # Create success message with stats
        message_parts = []

        # Main statistics
        message_parts.append(f"Total in file: {stats['total']}")
        message_parts.append(f"Successfully imported: {stats['imported']}")

        if stats["duplicates"] > 0:
            message_parts.append(f"Skipped (duplicates): {stats['duplicates']}")

        # Show errors if any
        if stats["errors"]:
            message_parts.append("")
            message_parts.append("Errors:")
            error_list = stats["errors"][:10]  # Show first 10 errors
            for error in error_list:
                message_parts.append(f"  • {error}")
            if len(stats["errors"]) > 10:
                message_parts.append(f"  ... and {len(stats['errors']) - 10} more errors")

        message = "\n".join(message_parts)

        # Determine title and alert type based on results
        if stats["errors"]:
            title = "TinyRedirect - Import Completed with Errors"
            alert_type = "warning"
        elif stats["duplicates"] > 0 and stats["imported"] > 0:
            title = "TinyRedirect - Import Completed"
            alert_type = "info"
        elif stats["duplicates"] > 0 and stats["imported"] == 0:
            title = "TinyRedirect - Import Complete (All Duplicates)"
            alert_type = "info"
        else:
            title = "TinyRedirect - Import Successful"
            alert_type = "success"

        # Return custom success page with proper styling
        page_data = {
            "title": title,
            "message": message,
            "alert_type": alert_type
        }
        return template("import_result", page_data)

    except data.ValidationError as e:
        return template("error", {
            "title": "TinyRedirect - Import Error",
            "error": str(e)
        })
    except Exception as e:
        logger.error(f"Import failed: {e}")
        return template("error", {
            "title": "TinyRedirect - Import Error",
            "error": f"Failed to import redirects: {str(e)}"
        })


@app.route("/shutdown")
def shutdown():
    page_data = {
        "title": "TinyRedirect - Shutdown!",
    }
    Thread(target=shutdown_server).start()
    return template("shutdown", page_data)


def shutdown_server():
    logger.info("shutdown_server: Shutdown sequence initiated...")
    logger.info("shutdown_server: Waiting 3 seconds before stopping...")
    time.sleep(3)
    logger.info("shutdown_server: Stopping tray icon...")
    stop_tray_icon()
    global MAIN_APP_PID
    logger.info(f"shutdown_server: Attempting to terminate process {MAIN_APP_PID}...")
    try:
        os.kill(MAIN_APP_PID, signal.SIGINT)
        logger.info(f"shutdown_server: Sent SIGINT to process {MAIN_APP_PID}")
    except Exception as e:
        logger.warning(f"shutdown_server: Unable to kill process {MAIN_APP_PID}: {e}")
        logger.warning("shutdown_server: Opening shutdown URL as fallback...")
        wb.open_new_tab(f"http://{shortname}:{port}/shutdown")


def open_webpage(shortname, port):
    logger.info(f"open_webpage: Waiting 5 seconds before opening browser...")
    time.sleep(5)
    url = f"http://{shortname}:{port}/"
    logger.info(f"open_webpage: Opening browser tab for {url}")
    try:
        wb.open_new_tab(url)
        logger.info("open_webpage: Browser opened successfully")
    except Exception as e:
        logger.error(f"open_webpage: Failed to open browser: {e}")


def check_single_instance():
    """
    Check if another instance of TinyRedirect is already running (Windows only).
    Uses a named mutex for reliable single-instance detection.
    Returns tuple: (is_single_instance, mutex_handle)
    - is_single_instance: True if this is the only instance, False if another exists
    - mutex_handle: Handle to keep mutex alive (None if not single instance or not Windows)

    Note: This function is called BEFORE logging is initialized, so it prints to stderr.
    """
    print(f"[DEBUG] check_single_instance: Starting single instance check (platform: {sys.platform})", file=sys.stderr)

    if sys.platform != 'win32':
        print("[DEBUG] check_single_instance: Not Windows, skipping mutex check", file=sys.stderr)
        return True, None

    try:
        import win32event
        import win32api
        import winerror

        # Create a unique mutex name for TinyRedirect
        mutex_name = "Global\\TinyRedirect_SingleInstance_Mutex"
        print(f"[DEBUG] check_single_instance: Creating mutex '{mutex_name}'", file=sys.stderr)

        # Try to create the mutex
        mutex = win32event.CreateMutex(None, False, mutex_name)
        last_error = win32api.GetLastError()
        print(f"[DEBUG] check_single_instance: Mutex created, last_error={last_error}", file=sys.stderr)

        # If the mutex already exists, another instance is running
        if last_error == winerror.ERROR_ALREADY_EXISTS:
            print("[DEBUG] check_single_instance: Mutex already exists - another instance is running", file=sys.stderr)
            # Close the mutex handle since we won't use it
            win32api.CloseHandle(mutex)
            return False, None

        # This is the first instance - keep the mutex handle alive
        print("[DEBUG] check_single_instance: This is the first instance, mutex acquired", file=sys.stderr)
        return True, mutex

    except ImportError as e:
        # pywin32 not available, skip the check
        print(f"Warning: pywin32 not available, single-instance check skipped: {e}", file=sys.stderr)
        return True, None
    except Exception as e:
        print(f"Warning: Single-instance check failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return True, None


def main():
    global db_path
    mutex_handle = None

    try:
        print(f"[DEBUG] main: TinyRedirect starting (PID: {os.getpid()})", file=sys.stderr)

        # Check if we're in the reloader child process FIRST
        # When reloader=True, Bottle spawns a child process with BOTTLE_CHILD env var
        is_reloader_child = os.environ.get('BOTTLE_CHILD') == 'true'
        print(f"[DEBUG] main: Reloader child process: {is_reloader_child}", file=sys.stderr)

        # Check for single instance ONLY if not a reloader child
        # The parent process holds the mutex, child processes skip the check
        if sys.platform == 'win32' and not is_reloader_child:
            print("[DEBUG] main: Performing single instance check...", file=sys.stderr)
            is_single, mutex_handle = check_single_instance()
            if not is_single:
                # Can't use logger yet, so print to stderr
                print("ERROR: Another instance of TinyRedirect is already running", file=sys.stderr)
                sys.exit(0)
            # Keep mutex_handle alive for the duration of the program
            # Register cleanup to close mutex on exit
            if mutex_handle:
                print(f"[DEBUG] main: Mutex acquired successfully (handle: {mutex_handle})", file=sys.stderr)
                def cleanup_mutex():
                    try:
                        import win32api
                        print("[DEBUG] cleanup_mutex: Releasing mutex", file=sys.stderr)
                        win32api.CloseHandle(mutex_handle)
                    except Exception as e:
                        print(f"[DEBUG] cleanup_mutex: Failed to release mutex: {e}", file=sys.stderr)
                atexit.register(cleanup_mutex)

        # Check for --info flag to enable detailed logging
        enable_info_logging = "--info" in sys.argv

        # Set up logging after single instance check
        print("[DEBUG] main: Setting up logging...", file=sys.stderr)
        print(f"[DEBUG] main: INFO logging to file: {enable_info_logging}", file=sys.stderr)
        setup_logging(enable_info_logging)

        # Install global exception handler for crash logging
        sys.excepthook = handle_exception

        logger.info("=" * 80)
        logger.info(f"TinyRedirect starting (PID: {os.getpid()})")
        logger.info(f"Platform: {sys.platform}")
        logger.info(f"Python version: {sys.version}")
        logger.info(f"Command line args: {sys.argv}")

        # Determine the appropriate database path
        logger.info("Determining database path...")
        db_path = get_db_path()
        logger.info(f"Using database: {db_path}")

        logger.info("Initializing database...")
        if not data.database_init(db_path) and not data.load_data(db_path)["settings"]:
            logger.error("Database not found; redirects.db could not be found or created.")
            sys.exit(1)

        try:
            logger.info("Loading database settings...")
            initial_database_load = data.load_data(db_path)
            logger.info(f"Database loaded successfully. Redirects count: {len(initial_database_load['redirects'])}")
        except sqlite3.OperationalError as e:
            logger.error(f"Database tables missing or damaged: {e}")
            logger.error("Expected database tables missing or damaged,\ndelete redirects.db and run again.")
            sys.exit(1)

        # is_reloader_child was already checked at the start of main()
        logger.info(f"Reloader child process: {is_reloader_child}")

        # Check for --startup flag to suppress browser opening
        suppress_browser = "--startup" in sys.argv
        logger.info(f"Suppress browser opening: {suppress_browser}")

        if len(sys.argv) > 1 and sys.argv[1] == "--defaults":
            logger.info("Starting server with defaults: host=127.0.0.1, port=80")
            logger.info("Starting Server with Defaults\n\n")
            logger.info('host="127.0.0.1"')
            logger.info('port="80"')

            # Only start browser and tray icon in parent process (not reloader child)
            if not is_reloader_child:
                logger.info("Starting background threads (browser opener and tray icon)...")
                if not suppress_browser:
                    logger.info("Starting browser opener thread...")
                    Thread(target=open_webpage, args=("localhost", "80")).start()
                logger.info("Starting tray icon thread...")
                Thread(target=create_tray_icon, args=("localhost", "80"), daemon=True).start()

            logger.info("Starting Bottle server with defaults...")
            app.run(
                host="127.0.0.1",
                port="80",
                debug=False,
                reloader=False,
            )
        else:
            app_database_data = initial_database_load

            # Start browser with configured settings
            shortname = app_database_data["settings"]["shortname"]
            port = app_database_data["settings"]["port"]
            logger.info(f"Configured shortname: {shortname}")
            logger.info(f"Configured port: {port}")

            # Only start browser and tray icon in parent process (not reloader child)
            if not is_reloader_child:
                logger.info("Starting background threads (browser opener and tray icon)...")
                if not suppress_browser:
                    logger.info("Starting browser opener thread...")
                    Thread(target=open_webpage, args=(shortname, port)).start()
                logger.info("Starting tray icon thread...")
                Thread(target=create_tray_icon, args=(shortname, port), daemon=True).start()

            # Allow environment variable override for host (useful for Docker)
            host = os.environ.get('TINYREDIRECT_HOST', app_database_data["settings"]["hostname"])
            port = os.environ.get('TINYREDIRECT_PORT', app_database_data["settings"]["port"])

            logger.info(f"Final server configuration: host={host}, port={port}")
            logger.info(f"Debug mode: {str_to_bool(app_database_data['settings']['bottle-debug'])}")
            logger.info(f"Reloader mode: {str_to_bool(app_database_data['settings']['bottle-reloader'])}")
            logger.info(f"Server engine: {app_database_data['settings']['bottle-engine']}")
            logger.info("Starting Bottle server...")
            logger.info("=" * 80)

            app.run(
                host=host,
                port=port,
                debug=str_to_bool(app_database_data["settings"]["bottle-debug"]),
                reloader=str_to_bool(app_database_data["settings"]["bottle-reloader"]),
                server=app_database_data["settings"]["bottle-engine"],
            )

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt (Ctrl+C), shutting down...")
        print("\n[DEBUG] main: Keyboard interrupt received", file=sys.stderr)
    except SystemExit as e:
        logger.info(f"System exit called with code: {e.code}")
        print(f"[DEBUG] main: System exit with code {e.code}", file=sys.stderr)
        raise
    except Exception as e:
        logger.critical("=" * 80)
        logger.critical("FATAL ERROR: Application crashed!")
        logger.critical(f"Exception type: {type(e).__name__}")
        logger.critical(f"Exception message: {str(e)}")
        logger.critical("Full traceback:")
        logger.exception(e)
        logger.critical("=" * 80)

        # Also print to stderr for immediate visibility
        print("\n" + "=" * 80, file=sys.stderr)
        print("FATAL ERROR: TinyRedirect has crashed!", file=sys.stderr)
        print(f"Exception: {type(e).__name__}: {str(e)}", file=sys.stderr)
        print("=" * 80, file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)

        # Open log folder on Windows
        if sys.platform == 'win32':
            open_log_folder_on_crash()

        sys.exit(1)
    finally:
        logger.info("TinyRedirect shutting down...")
        logger.info("Cleaning up resources...")
        stop_tray_icon()
        logger.info("Application shutdown complete.")
        print("[DEBUG] main: Application shutdown complete", file=sys.stderr)


if __name__ == "__main__":
    main()
