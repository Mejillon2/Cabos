import os
import firebird.driver as fdb
from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv('DB_PATH')

def get_connection():
    return fdb.connect(
        database=DB_PATH,
        user='SYSDBA',
        password='1234',
        charset='UTF-8'
    )