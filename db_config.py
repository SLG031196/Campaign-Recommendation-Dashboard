# db_config.py
import mysql.connector

def get_connection():
    return mysql.connector.connect(
        host="dataanalystdb.dinerotesting.com",
        user="jatin",
        password="57nOthuwo*a4ep!E@Ru_R",
        database="DataAnalyst_Jatin"
    )
