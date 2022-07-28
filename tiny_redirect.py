from operator import ne
import data
from bottle import Bottle, request, redirect, template, static_file, route
from bottle import route, run, template, static_file
from threading import Thread
import signal, time, os

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
    return redirect("/", 303)


@app.route("/about")
def about():
    redirect("https://sethstenzel.me/portfolio/tinyredirect/", 303)


@app.route("/<alias>")
def alias_redirection(alias):
    alias_redirect = app.app_db_data["redirects"].get(alias)
    if not alias_redirect:
        return f'"{alias}" not found in redirect table'
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


@app.route("/update")
def update_setting():
    pass


@app.route("/redirects")
def redirects():
    app.app_db_data = data.load_data()
    if app.app_db_data["redirects"]:
        page_data = {
            "title": "TinyRedirect - Modify Redirects",
            "redirects": app.app_db_data["redirects"].items(),
        }
        return template("redirects", page_data)
    return redirect("/", 303)


@app.route("/settings")
def settings():
    pass


@app.route("/shutdown")
def shutdown():
    page_data = {
        "title": "TinyRedirect - Shutdown!",
    }
    # Thread(target=shutdown_server).start()
    return template("shutdown", page_data)


def shutdown_server():
    time.sleep(4)
    pid = os.getpid()
    os.kill(pid, signal.SIGINT)


if __name__ == "__main__":
    app.app_db_data = data.load_data()
    app.run(
        host=app.app_db_data["settings"]["hostname"],
        port=app.app_db_data["settings"]["port"],
        debug=eval(app.app_db_data["settings"]["bottle-debug"]),
        reloader=eval(app.app_db_data["settings"]["bottle-reloader"]),
        server=app.app_db_data["settings"]["bottle-engine"],
    )
