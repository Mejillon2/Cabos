import re
from django.shortcuts import render, redirect
from .db_utils import get_connection
from datetime import datetime
from django.db import connection
from django.contrib import messages

def index(request):
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

            # 2. Contar TOTAL de pacientes en la clínica
            cur.execute("SELECT COUNT(*) FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'PACIENTE'")
            pacientes_totales = cur.fetchone()[0]

            # 3. Contar TOTAL de caballos en la clínica
            cur.execute("SELECT COUNT(*) FROM CABALLOS")
            caballos_totales = cur.fetchone()[0]
            
            conn.close()
            
            # CAMBIO AQUÍ: Nombres de variables idénticos a los de tu index_admin.html
            return render(request, 'gestion/index_admin.html', {
                'admin_nombre': nombre_usuario,
                'total_terapeutas': total_terapeutas,
                'total_pacientes': pacientes_totales,  # <-- Antes se llamaba pacientes_con_sesion
                'total_caballos': caballos_totales      # <-- Antes se llamaba caballos_saludables
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
            # CORRECCIÓN: Filtramos las sesiones cruzando con PACIENTES_INFO para validar el ID_PADRE
            query_padre = """
                SELECT T.NOMBRE AS TERAPEUTA, C.NOMBRE_C AS CABALLO, S.FECHA_HORA 
                FROM SESIONES S
                JOIN PERSONAS T ON S.ID_TERAPEUTA = T.ID_PERSONA
                JOIN CABALLOS C ON S.ID_CABALLO = C.ID_CABALLO
                JOIN PACIENTES_INFO PI ON S.ID_PACIENTE = PI.ID_PACIENTE
                WHERE PI.ID_PADRE = ? AND UPPER(TRIM(S.ESTADO_SESION)) = 'PROGRAMADA'
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

    # CORRECCIÓN: Se eliminó el espacio en t.ID_PACIENTE y se corrigió t.FECHA_NC a t.FECHA_NAC
    query_get = """
        SELECT p.ID_PERSONA, p.NOMBRE, p.TELEFONO, p.EMAIL, t.FECHA_NAC, t.DIAGNOSTICO 
        FROM PERSONAS p
        INNER JOIN PACIENTES_INFO t ON p.ID_PERSONA = t.ID_PACIENTE
        WHERE p.ROL = 'Paciente'
        ORDER BY p.ID_PERSONA DESC
    """
    
    cur.execute(query_get)
    pacientes_raw = cur.fetchall()
    
    pacientes = []
    for fila in pacientes_raw:
        registro = []
        for col in fila:
            if col is None:
                registro.append("")
            elif hasattr(col, 'read'):  # Control del BLOB text de Firebird
                registro.append(str(col.read()).strip())
            else:
                registro.append(str(col).strip())
        pacientes.append(registro)

    conn.close()
    return render(request, 'gestion/pacientes.html', {'pacientes': pacientes})

def editar_paciente(request, id_persona):
    # CORRECCIÓN DE SEGURIDAD: Usamos la misma validación basada en tu variable 'rol'
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
    
    # 1. Cuando el usuario entra a la página (GET), recuperamos los datos actuales
    if request.method == 'GET':
        conn = get_connection()
        cur = conn.cursor()
        
        # Hacemos el JOIN apuntando exactamente a tus tablas de Firebird
        cur.execute("""
            SELECT p.NOMBRE, p.TELEFONO, p.EMAIL, t.FECHA_NAC, t.DIAGNOSTICO 
            FROM PERSONAS p
            INNER JOIN PACIENTES_INFO t ON p.ID_PERSONA = t.ID_PACIENTE
            WHERE p.ID_PERSONA = ? AND p.ROL = 'Paciente'
        """, (id_persona,))
        row = cur.fetchone()
        conn.close()
            
        if not row:
            messages.error(request, "El paciente no existe.")
            return redirect('lista_pacientes')
        
        # Procesamos las columnas limpiando espacios vacíos o leyendo BLOBs si aplica
        datos_limpios = []
        for col in row:
            if col is None:
                datos_limpios.append("")
            elif hasattr(col, 'read'): # Por si el diagnóstico es un campo BLOB de Firebird
                datos_limpios.append(str(col.read()).strip())
            else:
                datos_limpios.append(str(col).strip())

        # Estructuramos el diccionario para tu HTML
        paciente_data = {
            'nombre': datos_limpios[0],
            'telefono': datos_limpios[1],
            'email': datos_limpios[2],
            'fecha_nac': datos_limpios[3], # Viene como string limpio listo para el input date
            'diagnostico': datos_limpios[4]
        }
        
        return render(request, 'gestion/editar_paciente.html', {
            'id_persona': id_persona,
            'paciente_data': paciente_data
        })

    # 2. Cuando el usuario presiona "Guardar Cambios" (POST)
    elif request.method == 'POST':
        nombre = request.POST.get('nombre')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '')
        fecha_nac = request.POST.get('fecha_nac')
        diagnostico = request.POST.get('diagnostico')
        
        conn = get_connection()
        cur = conn.cursor()
        try:
            # Actualizamos la tabla general PERSONAS
            cur.execute("""
                UPDATE PERSONAS 
                SET NOMBRE = ?, TELEFONO = ?, EMAIL = ? 
                WHERE ID_PERSONA = ? AND ROL = 'Paciente'
            """, (nombre, telefono, correo, id_persona))
            
            # Actualizamos la tabla de detalles clínicos PACIENTES_INFO
            cur.execute("""
                UPDATE PACIENTES_INFO 
                SET FECHA_NAC = ?, DIAGNOSTICO = ? 
                WHERE ID_PACIENTE = ?
            """, (fecha_nac, diagnostico, id_persona))
            
            conn.commit()
            messages.success(request, "Paciente actualizado correctamente.")
        except Exception as e:
            conn.rollback()
            print(f"Error al actualizar paciente: {e}")
            messages.error(request, f"Error al actualizar: {str(e)}")
        finally:
            conn.close()
            
        return redirect('lista_pacientes')

def eliminar_paciente(request, id_persona):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
        
    conn = get_connection()
    cur = conn.cursor()
    
    try:
        # 1. Primero borramos la información de la tabla dependiente
        cur.execute("DELETE FROM PACIENTES_INFO WHERE ID_PACIENTE = ?", (id_persona,))
        
        # 2. Después borramos el registro maestro en PERSONAS
        cur.execute("DELETE FROM PERSONAS WHERE ID_PERSONA = ? AND ROL = 'Paciente'", (id_persona,))
        
        conn.commit()
        messages.success(request, "Paciente eliminado correctamente.")
    except Exception as e:
        conn.rollback()
        print(f"Error al eliminar paciente: {e}")
        messages.error(request, f"No se pudo eliminar el paciente: {str(e)}")
    finally:
        conn.close()
        
    return redirect('lista_pacientes')

def lista_terapeutas(request):
    # CORRECCIÓN DE SEGURIDAD: Validamos usando la estructura correcta de tus otros módulos
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
        
    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '') # Proviene del input 'name="correo"' del HTML
        especialidad = request.POST.get('especialidad', '')
        
        try:
            # CORRECCIÓN: Se cambió la columna CORREO por EMAIL para coincidir con tu BD
            cur.execute("""
                INSERT INTO PERSONAS (NOMBRE, TELEFONO, EMAIL, ESPECIALIDAD, ROL) 
                VALUES (?, ?, ?, ?, 'Terapeuta')
            """, (nombre, telefono, correo, especialidad))
            conn.commit()
            messages.success(request, f"Terapeuta '{nombre}' registrado con éxito.")
        except Exception as e:
            print(f"Error al insertar terapeuta: {e}")
            messages.error(request, f"Error al guardar: {str(e)}")
        finally:
            conn.close()
        return redirect('lista_terapeutas')

    # =================================================================
    # GET: Consultamos limpiamente los registros en una sola línea
    # =================================================================
    query_get = """
        SELECT p.ID_PERSONA, p.NOMBRE, p.TELEFONO, p.EMAIL, t.ESPECIALIDAD 
        FROM PERSONAS p
        INNER JOIN TERAPEUTAS_INFO t ON p.ID_PERSONA = t.ID_TERAPEUTA
        WHERE p.ROL = 'Terapeuta'
        ORDER BY p.ID_PERSONA DESC
    """
    
    cur.execute(query_get)
    terapeutas_raw = cur.fetchall()
    
    # Limpieza de espacios en blanco de Firebird
    terapeutas = []
    for fila in terapeutas_raw:
        terapeutas.append([str(col).strip() if col is not None else "" for col in fila])

    conn.close()
    return render(request, 'gestion/terapeutas.html', {'terapeutas': terapeutas})


def editar_terapeuta(request, id_persona):
    # CORRECCIÓN DE SEGURIDAD: Validamos usando la estructura correcta
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')

    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '')  # Este es el valor que viene del formulario HTML
        especialidad = request.POST.get('especialidad', '')
        
        try:
            # 1. Actualizamos los datos generales en la tabla PERSONAS (usando la columna EMAIL)
            cur.execute("""
                UPDATE PERSONAS 
                SET NOMBRE = ?, TELEFONO = ?, EMAIL = ? 
                WHERE ID_PERSONA = ? AND ROL = 'Terapeuta'
            """, (nombre, telefono, correo, id_persona))
            
            # 2. Actualizamos la especialidad en la tabla TERAPEUTAS_INFO
            cur.execute("""
                UPDATE TERAPEUTAS_INFO 
                SET ESPECIALIDAD = ? 
                WHERE ID_TERAPEUTA = ?
            """, (especialidad, id_persona))
            
            conn.commit()
            messages.success(request, f"Datos del terapeuta '{nombre}' actualizados correctamente.")
            conn.close()
            return redirect('lista_terapeutas')
        except Exception as e:
            conn.rollback() # Buena práctica: si algo falla, deshacemos cualquier cambio parcial
            print(f"Error al actualizar terapeuta: {e}")
            messages.error(request, f"Error al actualizar el registro: {str(e)}")
            conn.close()

    # =================================================================
    # GET: Obtener la información actual uniendo ambas tablas (JOIN)
    # =================================================================
    cur.execute("""
        SELECT p.ID_PERSONA, p.NOMBRE, p.TELEFONO, p.EMAIL, t.ESPECIALIDAD 
        FROM PERSONAS p
        INNER JOIN TERAPEUTAS_INFO t ON p.ID_PERSONA = t.ID_TERAPEUTA
        WHERE p.ID_PERSONA = ? AND p.ROL = 'Terapeuta'
    """, (id_persona,))
    
    fila = cur.fetchone()
    conn.close()

    if not fila:
        messages.error(request, "El terapeuta solicitado no existe.")
        return redirect('lista_terapeutas')

    # Limpieza de espacios en blanco típicos de Firebird
    terapeuta = [str(col).strip() if col is not None else "" for col in fila]
    return render(request, 'gestion/editar_terapeuta.html', {'terapeuta': terapeuta})

def eliminar_terapeuta(request, id_persona):
    # CORRECCIÓN DE SEGURIDAD: Validamos usando la estructura correcta
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
        
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM PERSONAS WHERE ID_PERSONA = ? AND UPPER(TRIM(ROL)) = 'TERAPEUTA'", (id_persona,))
        conn.commit()
        messages.success(request, "Terapeuta eliminado correctamente.")
    except Exception as e:
        print(f"Error al eliminar terapeuta: {e}")
        messages.error(request, f"No se pudo eliminar el registro: {str(e)}")
    finally:
        conn.close()
        
    return redirect('lista_terapeutas')


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

    # Si se envía el formulario para registrar un nuevo padre
    if request.method == 'POST':
        nombre = request.POST.get('nombre')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '')
        
        try:
            cur.execute("""
                INSERT INTO PERSONAS (NOMBRE, TELEFONO, EMAIL, ROL) 
                VALUES (?, ?, ?, 'Padre')
            """, (nombre, telefono, correo))
            conn.commit()
            messages.success(request, f"Tutor '{nombre}' registrado correctamente.")
        except Exception as e:
            conn.rollback()
            messages.error(request, f"Error al registrar: {str(e)}")
        return redirect('lista_padres')

    # Consulta para listar a todos los registros con rol Padre
    query_get = """
        SELECT ID_PERSONA, NOMBRE, TELEFONO, EMAIL 
        FROM PERSONAS 
        WHERE ROL = 'Padre'
        ORDER BY ID_PERSONA DESC
    """
    cur.execute(query_get)
    padres_raw = cur.fetchall()
    
    padres = []
    for fila in padres_raw:
        registro = []
        for col in fila:
            if col is None:
                registro.append("")
            else:
                registro.append(str(col).strip())
        padres.append(registro)

    conn.close()
    return render(request, 'gestion/padres.html', {'padres': padres})


def editar_padres(request, id_persona):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
    
    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'GET':
        cur.execute("""
            SELECT NOMBRE, TELEFONO, EMAIL 
            FROM PERSONAS 
            WHERE ID_PERSONA = ? AND ROL = 'Padre'
        """, (id_persona,))
        row = cur.fetchone()
        conn.close()
            
        if not row:
            messages.error(request, "El tutor no existe.")
            return redirect('lista_padres')
        
        padre_data = {
            'nombre': str(row[0]).strip() if row[0] else "",
            'telefono': str(row[1]).strip() if row[1] else "",
            'email': str(row[2]).strip() if row[2] else ""
        }
        return render(request, 'gestion/editar_padre.html', {
            'id_persona': id_persona,
            'padre_data': padre_data
        })

    elif request.method == 'POST':
        nombre = request.POST.get('nombre')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '')
        
        try:
            cur.execute("""
                UPDATE PERSONAS 
                SET NOMBRE = ?, TELEFONO = ?, EMAIL = ? 
                WHERE ID_PERSONA = ? AND ROL = 'Padre'
            """, (nombre, telefono, correo, id_persona))
            conn.commit()
            messages.success(request, "Datos del tutor actualizados con éxito.")
        except Exception as e:
            conn.rollback()
            messages.error(request, f"Error al actualizar: {str(e)}")
        finally:
            conn.close()
            
        return redirect('lista_padres')


def eliminar_padres(request, id_persona):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
        
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM PERSONAS WHERE ID_PERSONA = ? AND ROL = 'Padre'", (id_persona,))
        conn.commit()
        messages.success(request, "Tutor eliminado correctamente.")
    except Exception as e:
        conn.rollback()
        messages.error(request, f"No se puede eliminar porque está asignado a un paciente.")
    finally:
        conn.close()
        
    return redirect('lista_padres')


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
            return redirect('agendar') # <-- Cambiado para que te regrese aquí mismo y veas la tabla actualizada
        except Exception as e:
            print(f"Error al insertar sesión o actualizar estados: {e}")
        finally:
            conn.close()

    pacientes = []
    terapeutas = []
    caballos = []
    sesiones = [] # <-- Lista para las sesiones existentes

    try:
        # 1. Tus consultas actuales de catálogos
        query_pacientes_libres = """
            SELECT P.ID_PERSONA, P.NOMBRE FROM PERSONAS P
            WHERE UPPER(TRIM(P.ROL)) = 'PACIENTE'
            AND P.ID_PERSONA NOT IN (SELECT S.ID_PACIENTE FROM SESIONES S WHERE S.ESTADO_SESION = 'Programada')
        """
        cur.execute(query_pacientes_libres)
        pacientes = [(p[0], str(p[1]).strip()) for p in cur.fetchall()]

        cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE ROL = 'Terapeuta'")
        terapeutas = [(t[0], str(t[1]).strip()) for t in cur.fetchall()]

        cur.execute("SELECT ID_CABALLO, NOMBRE_C FROM CABALLOS WHERE UPPER(TRIM(ESTADO_DISPONIBILIDAD)) = 'DISPONIBLE'")
        caballos = [(c[0], str(c[1]).strip()) for c in cur.fetchall()]

        # 2. NUEVA CONSULTA: Traer las sesiones programadas para la tabla
        query_sesiones = """
            SELECT 
                s.ID_SESION, 
                p.NOMBRE AS PACIENTE, 
                t.NOMBRE AS TERAPEUTA, 
                c.NOMBRE_C AS CABALLO, 
                s.FECHA_HORA, 
                s.ESTADO_SESION
            FROM SESIONES s
            INNER JOIN PERSONAS p ON s.ID_PACIENTE = p.ID_PERSONA
            INNER JOIN PERSONAS t ON s.ID_TERAPEUTA = t.ID_PERSONA
            INNER JOIN CABALLOS c ON s.ID_CABALLO = c.ID_CABALLO
            WHERE s.ESTADO_SESION = 'Programada'
            ORDER BY s.ID_SESION DESC
        """
        cur.execute(query_sesiones)
        for fila in cur.fetchall():
            sesiones.append([ "" if col is None else str(col).strip() for col in fila ])

    except Exception as e:
        print(f"Error al consultar catálogos: {e}")
    finally:
        conn.close()

    # Enviamos 'sesiones' al HTML
    return render(request, 'gestion/agendar.html', {
        'pacientes': pacientes,
        'terapeutas': terapeutas,
        'caballos': caballos,
        'sesiones': sesiones, # <-- Agregado
        'admin_nombre': request.session.get('usuario_nombre')
    })

def editar_cita(request, id_sesion):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
    
    conn = get_connection()
    cur = conn.cursor()

    if request.method == 'GET':
        try:
            # Obtener datos de la sesión actual
            cur.execute("""
                SELECT ID_PACIENTE, ID_TERAPEUTA, ID_CABALLO, FECHA_HORA 
                FROM SESIONES 
                WHERE ID_SESION = ?
            """, (id_sesion,))
            row = cur.fetchone()
            
            if not row:
                messages.error(request, "La sesión no existe.")
                return redirect('index')
            
            # row[3] es un objeto datetime gracias al tipo TIMESTAMP de Firebird
            dt_actual = row[3]
            fecha_val = dt_actual.strftime('%Y-%m-%d') if dt_actual else ""
            hora_val = dt_actual.strftime('%H:%M') if dt_actual else ""

            cita_data = {
                'id_paciente': row[0],
                'id_terapeuta': row[1],
                'id_caballo_actual': row[2],
                'fecha': fecha_val,
                'hora': hora_val
            }

            # Listar catálogos para renderizar los selectores
            cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'PACIENTE' ORDER BY NOMBRE")
            pacientes = [(p[0], str(p[1]).strip()) for p in cur.fetchall()]

            cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'TERAPEUTA' ORDER BY NOMBRE")
            terapeutas = [(t[0], str(t[1]).strip()) for t in cur.fetchall()]

            # Traer los caballos DISPONIBLES o el caballo asignado actualmente a esta cita
            cur.execute("""
                SELECT ID_CABALLO, NOMBRE_C 
                FROM CABALLOS 
                WHERE UPPER(TRIM(ESTADO_DISPONIBILIDAD)) = 'DISPONIBLE' OR ID_CABALLO = ?
                ORDER BY NOMBRE_C
            """, (cita_data['id_caballo_actual'],))
            caballos = [(c[0], str(c[1]).strip()) for c in cur.fetchall()]

        except Exception as e:
            print(f"Error al cargar datos de edición: {e}")
            messages.error(request, "Error al recuperar datos de la sesión.")
            return redirect('index')
        finally:
            conn.close()

        return render(request, 'gestion/editar_cita.html', {
            'id_sesion': id_sesion,
            'cita_data': cita_data,
            'pacientes': pacientes,
            'terapeutas': terapeutas,
            'caballos': caballos
        })

    elif request.method == 'POST':
        id_paciente = request.POST.get('paciente')
        id_terapeuta = request.POST.get('terapeuta')
        id_caballo_nuevo = request.POST.get('caballo')
        fecha = request.POST.get('fecha')
        hora = request.POST.get('hora')
        id_caballo_anterior = request.POST.get('id_caballo_anterior')
        
        # Combinar fecha y hora en cadena limpia para el TIMESTAMP
        fecha_hora_str = f"{fecha} {hora}:00"

        try:
            # 1. Actualizar la sesión
            query_update = """
                UPDATE SESIONES 
                SET ID_PACIENTE = ?, ID_TERAPEUTA = ?, ID_CABALLO = ?, FECHA_HORA = ? 
                WHERE ID_SESION = ?
            """
            cur.execute(query_update, (id_paciente, id_terapeuta, id_caballo_nuevo, fecha_hora_str, id_sesion))
            
            # 2. Si cambió el caballo co-terapeuta, alternar disponibilidades
            if str(id_caballo_nuevo) != str(id_caballo_anterior):
                if id_caballo_anterior:
                    cur.execute("""
                        UPDATE CABALLOS SET ESTADO_DISPONIBILIDAD = 'DISPONIBLE' WHERE ID_CABALLO = ?
                    """, (id_caballo_anterior,))
                if id_caballo_nuevo:
                    cur.execute("""
                        UPDATE CABALLOS SET ESTADO_DISPONIBILIDAD = 'NO DISPONIBLE' WHERE ID_CABALLO = ?
                    """, (id_caballo_nuevo,))

            conn.commit()
            messages.success(request, "Sesión reagendada correctamente.")
        except Exception as e:
            conn.rollback()
            print(f"Error al modificar sesión: {e}")
            messages.error(request, "No se pudo actualizar la sesión.")
        finally:
            conn.close()
            
        return redirect('index')


def eliminar_cita(request, id_sesion):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
        
    conn = get_connection()
    cur = conn.cursor()
    try:
        # Recuperar caballo antes de borrar la sesión
        cur.execute("SELECT ID_CABALLO FROM SESIONES WHERE ID_SESION = ?", (id_sesion,))
        row = cur.fetchone()
        
        if row and row[0]:
            # Liberar caballo
            cur.execute("""
                UPDATE CABALLOS 
                SET ESTADO_DISPONIBILIDAD = 'DISPONIBLE' 
                WHERE ID_CABALLO = ?
            """, (row[0],))

        # Eliminar sesión programada
        cur.execute("DELETE FROM SESIONES WHERE ID_SESION = ?", (id_sesion,))
        conn.commit()
        messages.success(request, "Sesión cancelada con éxito.")
    except Exception as e:
        conn.rollback()
        print(f"Error al eliminar sesión: {e}")
        messages.error(request, "No se pudo cancelar la sesión.")
    finally:
        conn.close()
        
    return redirect('index')

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