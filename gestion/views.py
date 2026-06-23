import re
from django.shortcuts import render, redirect
from .db_utils import get_connection
from datetime import datetime

def index(request):
    # Verificación global de sesión usando la clave unificada
    if 'usuario_id' not in request.session: 
        return redirect('login_view')
    
    rol = request.session.get('rol', '').upper().strip()
    usuario_id = request.session.get('usuario_id')
    nombre_usuario = request.session.get('usuario_nombre', 'Usuario')

    conn = get_connection()
    cur = conn.cursor()

    try:
        # ==========================================
        # VISTA 1: ADMINISTRADOR (Ve todo el sistema)
        # ==========================================
        if rol in ['ADMINISTRADOR', 'ADMIN']:
            # 1. Contar total de terapeutas registrados
            cur.execute("SELECT COUNT(*) FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'TERAPEUTA'")
            total_terapeutas = cur.fetchone()[0]

            # 2. Contar pacientes únicos que tienen alguna sesión programada
            cur.execute("SELECT COUNT(DISTINCT ID_PACIENTE) FROM SESIONES WHERE UPPER(TRIM(ESTADO_SESION)) = 'PROGRAMADA'")
            pacientes_con_sesion = cur.fetchone()[0]

            # 3. Contar caballos disponibles directamente desde tu tabla CABALLOS
            cur.execute("SELECT COUNT(*) FROM CABALLOS WHERE UPPER(TRIM(ESTADO_DISPONIBILIDAD)) = 'DISPONIBLE'")
            caballos_saludables = cur.fetchone()[0]
            conn.close()
            
            # Mandamos las variables limpias al HTML
            return render(request, 'gestion/index_admin.html', {
                'admin_nombre': nombre_usuario,
                'total_terapeutas': total_terapeutas,
                'pacientes_con_sesion': pacientes_con_sesion,
                'caballos_saludables': caballos_saludables
            })

        # ==========================================
        # VISTA 2: TERAPEUTA (Solo ve sus sesiones)
        # ==========================================
        elif rol == 'TERAPEUTA':
            query_terapeuta = """
                SELECT P.NOMBRE AS PACIENTE, C.NOMBRE_C AS CABALLO, S.FECHA_HORA 
                FROM SESIONES S
                JOIN PERSONAS P ON S.ID_PACIENTE = P.ID_PERSONA
                JOIN CABALLOS C ON S.ID_CABALLO = C.ID_CABALLO
                WHERE S.ID_TERAPEUTA = ? AND S.ESTADO_SESION = 'Programada'
                ORDER BY S.FECHA_HORA ASC
            """
            cur.execute(query_terapeuta, (usuario_id,))
            sesiones = cur.fetchall()
            conn.close()
            
            return render(request, 'gestion/index_terapeuta.html', {
                'nombre_usuario': nombre_usuario,
                'sesiones': sesiones
            })

        # ==========================================
        # VISTA 3: PADRE (Ventana de Notificaciones)
        # ==========================================
        elif rol == 'PADRE':
            # Nota: Buscamos las sesiones donde el ID_PACIENTE coincide con el ID de la persona (hijo o cuenta vinculada)
            query_padre = """
                SELECT T.NOMBRE AS TERAPEUTA, C.NOMBRE_C AS CABALLO, S.FECHA_HORA 
                FROM SESIONES S
                JOIN PERSONAS T ON S.ID_TERAPEUTA = T.ID_PERSONA
                JOIN CABALLOS C ON S.ID_CABALLO = C.ID_CABALLO
                WHERE S.ID_PACIENTE = ? AND S.ESTADO_SESION = 'Programada'
                ORDER BY S.FECHA_HORA DESC
            """
            cur.execute(query_padre, (usuario_id,))
            notificaciones = cur.fetchall()
            conn.close()
            
            return render(request, 'gestion/index_padre.html', {
                'nombre_usuario': nombre_usuario,
                'notificaciones': notificaciones
            })

    except Exception as e:
        print(f"Error al cargar la vista por roles: {e}")
        if conn: conn.close()
        
    return redirect('login_view')


def login_view(request):
    error = None
    if request.method == 'POST':
        usuario_ingresado = request.POST.get('usuario').strip()
        contrasena_ingresada = request.POST.get('contraseña').strip()

        # 1. Definición de las Expresiones Regulares según tus formatos estrictos
        regex_usuario = r'^(AD|TE|PA)_\d{2}#$'
        regex_password = r'^\d{2}_#(AD|TE|PA)#$'

        # 2. Validar formatos antes de hacer consultas SQL
        if not re.match(regex_usuario, usuario_ingresado):
            error = "El formato del usuario es inválido (Ej: AD_01#)."
        elif not re.match(regex_password, contrasena_ingresada):
            error = "El formato de la contraseña es inválido (Ej: 01_#AD#)."
        else:
            # 3. Extraer el prefijo (AD, TE o PA) para guiar la lógica
            prefijo_rol = usuario_ingresado.split('_')[0]

            conn = get_connection()
            cur = conn.cursor()

            # 4. Ajustar la consulta según el tipo de rol y la estructura de tu BD
            if prefijo_rol == 'AD':
                # El administrador se valida con la columna ES_ADMIN = 1
                query = 'SELECT ID_PERSONA, PASSWORD, NOMBRE, ROL, ES_ADMIN FROM PERSONAS WHERE USUARIO = ? AND ES_ADMIN = 1'
                cur.execute(query, (usuario_ingresado,))
            else:
                # Terapeutas o Padres se validan con su respectivo ROL del CHECK
                mapa_roles = {'TE': 'Terapeuta', 'PA': 'Padre'}
                rol_esperado = mapa_roles.get(prefijo_rol)
                
                query = 'SELECT ID_PERSONA, PASSWORD, NOMBRE, ROL, ES_ADMIN FROM PERSONAS WHERE USUARIO = ? AND UPPER(TRIM(ROL)) = UPPER(?)'
                cur.execute(query, (usuario_ingresado, rol_esperado))

            usuario = cur.fetchone()
            conn.close()

            # 5. Procesar el resultado físico obtenido de Firebird
            if usuario:
                db_id, db_pass, db_nombre, db_rol, db_es_admin = usuario
                db_pass_clean = str(db_pass).strip() if db_pass is not None else ""
                
                # Asignamos la etiqueta que tu función 'index' está esperando
                if db_es_admin == 1:
                    rol_sesion = 'ADMINISTRADOR'
                else:
                    rol_sesion = str(db_rol).strip().upper()

                # 6. Validar contraseña
                if db_pass_clean == contrasena_ingresada:
                    # Guardamos los parámetros unificados en las variables de sesión de Django
                    request.session['usuario_id'] = db_id
                    request.session['usuario_nombre'] = db_nombre
                    request.session['rol'] = rol_sesion
                    
                    # Redirección directa al enrutador de pantallas
                    return redirect('index')
                else:
                    error = "Contraseña incorrecta."
            else:
                error = "El usuario no se encuentra registrado o el rol no coincide."
            
    return render(request, 'gestion/login.html', {'error': error})


def logout_view(request):
    request.session.flush()
    return redirect('login_view')

def lista_pacientes(request):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
        
    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre_paciente = request.POST.get('nombre')
        id_padre = request.POST.get('id_padre')
        fecha_nac = request.POST.get('fecha_nac')
        diagnostico = request.POST.get('diagnostico')
        
        cur.execute("INSERT INTO PERSONAS (NOMBRE, ROL) VALUES (?, 'Paciente') RETURNING ID_PERSONA", (nombre_paciente,))
        nuevo_id = cur.fetchone()[0]
        
        cur.execute("""
            INSERT INTO PACIENTES_INFO (Id_Paciente, Id_Padre, Fecha_Nac, Diagnostico) 
            VALUES (?, ?, ?, ?)
        """, (nuevo_id, id_padre, fecha_nac, diagnostico))
        
        conn.commit()
        conn.close()
        return redirect('lista_pacientes')

    cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE ROL = 'Padre'")
    padres = cur.fetchall()

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
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
        
    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        especialidad = request.POST.get('especialidad')
        
        cur.execute("INSERT INTO PERSONAS (NOMBRE, ROL) VALUES (?, 'Terapeuta') RETURNING ID_PERSONA", (nombre,))
        nuevo_id = cur.fetchone()[0]
        cur.execute("INSERT INTO TERAPEUTAS_INFO (ID_TERAPEUTA, ESPECIALIDAD, DISPONIBLE) VALUES (?, ?, 1)", (nuevo_id, especialidad))
        conn.commit()
        conn.close()
        return redirect('lista_terapeutas') 

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
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
        
    conn = get_connection()
    cur = conn.cursor()

    # Si el formulario envía datos por POST, es una inserción (CREATE)
    if request.method == 'POST':
        nombre = request.POST.get('nombre_c')
        raza = request.POST.get('raza')
        edad = request.POST.get('edad')
        disponibilidad = request.POST.get('estado_disponibilidad')

        # Manejo de nulos para la edad si viene vacía
        edad_val = int(edad) if edad else None

        try:
            cur.execute("""
                INSERT INTO CABALLOS (NOMBRE_C, RAZA, EDAD, ESTADO_DISPONIBILIDAD) 
                VALUES (?, ?, ?, ?)
            """, (nombre, raza, edad_val, disponibilidad))
            conn.commit()
        except Exception as e:
            print(f"Error al insertar caballo: {e}")
        finally:
            conn.close()
        return redirect('lista_caballos')

    # Si es GET, simplemente listamos los caballos existentes (READ)
    cur.execute("SELECT ID_CABALLO, NOMBRE_C, RAZA, EDAD, ESTADO_DISPONIBILIDAD FROM CABALLOS ORDER BY ID_CABALLO DESC")
    caballos_raw = cur.fetchall()
    
    # Limpieza de espacios en blanco de Firebird
    caballos = []
    for fila in caballos_raw:
        caballos.append([str(col).strip() if col is not None else "" for col in fila])

    conn.close()
    return render(request, 'gestion/caballos.html', {'caballos': caballos})


# 2. ACTUALIZAR (UPDATE)
def editar_caballo(request, id_caballo):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')

    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre = request.POST.get('nombre_c')
        raza = request.POST.get('raza')
        edad = request.POST.get('edad')
        disponibilidad = request.POST.get('estado_disponibilidad')
        edad_val = int(edad) if edad else None

        cur.execute("""
            UPDATE CABALLOS 
            SET NOMBRE_C = ?, RAZA = ?, EDAD = ?, ESTADO_DISPONIBILIDAD = ? 
            WHERE ID_CABALLO = ?
        """, (nombre, raza, edad_val, disponibilidad, id_caballo))
        conn.commit()
        conn.close()
        return redirect('lista_caballos')

    # Obtener los datos actuales del caballo para precargar el formulario
    cur.execute("SELECT ID_CABALLO, NOMBRE_C, RAZA, EDAD, ESTADO_DISPONIBILIDAD FROM CABALLOS WHERE ID_CABALLO = ?", (id_caballo,))
    fila = cur.fetchone()
    conn.close()

    caballo = [str(col).strip() if col is not None else "" for col in fila] if fila else None
    return render(request, 'gestion/editar_caballo.html', {'caballo': caballo})


# 3. ELIMINAR (DELETE)
def eliminar_caballo(request, id_caballo):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')

    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM CABALLOS WHERE ID_CABALLO = ?", (id_caballo,))
        conn.commit()
    except Exception as e:
        print(f"Error al eliminar: {e}") # Por si tiene llaves foráneas activas
    finally:
        conn.close()
        
    return redirect('lista_caballos')
    

def lista_padres(request):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
    
    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        
        cur.execute("INSERT INTO PERSONAS (NOMBRE, ROL) VALUES (?, 'Padre') RETURNING ID_PERSONA", (nombre,))
        conn.commit()
        conn.close()
        return redirect('lista_padres') 
    
    cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE ROL = 'Padre'")
    padres = cur.fetchall()
    conn.close()
    
    return render(request, 'gestion/padres.html', {'padres': padres})


def agendar_cita(request):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')

    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        id_paciente = request.POST.get('paciente')
        id_terapeuta = request.POST.get('terapeuta')
        id_caballo = request.POST.get('caballo')
        fecha = request.POST.get('fecha')
        hora = request.POST.get('hora')
        
        fecha_hora = f"{fecha} {hora}"

        try:
            query_insert = """
                INSERT INTO SESIONES (ID_PACIENTE, ID_TERAPEUTA, ID_CABALLO, FECHA_HORA, ESTADO_SESION) 
                VALUES (?, ?, ?, ?, 'Programada')
            """
            cur.execute(query_insert, (id_paciente, id_terapeuta, id_caballo, fecha_hora))
            
            query_update_caballo = """
                UPDATE CABALLOS 
                SET ESTADO_DISPONIBILIDAD = 'NO DISPONIBLE' 
                WHERE ID_CABALLO = ?
            """
            cur.execute(query_update_caballo, (id_caballo,))

            conn.commit()
            return redirect('index')
        except Exception as e:
            print(f"Error al insertar sesión o actualizar estados: {e}")
        finally:
            conn.close()
            conn = get_connection()
            cur = conn.cursor()

    pacientes = []
    terapeutas = []
    caballos = []

    try:
        query_pacientes_libres = """
            SELECT P.ID_PERSONA, P.NOMBRE 
            FROM PERSONAS P
            WHERE UPPER(TRIM(P.ROL)) = 'PACIENTE'
            AND P.ID_PERSONA NOT IN (
                SELECT S.ID_PACIENTE 
                FROM SESIONES S 
                WHERE S.ESTADO_SESION = 'Programada'
            )
        """
        cur.execute(query_pacientes_libres)
        pacientes = [(p[0], str(p[1]).strip()) for p in cur.fetchall()]

        cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE ROL = 'Terapeuta'")
        terapeutas = [(t[0], str(t[1]).strip()) for t in cur.fetchall()]

        cur.execute("SELECT ID_CABALLO, NOMBRE_C FROM CABALLOS WHERE UPPER(TRIM(ESTADO_DISPONIBILIDAD)) = 'DISPONIBLE'")
        caballos = [(c[0], str(c[1]).strip()) for c in cur.fetchall()]

    except Exception as e:
        print(f"Error al consultar catálogos: {e}")
    finally:
        conn.close()

    return render(request, 'gestion/agendar.html', {
        'pacientes': pacientes,
        'terapeutas': terapeutas,
        'caballos': caballos,
        'admin_nombre': request.session.get('usuario_nombre')
    })

def lista_reportes(request):
    # Seguridad: Solo el administrador puede ver reportes
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
        
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    
    conn = get_connection()
    cur = conn.cursor()
    
    # Consulta base para traer el historial analítico de las sesiones
    query = """
        SELECT p_pac.NOMBRE AS PACIENTE, p_ter.NOMBRE AS TERAPEUTA, c.NOMBRE_C AS CABALLO, s.FECHA_HORA, s.ESTADO_SESION
        FROM SESIONES s
        JOIN PERSONAS p_pac ON s.ID_PACIENTE = p_pac.ID_PERSONA
        JOIN PERSONAS p_ter ON s.ID_TERAPEUTA = p_ter.ID_PERSONA
        JOIN CABALLOS c ON s.ID_CABALLO = c.ID_CABALLO
    """
    
    parametros = []
    
    # Si el usuario eligió fechas, filtramos dinámicamente en el WHERE
    if fecha_inicio and fecha_fin:
        query += " WHERE s.FECHA_HORA BETWEEN ? AND ?"
        parametros.extend([f"{fecha_inicio} 00:00:00", f"{fecha_fin} 23:59:59"])
    
    query += " ORDER BY s.FECHA_HORA DESC"
    
    cur.execute(query, parametros)
    sesiones_data = cur.fetchall()
    
    # Limpiamos posibles espacios en blanco de Firebird
    sesiones = []
    for fila in sesiones_data:
        sesiones.append([str(col).strip() if col is not None else "" for col in fila])
        
    conn.close()
    
    return render(request, 'gestion/reportes.html', {
        'sesiones': sesiones,
        'fecha_inicio': fecha_inicio,
        'fecha_fin': fecha_fin,
        'admin_nombre': request.session.get('usuario_nombre')
    })