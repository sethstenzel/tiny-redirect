from operator import ne
import data
from bottle import Bottle, request, redirect, template, static_file, route
from bottle import route, run, template, static_file
from threading import Thread
import signal, time, os, sys, sqlite3
import webbrowser as wb

app = Bottle()

# Static File Routes
@app.route("/img/<filename>")
def server_static(filename):
    return static_file(filename, root="./img")


@app.route("/js/<filename>")
def server_static(filename):
    return static_file(filename, root="./js")


@app.route("/css/<filename>")
def server_static(filename):
    return static_file(filename, root="./css")


@app.get("/favicon.ico")
def get_favicon():
    return server_static("./img/favicon.ico")


# App Routes


@app.route("/")
def index():
    app_database_data = data.load_data()
    if app_database_data["redirects"]:
        page_data = {
            "title": "TinyRedirect - List Redirects",
            "redirects": app_database_data["redirects"].items(),
        }
        return template("root", page_data)
    return redirect("/redirects", 303)


@app.route("/about")
def about():
    redirect("https://sethstenzel.me/portfolio/tinyredirect/", 303)


@app.route("/<alias>")
def alias_redirection(alias):
    app_database_data = data.load_data()
    alias_redirect = app_database_data["redirects"].get(alias)
    if not alias_redirect:
        page_data = {"title": "TinyRedirect - Alias Not Found!", "alias": alias}
        return template("noalias", page_data)
    if not "://" in alias_redirect:
        alias_redirect = "http://" + alias_redirect
    redirect(alias_redirect, 303)


@app.route("/add")
def add_alias():
    print(request)
    new_alias = request.query.alias
    new_redirect = request.query.redirect
    goto = request.query.goto
    print(new_alias, new_redirect, goto)
    data.add_alias(new_alias, new_redirect)
    if goto:
        redirect(goto, 303)
    redirect("/", 303)


@app.route("/del")
def delete_alias():
    del_alias = request.query.alias
    goto = request.query.goto
    data.delete_alias(del_alias)
    if goto:
        redirect(goto, 303)
    redirect("/", 303)


@app.route("/settings")
def settings():
    app_database_data = data.load_data()

    page_data = {
        "title": "TinyRedirect - Server Settings",
        "current_host": app_database_data["settings"]["hostname"],
        "current_port": app_database_data["settings"]["port"],
        "current_debug": eval(app_database_data["settings"]["bottle-debug"]),
        "current_reloader": eval(app_database_data["settings"]["bottle-reloader"]),
        "current_console": eval(app_database_data["settings"]["hide-console"]),
        "current_shortname": app_database_data["settings"]["shortname"],
    }
    return template("settings", page_data)


@app.route("/update_settings")
def update_setting():
    update_hostname = request.query.hostname
    if update_hostname != "":
        data.update_setting(
            "hostname", app_database_data["settings"]["hostname"], update_hostname
        )
    update_port = request.query.port
    if update_port != "":
        data.update_setting("port", app_database_data["settings"]["port"], update_port)

    update_shortname = request.query.shortname
    if update_shortname != "":
        data.update_setting(
            "shortname", app_database_data["settings"]["shortname"], update_shortname
        )

    update_debug = request.query.debug
    if update_debug != "":
        data.update_setting(
            "bottle-debug", app_database_data["settings"]["bottle-debug"], update_debug
        )
    else:
        data.update_setting(
            "bottle-debug",
            app_database_data["settings"]["bottle-debug"],
            "False",
        )

    update_reloader = request.query.reloader
    if update_reloader != "":

        data.update_setting(
            "bottle-reloader",
            app_database_data["settings"]["bottle-reloader"],
            update_reloader,
        )
    else:
        data.update_setting(
            "bottle-reloader",
            app_database_data["settings"]["bottle-reloader"],
            "False",
        )

    update_console = request.query.console
    if update_console != "":
        data.update_setting(
            "hide-console", app_database_data["settings"]["hide-console"], update_console
        )
    else:
        data.update_setting(
            "hide-console",
            app_database_data["settings"]["hide-console"],
            "False",
        )
    app_database_data = data.load_data()
    return redirect("/settings", 303)


@app.route("/redirects")
def redirects():
    app_database_data = data.load_data()
    if app_database_data["redirects"]:
        page_data = {
            "title": "TinyRedirect - Modify Redirects",
            "redirects": app_database_data["redirects"].items(),
        }
        return template("redirects", page_data)
    return redirect("/add?alias=ex&redirect=https://example.com/", 303)


@app.route("/shutdown")
def shutdown():
    page_data = {
        "title": "TinyRedirect - Shutdown!",
    }
    Thread(target=shutdown_server).start()
    return template("shutdown", page_data)


def shutdown_server():
    time.sleep(4)
    pid = os.getpid()
    os.kill(pid, signal.SIGINT)


def open_webpage():
    time.sleep(5)
    shortname = app_database_data["settings"]["shortname"]
    port = app_database_data["settings"]["port"]
    wb.open_new_tab(f"http://{shortname}:{port}/")


def get_windows():
    app_windows = []

    def winEnumHandler(hwnd, ctx):
        if win32gui.IsWindowVisible(hwnd):
            n = win32gui.GetWindowText(hwnd)
            if n == "TinyRedirect - App Server":
                app_windows.append((n, hwnd))
                print((n, hwnd))

    win32gui.EnumWindows(winEnumHandler, None)
    return app_windows


if __name__ == "__main__":

    if not data.database_init() and not data.load_data()["settings"]:
        raise ("Database not found; data.db could not be found or created.")

    try:
        intial_database_load = data.load_data()
    except sqlite3.OperationalError as error:
        print(
            "\nExpected database tables missing or damaged,\ndelete data.db and run again."
        )
        sys.exit()

    Thread(target=open_webpage).start()

    if len(sys.argv) > 1 and sys.argv[1] == "--defaults":
        print("Starting Server with Defaults\n\n")
        print('host="0.0.0.0"')
        print('port="8888"')
        app.run(
            host="0.0.0.0",
            port="8888",
            debug=True,
            reloader=True,
        )
    else:
        app_database_data = intial_database_load
        if eval(app_database_data["settings"]["hide-console"]):
            import win32.lib.win32con as win32con
            import win32gui
            from win32gui import GetWindowText

            app_windows = get_windows()
            for app_window in app_windows:
                win32gui.ShowWindow(app_window[1], win32con.SW_HIDE)

        app.run(
            host=app_database_data["settings"]["hostname"],
            port=app_database_data["settings"]["port"],
            debug=eval(app_database_data["settings"]["bottle-debug"]),
            reloader=eval(app_database_data["settings"]["bottle-reloader"]),
            server=app_database_data["settings"]["bottle-engine"],
        )
