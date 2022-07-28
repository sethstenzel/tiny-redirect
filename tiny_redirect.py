from operator import ne
import data
from bottle import Bottle, request, redirect, template, static_file, route
from bottle import route, run, template, static_file
from threading import Thread
import signal, time, os, sys

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
    app.app_db_data = data.load_data()
    if app.app_db_data["redirects"]:
        page_data = {
            "title": "TinyRedirect - List Redirects",
            "redirects": app.app_db_data["redirects"].items(),
        }
        return template("root", page_data)
    return redirect("/redirects", 303)


@app.route("/about")
def about():
    redirect("https://sethstenzel.me/portfolio/tinyredirect/", 303)


@app.route("/<alias>")
def alias_redirection(alias):
    alias_redirect = app.app_db_data["redirects"].get(alias)
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
    app.app_db_data = data.load_data()

    page_data = {
        "title": "TinyRedirect - Server Settings",
        "current_host": app.app_db_data["settings"]["hostname"],
        "current_port": app.app_db_data["settings"]["port"],
        "current_debug": eval(app.app_db_data["settings"]["bottle-debug"]),
        "current_reloader": eval(app.app_db_data["settings"]["bottle-reloader"]),
        "current_console": eval(app.app_db_data["settings"]["hide-console"]),
    }
    return template("settings", page_data)


@app.route("/update_settings")
def update_setting():
    update_hostname = request.query.hostname
    if update_hostname != "":
        data.update_setting(
            "hostname", app.app_db_data["settings"]["hostname"], update_hostname
        )
    update_port = request.query.port
    if update_port != "":
        data.update_setting("port", app.app_db_data["settings"]["port"], update_port)

    update_debug = request.query.debug
    if update_debug != "":
        data.update_setting(
            "bottle-debug", app.app_db_data["settings"]["bottle-debug"], update_debug
        )
    else:
        data.update_setting(
            "bottle-debug",
            app.app_db_data["settings"]["bottle-debug"],
            "False",
        )

    update_reloader = request.query.reloader
    if update_reloader != "":

        data.update_setting(
            "bottle-reloader",
            app.app_db_data["settings"]["bottle-reloader"],
            update_reloader,
        )
    else:
        data.update_setting(
            "bottle-reloader",
            app.app_db_data["settings"]["bottle-reloader"],
            "False",
        )

    update_console = request.query.console
    if update_console != "":
        data.update_setting(
            "hide-console", app.app_db_data["settings"]["hide-console"], update_console
        )
    else:
        data.update_setting(
            "hide-console",
            app.app_db_data["settings"]["hide-console"],
            "False",
        )
    app.app_db_data = data.load_data()
    return redirect("/settings", 303)


@app.route("/redirects")
def redirects():
    app.app_db_data = data.load_data()
    if app.app_db_data["redirects"]:
        page_data = {
            "title": "TinyRedirect - Modify Redirects",
            "redirects": app.app_db_data["redirects"].items(),
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


if __name__ == "__main__":
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
        app.app_db_data = data.load_data()
        if eval(app.app_db_data["settings"]["hide-console"]):
            import win32.lib.win32con as win32con
            import win32gui

            my_app = win32gui.GetForegroundWindow()
            win32gui.ShowWindow(my_app, win32con.SW_HIDE)

        app.run(
            host=app.app_db_data["settings"]["hostname"],
            port=app.app_db_data["settings"]["port"],
            debug=eval(app.app_db_data["settings"]["bottle-debug"]),
            reloader=eval(app.app_db_data["settings"]["bottle-reloader"]),
            server=app.app_db_data["settings"]["bottle-engine"],
        )
