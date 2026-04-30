import firebird.driver as fdb

def get_connection():
    # Nota: Usamos la ruta absoluta del archivo que movimos
    return fdb.connect('localhost:/var/firebird/data/sistema_equinoterapia.fdb', 
                       user='SYSDBA', 
                       password='1234')