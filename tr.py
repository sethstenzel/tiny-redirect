redirect_table = {
    "rt":"10.0.1.1",
    "grafana":"raijin:3000",
    "raijin":"raijin:2500",
    "proxmox":"https://10.0.1.16:8006/"
}

from bottle import Bottle, request, redirect
from threading import Thread
import signal, time, os

app = Bottle()

@app.route('/')
def index():
    table = ""
    for k, v in redirect_table.items():
        table += f"[{k} &rarr; {v}]<br>"
    return table

@app.route('/<new_path:path>')
def base(new_path):
    print(new_path)
    rkey = request.url.split("//")[1].split("/")[1]
    redirection = redirect_table.get(rkey)
    if not redirection:
        return f"\"{rkey}\" not found in redirect table"
    if not "://" in redirection:
        redirection = "http://" + redirection
    redirect(redirection, 303)

@app.route('/shutdown')
def shutdown():
    Thread(target=shutdown_server).start()
    return 'Stopping Server...'

def shutdown_server():
    time.sleep(3)
    pid = os.getpid()
    os.kill(pid, signal.SIGINT)

app.run(host='0.0.0.0', port=80)

