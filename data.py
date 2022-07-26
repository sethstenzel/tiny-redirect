import sqlite3

def dict_factory(cursor, row):
    dictionary = {}
    for idx, col in enumerate(cursor.description):
        dictionary[col[0]] = row[idx]
    return dictionary

def load_settings(data):
    connection = sqlite3.connect("data.db")  
    connection.row_factory = dict_factory
    cursor = connection.cursor()
    sql_query = 'SELECT * FROM settings'

    cursor.execute(sql_query)
    data["settings"] = cursor.fetchone()
    connection.close()
    return data

def load_redirects(data):
    connection = sqlite3.connect("data.db")  
    connection.row_factory = dict_factory
    cursor = connection.cursor()
    sql_query = 'SELECT * FROM redirects'

    cursor.execute(sql_query)
    data["redirects"] = cursor.fetchone()
    connection.close()
    return data

def load_data():
    data = {
        "settings":"",
        "redirects":"",
    }
    data = load_settings(data)
    data = load_redirects(data)
    return data

