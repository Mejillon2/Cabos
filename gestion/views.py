from django.shortcuts import render, redirect
from .db_utils import get_connection

def index(request):
    if 'admin_id' not in request.session:
        return redirect('login_view')
    
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT ID_PERSONA, NOMBRE, ROL FROM PERSONAS")
    personas = cur.fetchall()
    conn.close()
    
    return render(request, 'gestion/index.html', {'personas': personas})

def login_view(request):
    error = None
    
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        password = request.POST.get('password')
        
        try:
            conn = get_connection()
            cur = conn.cursor()
            
            query = "SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE NOMBRE = ? AND ID_PERSONA = ? AND ES_ADMIN = 1"
            cur.execute(query, (nombre, password))
            user = cur.fetchone()
            conn.close()
            
            if user:
                
                request.session['admin_id'] = user[0]
                request.session['admin_nombre'] = user[1]
                return redirect('index')
            else:
                error = "Credenciales incorrectas o no tienes permisos de administrador."
                
        except Exception as e:
            error = f"Error de conexión: {e}"

    return render(request, 'gestion/login.html', {'error': error})

def logout_view(request):
    request.session.flush()
    return redirect('login_view')

def lista_pacientes(request):
    if 'admin_id' not in request.session:
        return redirect('login_view')

    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT p.ID_PERSONA, p.NOMBRE, i.FECHA_NAC, i.DIAGNOSTICO 
        FROM PERSONAS p
        JOIN PACIENTES_INFO i ON p.ID_PERSONA = i.ID_PACIENTE
    """
    cur.execute(query)
    pacientes = cur.fetchall()
    conn.close()
    
    return render(request, 'gestion/pacientes.html', {'pacientes': pacientes})