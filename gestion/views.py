from django.shortcuts import render, redirect
from .db_utils import get_connection
from datetime import datetime

def index(request):
    if 'admin_id' not in request.session:
        return redirect('login_view')
    
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        cur.execute('SELECT COUNT(*) FROM "TERAPEUTAS_INFO" WHERE "DISPONIBLE" = 1')
        total_terapeutas = cur.fetchone()[0]

        cur.execute('SELECT COUNT(DISTINCT "Id_Paciente") FROM "Sesiones"')
        pacientes_activos = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM \"Salud_Caballo\" WHERE \"Estado_Fisico\" = 'Saludable'")
        caballos_ok = cur.fetchone()[0]
        
    except Exception as e:
        print(f"Error en las consultas de index: {e}")
        total_terapeutas = pacientes_activos = caballos_ok = 0
    finally:
        conn.close()
    
    context = {
        'total_terapeutas': total_terapeutas,
        'pacientes_activos': pacientes_activos,
        'caballos_ok': caballos_ok,
        'admin_nombre': request.session.get('admin_nombre')
    }
    
    return render(request, 'gestion/index.html', context)

def login_view(request):
    error = None
    if request.method == 'POST':
        usuario_ingresado = request.POST.get('usuario').strip()
        contrasena_ingresada = request.POST.get('contraseña').strip()

        conn = get_connection()
        cur = conn.cursor()

        query = 'SELECT ID_PERSONA, PASSWORD, NOMBRE FROM PERSONAS WHERE NOMBRE = ? AND ES_ADMIN = 1'
        cur.execute(query, (usuario_ingresado,))
        usuario = cur.fetchone()
        conn.close()

        if usuario:
            db_id, db_pass, db_nombre = usuario
            
            if db_pass.strip() == contrasena_ingresada:
                request.session['admin_id'] = db_id
                request.session['admin_nombre'] = db_nombre
                return redirect('index')
            else:
                error = "Contraseña incorrecta."
        else:
            error = "Usuario no encontrado o no tiene permisos de administrador."
            
    return render(request, 'gestion/login.html', {'error': error})

def logout_view(request):
    request.session.flush()
    return redirect('login_view')

def lista_pacientes(request):
    if 'admin_id' not in request.session: return redirect('login_view')
    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre_paciente = request.POST.get('nombre')
        id_padre = request.POST.get('id_padre')
        fecha_nac = request.POST.get('fecha_nac')
        diagnostico = request.POST.get('diagnostico')
        
        # 1. Insertar en PERSONAS
        cur.execute("INSERT INTO PERSONAS (NOMBRE, ROL) VALUES (?, 'Paciente') RETURNING ID_PERSONA", (nombre_paciente,))
        nuevo_id = cur.fetchone()[0]
        
        # 2. Insertar en PACIENTES_INFO (Usando los nombres de tu tabla en la imagen 4)
        cur.execute("""
            INSERT INTO PACIENTES_INFO (Id_Paciente, Id_Padre, Fecha_Nac, Diagnostico) 
            VALUES (?, ?, ?, ?)
        """, (nuevo_id, id_padre, fecha_nac, diagnostico))
        
        conn.commit()
        conn.close()
        return redirect('lista_pacientes')

    # Obtenemos la lista de padres para el selector del formulario
    cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE ROL = 'Padre'")
    padres = cur.fetchall()

    # Obtenemos la lista de pacientes ya registrados para la tabla
    cur.execute("""
        SELECT p.NOMBRE, padre.NOMBRE, pi.Diagnostico 
        FROM PERSONAS p
        JOIN PACIENTES_INFO pi ON p.ID_PERSONA = pi.Id_Paciente
        JOIN PERSONAS padre ON pi.Id_Padre = padre.ID_PERSONA
    """)
    pacientes = cur.fetchall()
    conn.close()
    
    return render(request, 'gestion/pacientes.html', {'pacientes': pacientes, 'padres': padres})

def lista_terapeutas(request):
    if 'admin_id' not in request.session: return redirect('login_view')
    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        especialidad = request.POST.get('especialidad')
        
        # Insertar datos
        cur.execute("INSERT INTO PERSONAS (NOMBRE, ROL) VALUES (?, 'Terapeuta') RETURNING ID_PERSONA", (nombre,))
        nuevo_id = cur.fetchone()[0]
        cur.execute("INSERT INTO TERAPEUTAS_INFO (ID_TERAPEUTA, ESPECIALIDAD, DISPONIBLE) VALUES (?, ?, 1)", (nuevo_id, especialidad))
        conn.commit()
        conn.close() # Cerramos antes de irnos
        
        # ¡ESTA ES LA CLAVE! Redireccionamos a la misma vista para "limpiar" el formulario
        return redirect('lista_terapeutas') 

    # Si es GET (o después del redirect), cargamos la lista normal
    query = """
        SELECT p.ID_PERSONA, p.NOMBRE, t.ESPECIALIDAD, t.DISPONIBLE 
        FROM PERSONAS p
        JOIN TERAPEUTAS_INFO t ON p.ID_PERSONA = t.ID_TERAPEUTA
    """
    cur.execute(query)
    terapeutas = cur.fetchall()
    conn.close()
    return render(request, 'gestion/terapeutas.html', {'terapeutas': terapeutas})

def lista_caballos(request):
    if 'admin_id' not in request.session: 
        return redirect('login_view')
    
    conn = get_connection()
    cur = conn.cursor()
    
    # --- PROCESAR FORMULARIO PARA AGREGAR CABALLO (POST) ---
    if request.method == 'POST':
        nombre = request.POST.get('nombre_c')
        raza = request.POST.get('raza')
        disponibilidad = request.POST.get('disponibilidad')
        
        try:
            # Al ser Identity, omitimos por completo ID_CABALLO en el INSERT
            # Colocamos las columnas en el orden exacto de tu estructura SQL
            query_insert = """
                INSERT INTO CABALLOS (NOMBRE_C, RAZA, ESTADO_DISPONIBILIDAD) 
                VALUES (?, ?, ?)
            """
            cur.execute(query_insert, (nombre, raza, disponibilidad))
            conn.commit()
            print(f"DEBUG: ¡Caballo '{nombre}' guardado exitosamente!")
            return redirect('lista_caballos')
            
        except Exception as e:
            print(f"Error crítico al insertar caballo: {e}")
        finally:
            conn.close()
            conn = get_connection()
            cur = conn.cursor()

    # --- LISTAR CABALLOS EN LA TABLA (GET) ---
    try:
        # Aseguramos el orden correcto: ID(0), Nombre(1), Raza(2), Disponibilidad(3), Salud(4)
        query_select = """
            SELECT c.ID_CABALLO, c.NOMBRE_C, c.RAZA, c.ESTADO_DISPONIBILIDAD, s.ESTADO_FISICO
            FROM CABALLOS c
            LEFT JOIN SALUD_CABALLO s ON c.ID_CABALLO = s.ID_CABALLO
        """
        cur.execute(query_select)
        datos = cur.fetchall()
        
        caballos = []
        for fila in datos:
            caballos.append([str(col).strip() if col is not None else "" for col in fila])
            
    except Exception as e:
        print(f"Error al listar caballos: {e}")
        caballos = []
    finally:
        conn.close()
        
    return render(request, 'gestion/caballos.html', {
        'caballos': caballos,
        'admin_nombre': request.session.get('admin_nombre')
    })
    
def lista_padres(request):
    if 'admin_id' not in request.session: 
        return redirect('login_view')
    
    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        
        # Insertamos en PERSONAS con el rol correspondiente
        cur.execute("INSERT INTO PERSONAS (NOMBRE, ROL) VALUES (?, 'Padre') RETURNING ID_PERSONA", (nombre,))
        conn.commit()
        conn.close()
        return redirect('lista_padres') 

    # Consultamos solo a los que tienen rol de Padre
    cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE ROL = 'Padre'")
    padres = cur.fetchall()
    conn.close()
    
    return render(request, 'gestion/padres.html', {'padres': padres})

def agendar_cita(request):
    # Verificación de sesión según tu flujo actual
    if 'admin_id' not in request.session:
        return redirect('login_view')

    conn = get_connection()
    cur = conn.cursor()

    # --- LÓGICA PARA GUARDAR LA CITA (POST) ---
    if request.method == 'POST':
        id_paciente = request.POST.get('paciente')
        id_terapeuta = request.POST.get('terapeuta')
        id_caballo = request.POST.get('caballo')
        fecha = request.POST.get('fecha')
        hora = request.POST.get('hora')
        
        # Combinar fecha y hora para el campo TIMESTAMP de Firebird
        fecha_hora = f"{fecha} {hora}"

        try:
            # Usamos los nombres de tabla en MAYÚSCULAS como se ve en tu terminal
            query_insert = """
                INSERT INTO SESIONES (ID_PACIENTE, ID_TERAPEUTA, ID_CABALLO, FECHA_HORA, ESTADO_SESION) 
                VALUES (?, ?, ?, ?, 'Programada')
            """
            cur.execute(query_insert, (id_paciente, id_terapeuta, id_caballo, fecha_hora))
            conn.commit()
            return redirect('index')
        except Exception as e:
            print(f"Error al insertar sesión: {e}")
        finally:
            # Cerramos esta conexión antes de continuar o terminar
            conn.close()
            # Si entramos por POST y falló o terminó, necesitamos reabrir para los selects
            conn = get_connection()
            cur = conn.cursor()

    # --- CARGA DE DATOS PARA LOS SELECTORES ---
    pacientes = []
    terapeutas = []
    caballos = []

    try:
        # 1. Pacientes: Usamos TRIM y UPPER para máxima compatibilidad
        cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'PACIENTE'")
        pacientes = [(p[0], str(p[1]).strip()) for p in cur.fetchall()]

        # 2. Terapeutas
        cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'TERAPEUTA'")
        terapeutas = [(t[0], str(t[1]).strip()) for t in cur.fetchall()]

        # 3. Caballos
        cur.execute("SELECT ID_CABALLO, NOMBRE_C FROM CABALLOS WHERE UPPER(TRIM(ESTADO_DISPONIBILIDAD)) = 'DISPONIBLE'")
    # Limpiamos espacios en blanco para que el selector no falle
        caballos = [(c[0], str(c[1]).strip()) for c in cur.fetchall()]

        # Imprime esto en tu consola de Linux/VS Code para confirmar que ya hay datos
        print(f"DEBUG: {len(pacientes)} pacientes y {len(terapeutas)} terapeutas cargados.")

    except Exception as e:
        print(f"Error al consultar catálogos: {e}")
    finally:
        conn.close()

    # Renderizado con los datos limpios
    return render(request, 'gestion/agendar.html', {
        'pacientes': pacientes,
        'terapeutas': terapeutas,
        'caballos': caballos,
        'admin_nombre': request.session.get('admin_nombre')
    })