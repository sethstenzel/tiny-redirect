# TinyRedirect
A small python server utility for redirecting around the local network.

!["Tiny Redirect App Screenshot"](imgs/tr1.jpg)

## Installation / Running

Tested on Python version 3.10 and 3.13.1, any version other than that and YMMV.

1. Clone the repo
2. Create a new virtual env with `python -m venv env`
3. Activate your new env with `.\env\Scripts\activate`
4. Install the required python packages with `python -m pip install -r requirements.txt`
5. Add and entry to your host file `127.0.0.1 r`.
   - you can use anything you want for the server name, I choose 'r' for redirect, you can make it whatever you want. 
6. Run the server with python `python main.py`

## If things go wrong

The data.db file can be deleted if something goes crazy and will be rebuilt on first run.
Also you can use the `--defaults` flag when starting the server and it will assume default options instead of what is in the settings db table.
ex: `python tiny_redirect.py --defaults`
