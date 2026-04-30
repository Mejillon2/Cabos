import os
import firebird.driver as fdb
from dotenv import load_dotenv

load_dotenv()

DB_PATH = '127.0.0.1:/var/firebird/data/sistema_equinoterapia.fdb'

def get_connection():
    return fdb.connect(
        database=DB_PATH,
        user='SYSDBA',
        password='1234',
        charset='UTF8'
    )