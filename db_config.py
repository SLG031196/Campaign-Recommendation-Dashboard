# db_config.py
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host=" ",
        user=" ",
        password=" ",
        database=" "
    )

