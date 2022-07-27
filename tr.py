from data import load_data
from bottle import Bottle, request, redirect
from threading import Thread
import signal, time, os

app = Bottle()


@app.route("/")
def index():
    redirect_table = ""
    if app.app_db_data["redirects"]:
        for k, v in app.app_db_data["redirects"].items():
            redirect_table += f"[{k} &rarr; {v}]<br>"
        return redirect_table
    return "no redirects found :("


@app.route("/<new_path:path>")
def base(new_path):
    rkey = request.url.split("//")[1].split("/")[1]
    redirection = app.app_db_data["redirects"].get(rkey)
    if not redirection:
        return f'"{rkey}" not found in redirect table'
    if not "://" in redirection:
        redirection = "http://" + redirection
    redirect(redirection, 303)


@app.route("/shutdown")
def shutdown():
    Thread(target=shutdown_server).start()
    return "Stopping Server..."


def shutdown_server():
    time.sleep(3)
    pid = os.getpid()
    os.kill(pid, signal.SIGINT)


if __name__ == "__main__":
    app.app_db_data = load_data()
    app.run(
        host=app.app_db_data["settings"]["hostname"],
        port=app.app_db_data["settings"]["port"],
        debug=eval(app.app_db_data["settings"]["bottle-debug"]),
        reloader=eval(app.app_db_data["settings"]["bottle-reloader"]),
        server=app.app_db_data["settings"]["bottle-engine"],
    )
