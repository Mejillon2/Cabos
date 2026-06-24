import re
from django.shortcuts import render, redirect
from .db_utils import get_connection
from datetime import datetime
from django.db import connection
from django.contrib import messages

REGEX_MIN_3_LETRAS = r"^[a-zA-ZÁéíóúÁÉÍÓÚñÑ]{3,}(?: [a-zA-ZÁéíóúÁÉÍÓÚñÑ]{3,})*$"
REGEX_TELEFONO = r"^\d{10}$"
REGEX_GMAIL = r"^[a-zA-Z0-9._%+-]+@gmail\.com$"
REGEX_ESPECIALIDAD = r"^[a-zA-ZÁéíóúÁÉÍÓÚñÑ]{4,}(?: [a-zA-ZÁéíóúÁÉÍÓÚñÑ]{4,})*$"
REGEX_RAZA = r"^[a-zA-ZÁéíóúÁÉÍÓÚñÑ]{3,}(?: [a-zA-ZÁéíóúÁÉÍÓÚñÑ]{3,})*$"

def index(request):
    if 'usuario_id' not in request.session: 
        return redirect('login_view')
    rol = request.session.get('rol', '').upper().strip()
    usuario_id = request.session.get('usuario_id')
    nombre_usuario = request.session.get('usuario_nombre', 'Usuario')
    conn = get_connection()
    cur = conn.cursor()
    try:
        if rol in ['ADMINISTRADOR', 'ADMIN']:
            cur.execute("SELECT COUNT(*) FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'TERAPEUTA'")
            total_terapeutas = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'PACIENTE'")
            pacientes_totales = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM CABALLOS")
            caballos_totales = cur.fetchone()[0]
            conn.close()
            return render(request, 'gestion/index_admin.html', {
                'admin_nombre': nombre_usuario,
                'total_terapeutas': total_terapeutas,
                'total_pacientes': pacientes_totales,
                'total_caballos': caballos_totales
            })
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
        elif rol == 'PADRE':
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
        regex_usuario = r'^(AD|TE|PA)_\d{2}#$'
        regex_password = r'^\d{2}_#(AD|TE|PA)#$'

        if not re.match(regex_usuario, usuario_ingresado):
            error = "El formato del usuario es inválido (Ej: AD_01#)."
        elif not re.match(regex_password, contrasena_ingresada):
            error = "El formato de la contraseña es inválido (Ej: 01_#AD#)."
        else:
            prefijo_rol = usuario_ingresado.split('_')[0]
            conn = get_connection()
            cur = conn.cursor()
            if prefijo_rol == 'AD':
                query = 'SELECT ID_PERSONA, PASSWORD, NOMBRE, ROL, ES_ADMIN FROM PERSONAS WHERE USUARIO = ? AND ES_ADMIN = 1'
                cur.execute(query, (usuario_ingresado,))
            else:
                mapa_roles = {'TE': 'Terapeuta', 'PA': 'Padre'}
                rol_esperado = mapa_roles.get(prefijo_rol)
                
                query = 'SELECT ID_PERSONA, PASSWORD, NOMBRE, ROL, ES_ADMIN FROM PERSONAS WHERE USUARIO = ? AND UPPER(TRIM(ROL)) = UPPER(?)'
                cur.execute(query, (usuario_ingresado, rol_esperado))
            usuario = cur.fetchone()
            conn.close()
            if usuario:
                db_id, db_pass, db_nombre, db_rol, db_es_admin = usuario
                db_pass_clean = str(db_pass).strip() if db_pass is not None else ""
                if db_es_admin == 1:
                    rol_sesion = 'ADMINISTRADOR'
                else:
                    rol_sesion = str(db_rol).strip().upper()
                if db_pass_clean == contrasena_ingresada:
                    request.session['usuario_id'] = db_id
                    request.session['usuario_nombre'] = db_nombre
                    request.session['rol'] = rol_sesion
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
    
    # === 1. PROCESAR EL REGISTRO CUANDO SE ENVÍA EL FORMULARIO (POST) ===
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '').strip()
        id_padre = request.POST.get('padre')  # Captura el ID seleccionado del select
        fecha_nac = request.POST.get('fecha_nac')
        diagnostico = request.POST.get('diagnostico', '').strip()
        
        hubo_error = False
        
        if not re.match(REGEX_MIN_3_LETRAS, nombre):
            messages.error(request, "Error en Nombre: Solo letras, sin espacios extremos y mínimo 3 letras por palabra.")
            hubo_error = True
        elif not id_padre:
            messages.error(request, "Error: Debe seleccionar un Padre/Tutor Responsable.")
            hubo_error = True
        elif not re.match(REGEX_MIN_3_LETRAS, diagnostico):
            messages.error(request, "Error en Diagnóstico: Solo letras, sin espacios extremos y mínimo 3 letras por palabra.")
            hubo_error = True
            
        if not hubo_error:
            try:
                # Insertar primero en PERSONAS generales
                cur.execute("""
                    INSERT INTO PERSONAS (NOMBRE, ROL) 
                    VALUES (?, 'Paciente')
                """, (nombre,))
                
                # Obtener el ID generado para el nuevo paciente
                cur.execute("SELECT MAX(ID_PERSONA) FROM PERSONAS")
                nuevo_id_paciente = cur.fetchone()[0]
                
                # Insertar en PACIENTES_INFO agregando el ID_PADRE (tutor)
                cur.execute("""
                    INSERT INTO PACIENTES_INFO (ID_PACIENTE, ID_PADRE, FECHA_NAC, DIAGNOSTICO) 
                    VALUES (?, ?, ?, ?)
                """, (nuevo_id_paciente, id_padre, fecha_nac, diagnostico))
                
                conn.commit()
                messages.success(request, f"Paciente '{nombre}' registrado con éxito.")
                conn.close()
                return redirect('lista_pacientes')
            except Exception as e:
                conn.rollback()
                print(f"Error al insertar paciente: {e}")
                messages.error(request, f"Error en la base de datos: {str(e)}")

    # === 2. LEER DATOS PARA RENDERIZAR LA VISTA (GET o tras un error en POST) ===
    # Consulta A: Lista de Pacientes para la Tabla de la derecha
    query_get_pacientes = """
        SELECT p.ID_PERSONA, p.NOMBRE, p.TELEFONO, p.EMAIL, t.FECHA_NAC, t.DIAGNOSTICO 
        FROM PERSONAS p
        INNER JOIN PACIENTES_INFO t ON p.ID_PERSONA = t.ID_PACIENTE
        WHERE p.ROL = 'Paciente'
        ORDER BY p.ID_PERSONA DESC
    """
    cur.execute(query_get_pacientes)
    pacientes_raw = cur.fetchall()
    pacientes = []
    for fila in pacientes_raw:
        registro = []
        for col in fila:
            if col is None:
                registro.append("")
            elif hasattr(col, 'read'):
                registro.append(str(col.read()).strip())
            else:
                registro.append(str(col).strip())
        pacientes.append(registro)
        
    # Consulta B: Lista de Padres/Tutores para llenar el SELECT del Formulario
    query_get_padres = """
        SELECT ID_PERSONA, NOMBRE 
        FROM PERSONAS 
        WHERE UPPER(TRIM(ROL)) = 'PADRE'
        ORDER BY NOMBRE ASC
    """
    cur.execute(query_get_padres)
    padres = [(row[0], str(row[1]).strip()) for row in cur.fetchall()]
    
    conn.close()
    
    # Enviamos tanto la lista de pacientes como la lista de padres al HTML
    return render(request, 'gestion/pacientes.html', {
        'pacientes': pacientes,
        'padres': padres
    })

def editar_paciente(request, id_persona):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')  
    if request.method == 'GET':
        conn = get_connection()
        cur = conn.cursor()
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
            
        datos_limpios = []
        for col in row:
            if col is None:
                datos_limpios.append("")
            elif hasattr(col, 'read'):
                datos_limpios.append(str(col.read()).strip())
            else:
                datos_limpios.append(str(col).strip())
                
        paciente_data = {
            'nombre': datos_limpios[0],
            'telefono': datos_limpios[1],
            'email': datos_limpios[2],
            'fecha_nac': datos_limpios[3],
            'diagnostico': datos_limpios[4]
        }
        
        return render(request, 'gestion/editar_paciente.html', {
            'id_persona': id_persona,
            'paciente_data': paciente_data
        })  
    elif request.method == 'POST':
        nombre = request.POST.get('nombre', '')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '')
        fecha_nac = request.POST.get('fecha_nac')
        diagnostico = request.POST.get('diagnostico', '')

        if not re.match(REGEX_MIN_3_LETRAS, nombre):
            messages.error(request, "Error en Nombre: Solo letras, sin espacios extremos y mínimo 3 letras por palabra.")
            return redirect('editar_paciente', id_persona=id_persona)
            
        if not re.match(REGEX_MIN_3_LETRAS, diagnostico):
            messages.error(request, "Error en Diagnóstico: Solo letras, sin espacios extremos y mínimo 3 letras por palabra.")
            return redirect('editar_paciente', id_persona=id_persona)

        conn = get_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                UPDATE PERSONAS 
                SET NOMBRE = ?, TELEFONO = ?, EMAIL = ? 
                WHERE ID_PERSONA = ? AND ROL = 'Paciente'
            """, (nombre, telefono, correo, id_persona))
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
        cur.execute("DELETE FROM PACIENTES_INFO WHERE ID_PACIENTE = ?", (id_persona,))
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
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')  
    
    conn = get_connection()
    cur = conn.cursor()
    
    valores_previos = None
    hubo_error = False

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '')
        especialidad = request.POST.get('especialidad', '')
        
        valores_previos = {
            'nombre': nombre,
            'telefono': telefono,
            'correo': correo,
            'especialidad': especialidad
        }

        if not re.match(REGEX_MIN_3_LETRAS, nombre):
            messages.error(request, "Error en Nombre: Solo letras, un espacio intermedio, mínimo 3 letras por palabra y sin espacios extremos.")
            hubo_error = True
            
        elif telefono and not re.match(REGEX_TELEFONO, telefono):
            messages.error(request, "Error en Teléfono: El número telefónico debe constar de exactamente 10 dígitos.")
            hubo_error = True
            
        elif correo and not re.match(REGEX_GMAIL, correo):
            messages.error(request, "Error en Correo: Debe ser una dirección terminada en @gmail.com sin espacios.")
            hubo_error = True
            
        elif not re.match(REGEX_ESPECIALIDAD, especialidad):
            messages.error(request, "Error en Especialidad/Notas: Solo letras, sin espacios en los extremos y mínimo 4 letras por palabra.")
            hubo_error = True

        if not hubo_error:
            try:
                # 1. Insertamos primero en la tabla PERSONAS (sin ESPECIALIDAD)
                cur.execute("""
                    INSERT INTO PERSONAS (NOMBRE, TELEFONO, EMAIL, ROL) 
                    VALUES (?, ?, ?, 'Terapeuta')
                """, (nombre, telefono if telefono else None, correo if correo else None))
                
                # 2. Obtenemos el ID de la persona que se acaba de crear
                # Dependiendo de tu BD, si usas Firebird/Interbase (por el formato del error parece ser Firebird o similar con pyodbc)
                # puedes usar cur.execute("SELECT @@IDENTITY") o el método de tu conector. 
                # Si es Firebird habitual, puedes hacer:
                cur.execute("SELECT MAX(ID_PERSONA) FROM PERSONAS")
                nuevo_id = cur.fetchone()[0]
                
                # 3. Insertamos la especialidad en TERAPEUTAS_INFO ligada al nuevo ID
                cur.execute("""
                    INSERT INTO TERAPEUTAS_INFO (ID_TERAPEUTA, ESPECIALIDAD)
                    VALUES (?, ?)
                """, (nuevo_id, especialidad))
                
                conn.commit()
                messages.success(request, f"Terapeuta '{nombre}' registrado con éxito.")
                conn.close()
                return redirect('lista_terapeutas')
                
            except Exception as e:
                conn.rollback() # Importante hacer rollback si el segundo insert falla
                print(f"Error al insertar terapeuta: {e}")
                messages.error(request, f"Error al guardar: {str(e)}")
                hubo_error = True

    # Carga de la lista de la tabla tanto para GET como para errores en POST
    query_get = """
        SELECT p.ID_PERSONA, p.NOMBRE, p.TELEFONO, p.EMAIL, t.ESPECIALIDAD 
        FROM PERSONAS p
        INNER JOIN TERAPEUTAS_INFO t ON p.ID_PERSONA = t.ID_TERAPEUTA
        WHERE p.ROL = 'Terapeuta'
        ORDER BY p.ID_PERSONA DESC
    """
    cur.execute(query_get)
    terapeutas_raw = cur.fetchall()
    terapeutas = []
    for fila in terapeutas_raw:
        terapeutas.append([str(col).strip() if col is not None else "" for col in fila])
    conn.close()
    
    return render(request, 'gestion/terapeutas.html', {
        'terapeutas': terapeutas,
        'valores': valores_previos
    })

def editar_terapeuta(request, id_persona):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
    conn = get_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        nombre = request.POST.get('nombre', '')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '')
        especialidad = request.POST.get('especialidad', '')
        
        if not re.match(REGEX_MIN_3_LETRAS, nombre):
            messages.error(request, "Error en Nombre: Solo letras, un espacio intermedio, mínimo 3 letras por palabra y sin espacios extremos.")
            conn.close()
            return redirect('editar_terapeuta', id_persona=id_persona)
            
        if telefono and not re.match(REGEX_TELEFONO, telefono):
            messages.error(request, "Error en Teléfono: El número telefónico debe constar de exactamente 10 dígitos.")
            conn.close()
            return redirect('editar_terapeuta', id_persona=id_persona)
            
        if correo and not re.match(REGEX_GMAIL, correo):
            messages.error(request, "Error en Correo: Debe ser una dirección terminada en @gmail.com sin espacios.")
            conn.close()
            return redirect('editar_terapeuta', id_persona=id_persona)
            
        if not re.match(REGEX_ESPECIALIDAD, especialidad):
            messages.error(request, "Error en Especialidad/Notas: Solo letras, sin espacios en los extremos y mínimo 4 letras por palabra.")
            conn.close()
            return redirect('editar_terapeuta', id_persona=id_persona)
        try:
            cur.execute("""
                UPDATE PERSONAS 
                SET NOMBRE = ?, TELEFONO = ?, EMAIL = ? 
                WHERE ID_PERSONA = ? AND ROL = 'Terapeuta'
            """, (nombre, telefono if telefono else None, correo if correo else None, id_persona))
            
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
            conn.rollback()
            print(f"Error al actualizar terapeuta: {e}")
            messages.error(request, f"Error al actualizar el registro: {str(e)}")
            conn.close()

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
    terapeuta = [str(col).strip() if col is not None else "" for col in fila]
    return render(request, 'gestion/editar_terapeuta.html', {'terapeuta': terapeutas})

def eliminar_terapeuta(request, id_persona):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')  
    conn = get_connection()
    cur = conn.cursor()
    try:
        # 1. Borramos primero el detalle en TERAPEUTAS_INFO para liberar la llave foránea
        cur.execute("DELETE FROM TERAPEUTAS_INFO WHERE ID_TERAPEUTA = ?", (id_persona,))
        
        # 2. Ahora sí podemos borrar de forma segura el registro en PERSONAS
        cur.execute("DELETE FROM PERSONAS WHERE ID_PERSONA = ? AND UPPER(TRIM(ROL)) = 'TERAPEUTA'", (id_persona,))
        
        conn.commit()
        messages.success(request, "Terapeuta eliminado correctamente.")
    except Exception as e:
        conn.rollback() # Hacemos rollback si algo falla en el proceso
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
    
    valores_previos = None
    hubo_error = False

    if request.method == 'POST':
        nombre = request.POST.get('nombre_c', '')
        raza = request.POST.get('raza', '')
        edad = request.POST.get('edad', '')
        disponibilidad = request.POST.get('estado_disponibilidad')
        
        valores_previos = {
            'nombre_c': nombre,
            'raza': raza,
            'edad': edad,
            'estado_disponibilidad': disponibilidad
        }

        if not re.match(REGEX_MIN_3_LETRAS, nombre):
            messages.error(request, "Error en Nombre del Caballo: Solo letras, mínimo 3 letras por palabra, sin espacios extremos.")
            hubo_error = True
            
        elif not re.match(REGEX_RAZA, raza):
            messages.error(request, "Error en Raza: Solo letras, mínimo 3 letras por palabra y sin espacios extremos.")
            hubo_error = True
            
        try:
            edad_val = int(edad) if edad else 0
            if not (5 <= edad_val <= 45):
                raise ValueError
        except ValueError:
            messages.error(request, "Error en Edad: La edad del caballo debe estar forzosamente entre 5 y 45 años.")
            hubo_error = True

        if not hubo_error:
            try:
                cur.execute("""
                    INSERT INTO CABALLOS (NOMBRE_C, RAZA, EDAD, ESTADO_DISPONIBILIDAD) 
                    VALUES (?, ?, ?, ?)
                """, (nombre, raza, edad_val, disponibilidad))
                conn.commit()
                conn.close()
                return redirect('lista_caballos')
            except Exception as e:
                print(f"Error al insertar caballo: {e}")
                messages.error(request, f"Error en base de datos: {str(e)}")
                hubo_error = True

    cur.execute("SELECT ID_CABALLO, NOMBRE_C, RAZA, EDAD, ESTADO_DISPONIBILIDAD FROM CABALLOS ORDER BY ID_CABALLO DESC")
    caballos_raw = cur.fetchall()
    caballos = []
    for fila in caballos_raw:
        caballos.append([str(col).strip() if col is not None else "" for col in fila])
    conn.close()
    
    return render(request, 'gestion/caballos.html', {
        'caballos': caballos,
        'valores': valores_previos
    })

def editar_caballo(request, id_caballo):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
    conn = get_connection()
    cur = conn.cursor()
    if request.method == 'POST':
        nombre = request.POST.get('nombre_c', '')
        raza = request.POST.get('raza', '')
        edad = request.POST.get('edad', '')
        disponibilidad = request.POST.get('estado_disponibilidad')
        if not re.match(REGEX_MIN_3_LETRAS, nombre):
            messages.error(request, "Error en Nombre del Caballo: Solo letras, mínimo 3 letras por palabra, sin espacios extremos.")
            conn.close()
            return redirect('editar_caballo', id_caballo=id_caballo)
            
        if not re.match(REGEX_RAZA, raza):
            messages.error(request, "Error en Raza: Solo letras, mínimo 3 letras por palabra y sin espacios extremos.")
            conn.close()
            return redirect('editar_caballo', id_caballo=id_caballo)
            
        try:
            edad_val = int(edad) if edad else 0
            if not (5 <= edad_val <= 45):
                raise ValueError
        except ValueError:
            messages.error(request, "Error en Edad: La edad del caballo debe estar forzosamente entre 5 y 45 años.")
            conn.close()
            return redirect('editar_caballo', id_caballo=id_caballo)

        cur.execute("""
            UPDATE CABALLOS 
            SET NOMBRE_C = ?, RAZA = ?, EDAD = ?, ESTADO_DISPONIBILIDAD = ? 
            WHERE ID_CABALLO = ?
        """, (nombre, raza, edad_val, disponibilidad, id_caballo))
        conn.commit()
        conn.close()
        return redirect('lista_caballos')
    cur.execute("SELECT ID_CABALLO, NOMBRE_C, RAZA, EDAD, ESTADO_DISPONIBILIDAD FROM CABALLOS WHERE ID_CABALLO = ?", (id_caballo,))
    fila = cur.fetchone()
    conn.close()
    caballo = [str(col).strip() if col is not None else "" for col in fila] if fila else None
    return render(request, 'gestion/editar_caballo.html', {'caballo': caballo})

def eliminar_caballo(request, id_caballo):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
    conn = get_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM CABALLOS WHERE ID_CABALLO = ?", (id_caballo,))
        conn.commit()
    except Exception as e:
        print(f"Error al eliminar: {e}")
    finally:
        conn.close()
        
    return redirect('lista_caballos')

def lista_padres(request):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
    
    conn = get_connection()
    cur = conn.cursor()
    
    valores_previos = None
    hubo_error = False

    if request.method == 'POST':
        nombre = request.POST.get('nombre', '')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '')
        
        valores_previos = {
            'nombre': nombre,
            'telefono': telefono,
            'correo': correo
        }

        if not re.match(REGEX_MIN_3_LETRAS, nombre):
            messages.error(request, "Error en Nombre: Solo letras, un espacio intermedio, mínimo 3 letras por palabra y sin espacios extremos.")
            hubo_error = True
            
        elif telefono and not re.match(REGEX_TELEFONO, telefono):
            messages.error(request, "Error en Teléfono: El número telefónico debe constar de exactamente 10 dígitos.")
            hubo_error = True
            
        elif correo and not re.match(REGEX_GMAIL, correo):
            messages.error(request, "Error en Correo: Debe ser una dirección terminada en @gmail.com sin espacios.")
            hubo_error = True

        if not hubo_error:
            try:
                cur.execute("""
                    INSERT INTO PERSONAS (NOMBRE, TELEFONO, EMAIL, ROL) 
                    VALUES (?, ?, ?, 'Padre')
                """, (nombre, telefono if telefono else None, correo if correo else None))
                conn.commit()
                messages.success(request, f"Tutor '{nombre}' registrado correctamente.")
                conn.close()
                return redirect('lista_padres')
            except Exception as e:
                conn.rollback()
                messages.error(request, f"Error al registrar: {str(e)}")
                hubo_error = True

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
    
    return render(request, 'gestion/padres.html', {
        'padres': padres,
        'valores': valores_previos
    })

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
        nombre = request.POST.get('nombre', '')
        telefono = request.POST.get('telefono', '')
        correo = request.POST.get('correo', '')
        if not re.match(REGEX_MIN_3_LETRAS, nombre):
            messages.error(request, "Error en Nombre: Solo letras, un espacio intermedio, mínimo 3 letras por palabra y sin espacios extremos.")
            conn.close()
            return redirect('editar_padres', id_persona=id_persona)
            
        if telefono and not re.match(REGEX_TELEFONO, telefono):
            messages.error(request, "Error en Teléfono: El número telefónico debe constar de exactamente 10 dígitos.")
            conn.close()
            return redirect('editar_padres', id_persona=id_persona)
            
        if correo and not re.match(REGEX_GMAIL, correo):
            messages.error(request, "Error en Correo: Debe ser una dirección terminada en @gmail.com sin espacios.")
            conn.close()
            return redirect('editar_padres', id_persona=id_persona)
        
        try:
            cur.execute("""
                UPDATE PERSONAS 
                SET NOMBRE = ?, TELEFONO = ?, EMAIL = ? 
                WHERE ID_PERSONA = ? AND ROL = 'Padre'
            """, (nombre, telefono if telefono else None, correo if correo else None, id_persona))
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
            return redirect('agendar')
        except Exception as e:
            print(f"Error al insertar sesión o actualizar estados: {e}")
        finally:
            conn.close()
    pacientes = []
    terapeutas = []
    caballos = []
    sesiones = []
    try:
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
    return render(request, 'gestion/agendar.html', {
        'pacientes': pacientes,
        'terapeutas': terapeutas,
        'caballos': caballos,
        'sesiones': sesiones,
        'admin_nombre': request.session.get('usuario_nombre')
    })

def editar_cita(request, id_sesion):
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view')
    conn = get_connection()
    cur = conn.cursor()
    if request.method == 'GET':
        try:
            cur.execute("""
                SELECT ID_PACIENTE, ID_TERAPEUTA, ID_CABALLO, FECHA_HORA 
                FROM SESIONES 
                WHERE ID_SESION = ?
            """, (id_sesion,))
            row = cur.fetchone()
            
            if not row:
                messages.error(request, "La sesión no existe.")
                return redirect('index')
            
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
            cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'PACIENTE' ORDER BY NOMBRE")
            pacientes = [(p[0], str(p[1]).strip()) for p in cur.fetchall()]

            cur.execute("SELECT ID_PERSONA, NOMBRE FROM PERSONAS WHERE UPPER(TRIM(ROL)) = 'TERAPEUTA' ORDER BY NOMBRE")
            terapeutas = [(t[0], str(t[1]).strip()) for t in cur.fetchall()]
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
        fecha_hora_str = f"{fecha} {hora}:00"

        try:
            query_update = """
                UPDATE SESIONES 
                SET ID_PACIENTE = ?, ID_TERAPEUTA = ?, ID_CABALLO = ?, FECHA_HORA = ? 
                WHERE ID_SESION = ?
            """
            cur.execute(query_update, (id_paciente, id_terapeuta, id_caballo_nuevo, fecha_hora_str, id_sesion))
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
        cur.execute("SELECT ID_CABALLO FROM SESIONES WHERE ID_SESION = ?", (id_sesion,))
        row = cur.fetchone()
        if row and row[0]:
            cur.execute("""
                UPDATE CABALLOS 
                SET ESTADO_DISPONIBILIDAD = 'DISPONIBLE' 
                WHERE ID_CABALLO = ?
            """, (row[0],))
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
    if request.session.get('rol') not in ['ADMINISTRADOR', 'ADMIN']: 
        return redirect('login_view') 
    fecha_inicio = request.GET.get('fecha_inicio', '')
    fecha_fin = request.GET.get('fecha_fin', '')
    conn = get_connection()
    cur = conn.cursor()
    query = """
        SELECT p_pac.NOMBRE AS PACIENTE, p_ter.NOMBRE AS TERAPEUTA, c.NOMBRE_C AS CABALLO, s.FECHA_HORA, s.ESTADO_SESION
        FROM SESIONES s
        JOIN PERSONAS p_pac ON s.ID_PACIENTE = p_pac.ID_PERSONA
        JOIN PERSONAS p_ter ON s.ID_TERAPEUTA = p_ter.ID_PERSONA
        JOIN CABALLOS c ON s.ID_CABALLO = c.ID_CABALLO
    """
    parametros = []
    if fecha_inicio and fecha_fin:
        query += " WHERE s.FECHA_HORA BETWEEN ? AND ?"
        parametros.extend([f"{fecha_inicio} 00:00:00", f"{fecha_fin} 23:59:59"])
    query += " ORDER BY s.FECHA_HORA DESC"
    cur.execute(query, parametros)
    sesiones_data = cur.fetchall()
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