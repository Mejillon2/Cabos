import os
import firebird.driver as fdb
from dotenv import load_dotenv

load_dotenv()

# Apuntamos formalmente a la dirección IP de tu nodo de datos remoto
DB_PATH = 'localhost:/var/firebird/data/sistema_equinoterapia.fdb'

def get_connection():
    return fdb.connect(
        database=DB_PATH,
        user='SYSDBA',
        password='1234',  # Tu contraseña asignada al motor de la VM
        charset='UTF-8'
    )