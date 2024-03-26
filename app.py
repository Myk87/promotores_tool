from flask import Flask, render_template, redirect, request, session, url_for, jsonify, flash
from flask_mysqldb import MySQL
import pandas as pd
from admin_utils import admin_required
import numpy as np
import string
import random
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from markupsafe import Markup
from datetime import datetime

app = Flask(__name__, template_folder="template")
app.secret_key = "8462a954b9f6d4ce14b42ccd24a90d500d917466021cab89"

# Configuración de la base de datos MySQL
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'login'

# Inicialización de la extensión MySQL
mysql = MySQL(app)

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/admin")
@admin_required
def admin():
    return render_template("admin/admin.html")

@app.route("/acceso-login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if "txtCorreo" in request.form and "txtPassword" in request.form:
            correo = request.form["txtCorreo"]
            password = request.form["txtPassword"]

            cur = mysql.connection.cursor()

            cur.execute("SELECT * FROM usuarios WHERE correo = %s AND password = %s", (correo, password,))
            account = cur.fetchone()

            if account:
                id_centro = account[5]
                id_fabricante = account[7]

                cur.execute("SELECT nombre_centro, codigo_cliente FROM centros WHERE id_centro = %s", (id_centro,))
                nombre_centro_result = cur.fetchone()

                cur.execute("SELECT nombre_fabricante FROM fabricantes WHERE id_fabricante = %s", (id_fabricante,))
                nombre_fabricante_result = cur.fetchone()

                cur.close()

                if nombre_centro_result:
                    nombre_centro = nombre_centro_result[0]
                    codigo_cliente = nombre_centro_result[1]

                if nombre_fabricante_result:
                    nombre_fabricante = nombre_fabricante_result[0]

                session["logueado"] = True
                session["id"] = account[0]
                session["id_rol"] = account[6]
                session["nombre"] = account[3]
                session["id_centro"] = id_centro
                session["nombre_centro"] = nombre_centro
                session["codigo_cliente"] = codigo_cliente
                session["id_fabricante"] = id_fabricante
                session["nombre_fabricante"] = nombre_fabricante

                # Obtener el nombre del mes actual en español
                now = datetime.now()
                mes_actual = now.strftime('%B').lower()  # Convertir a minúsculas
                mes_actual_espanol = meses_espanol.get(mes_actual, mes_actual.capitalize())  # Obtener el nombre en español o mantenerlo en inglés

                # Verificar si el usuario ya tiene un registro en la tabla mes_consulta_dash
                cur = mysql.connection.cursor()
                cur.execute("SELECT * FROM mes_consulta_dash WHERE id_usuario = %s", (account[0],))
                existing_record = cur.fetchone()

                if existing_record:
                    # Si ya existe, actualizar el mes
                    cur.execute("UPDATE mes_consulta_dash SET mes_form_dash = %s WHERE id_usuario = %s", (mes_actual_espanol, account[0]))
                else:
                    # Si no existe, insertar un nuevo registro
                    cur.execute("INSERT INTO mes_consulta_dash (id_usuario, mes_form_dash) VALUES (%s, %s)", (account[0], mes_actual_espanol))

                mysql.connection.commit()
                cur.close()

                if session["id_rol"] == 1:
                    return redirect(url_for("admin"))
                elif session["id_rol"] == 2:
                    return redirect(url_for("inicio"))

            return render_template("login.html", mensaje="Usuario o contraseña incorrectos")

    return render_template("login.html")


# Diccionario temporal para almacenar las contraseñas temporales (solo para propósitos de demostración)
contrasenas_temporales = {}

def generar_contrasena_temporal():
    # Caracteres posibles para la contraseña
    caracteres = string.ascii_letters + string.digits

    # Generar una contraseña de 8 caracteres seleccionando aleatoriamente de los caracteres posibles
    contrasena_temporal = ''.join(random.choice(caracteres) for _ in range(8))

    return contrasena_temporal

@app.route('/contrasena-perdida', methods=['GET', 'POST'])
def contrasena_perdida():
    if request.method == 'POST':
        correo = request.form['correo']
        confirmar_correo = request.form['confirmar_correo']

        # Verificar si los correos coinciden
        if correo != confirmar_correo:
            return render_template('contrasena_perdida.html', mensaje='Los correos no coinciden. Por favor, inténtelo de nuevo.')

        # Verificar si el correo está en la base de datos
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM usuarios WHERE correo = %s", (correo,))
        account = cur.fetchone()

        if not account:
            cur.close()
            return render_template('contrasena_perdida.html', mensaje='El correo electrónico no está registrado en nuestra base de datos. Por favor, póngase en contacto con el administrador.')

        # Generar una contraseña temporal segura
        contrasena_temporal = generar_contrasena_temporal()

        # Verificar si ya existe una contraseña temporal para este correo
        cur.execute("SELECT * FROM psw_temp WHERE correo = %s", (correo,))
        existing_entry = cur.fetchone()

        if existing_entry:
            # Si existe una entrada anterior para este correo, actualizamos la contraseña temporal
            cur.execute("UPDATE psw_temp SET contrasena_temp = %s WHERE correo = %s", (contrasena_temporal, correo))
        else:
            # Si no existe una entrada anterior, insertamos una nueva entrada
            cur.execute("INSERT INTO psw_temp (correo, contrasena_temp) VALUES (%s, %s)", (correo, contrasena_temporal))

        mysql.connection.commit()
        cur.close()

        # Enviar correo electrónico con la contraseña temporal
        enviar_correo(correo, contrasena_temporal)

        # Redirigir a la página de cambio de contraseña
        return redirect(url_for('cambio_contrasena'))
    else:
        return render_template('contrasena_perdida.html')

def enviar_correo(destinatario, contrasena_temporal):
    message = Mail(
        from_email='prmotorolaesprinet@gmail.com',
        to_emails=destinatario,
        subject='Contraseña temporal',
        html_content=f'Hola,<br><br>Tu nueva contraseña temporal es: <strong>{contrasena_temporal}</strong><br><br>Por favor, cambia tu contraseña después de iniciar sesión.'
    )

    try:
        sg = SendGridAPIClient('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')
        response = sg.send(message)
        print(response.status_code)
        print(response.body)
        print(response.headers)
        print('Correo electrónico enviado con éxito a', destinatario)
    except Exception as e:
        print(e.message)


@app.route('/cambio-contrasena', methods=['GET', 'POST'])
def cambio_contrasena():
    if request.method == 'POST':
        contrasena_provisoria = request.form['contrasena_provisoria']
        nueva_contrasena = request.form['nueva_contrasena']
        repite_contrasena = request.form['repite_contrasena']

        # Verificar si la contraseña provisoria es válida
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM psw_temp WHERE contrasena_temp = %s", (contrasena_provisoria,))
        provisory_password_entry = cur.fetchone()

        if not provisory_password_entry:
            cur.close()
            mensaje = 'La contraseña provisoria no es válida'
            return render_template('cambio_contrasena.html', mensaje=mensaje)

        # Verificar si las nuevas contraseñas coinciden
        if nueva_contrasena != repite_contrasena:
            cur.close()
            mensaje = 'Las nuevas contraseñas no coinciden'
            return render_template('cambio_contrasena.html', mensaje=mensaje)

        # Actualizar la contraseña en la tabla de usuarios
        correo = provisory_password_entry[0]  # El correo asociado a la contraseña provisoria
        cur.execute("UPDATE usuarios SET password = %s WHERE correo = %s", (nueva_contrasena, correo))
        mysql.connection.commit()
        cur.close()

        # Eliminar la entrada de contraseña provisoria de la tabla psw_temp
        cur = mysql.connection.cursor()
        cur.execute("DELETE FROM psw_temp WHERE correo = %s", (correo,))
        mysql.connection.commit()
        cur.close()

        mensaje2 = 'Contraseña cambiada exitosamente.'
        mensaje2 = Markup(mensaje2)
        return render_template('cambio_contrasena.html', mensaje2=mensaje2)

@app.route("/inicio")
def inicio():
    # Verificar si el usuario está autenticado
    if 'logueado' in session:
        return render_template('index.html', nombre=session['nombre'],)

    else:
        # Redirigir al usuario al inicio de sesión si no está autenticado
        print("Usuario no autenticado. Redirigiendo al login...")  # Agregar mensaje de depuración
        return redirect(url_for('login'))

@app.route("/logout")
def logout():
    # Remover todas las variables de sesión
    session.clear()
    # Renderizar la plantilla logout.html
    return render_template("logout.html")

@app.route("/listar", methods=["GET", "POST"])
@admin_required
def listar():
    cur = mysql.connection.cursor()

    # Consulta para obtener los datos de los usuarios con el nombre del fabricante
    cur.execute("""
        SELECT
            usuarios.id, usuarios.correo, usuarios.nombre, usuarios.apellido,
            centros.id_centro, centros.nombre_centro, cadenas.nombre_cadena,
            fabricantes.id_fabricante, fabricantes.nombre_fabricante
        FROM
            usuarios
        INNER JOIN
            centros ON usuarios.id_centro = centros.id_centro
        INNER JOIN
            cadenas ON centros.id_cadena = cadenas.id_cadenas
        INNER JOIN
            fabricantes ON usuarios.id_fabricante = fabricantes.id_fabricante
    """)

    usuarios = cur.fetchall()

    # Consulta para obtener los puntos de venta con el nombre de la cadena
    cur.execute("""
        SELECT centros.id_centro, centros.nombre_centro, cadenas.nombre_cadena
        FROM centros
        INNER JOIN cadenas ON centros.id_cadena = cadenas.id_cadenas
    """)
    puntos_ventas = cur.fetchall()

    cur.execute("SELECT id_fabricante, nombre_fabricante FROM fabricantes")
    fabricantes = cur.fetchall()

    cur.close()

    return render_template("admin/listar_usuarios.html", usuarios=usuarios, puntos_ventas=puntos_ventas, fabricantes=fabricantes)


@app.route("/editar-usuario", methods=["POST"])
@admin_required
def editar_usuario():
    if request.method == "POST":
        id_usuario = request.form.get("id_usuario")
        nuevo_correo = request.form.get("nuevo_correo")
        nuevo_nombre = request.form.get("nuevo_nombre")
        nuevo_apellido = request.form.get("nuevo_apellido")
        nuevo_centro_id = request.form.get("nuevo_centro_id")
        nuevo_fabricante_id = request.form.get("nuevo_fabricante_id")  # Nuevo campo para el ID del fabricante

        # Crear un cursor para realizar consultas SQL
        cur = mysql.connection.cursor()

        # Verificar si nuevo_centro_id existe en la tabla centros
        cur.execute("SELECT COUNT(*) FROM centros WHERE id_centro = %s", (nuevo_centro_id,))
        centro_existente = cur.fetchone()[0]

        # Verificar si nuevo_fabricante_id existe en la tabla fabricantes
        cur.execute("SELECT COUNT(*) FROM fabricantes WHERE id_fabricante = %s", (nuevo_fabricante_id,))
        fabricante_existente = cur.fetchone()[0]  # Cambiado a fabricante_existente

        if centro_existente and fabricante_existente:  # Asegúrate de verificar ambos existentes
            # Ambos centro y fabricante existen, se puede proceder con la actualización
            cur.execute("UPDATE usuarios SET correo = %s, nombre = %s, apellido = %s, id_centro = %s, id_fabricante = %s WHERE id = %s", (nuevo_correo, nuevo_nombre, nuevo_apellido, nuevo_centro_id, nuevo_fabricante_id, id_usuario))
            mysql.connection.commit()
            cur.close()
            return "Actualización exitosa"
        else:
            # Al menos uno de los IDs no existe, mostrar un mensaje de error o redirigir
            return "Error: El centro o el fabricante seleccionado no existe"

@app.route('/ventas')
@admin_required
def index():
    ventasdb = obtener_ventas_db()
    return render_template('admin/cargar_ventas.html', ventasdb=ventasdb)

@app.route('/obtener-ventas')
def obtener_ventas_db():
    cur = mysql.connection.cursor()

    # Ejecuta una consulta para obtener los datos de ventas
    cur.execute("SELECT codigo_cadena, nombre_fabricante, tienda_motorola, fecha, semana, mes, dia, ano, modelo_color, sellout, valor_venta, modelo FROM datos_producto")
    ventas = cur.fetchall()
    cur.close()

    # Devuelve los datos de ventas
    return ventas


@app.route('/cargar-csv', methods=['POST'])
@admin_required
def cargar_csv():
    try:
        # Obtener el archivo CSV enviado desde el formulario
        archivo_csv = request.files['archivo_csv']

        # Leer el archivo CSV usando pandas y especificar el formato de fecha
        df = pd.read_csv(archivo_csv, sep=';', parse_dates=['Fecha'], dayfirst=True)

        # Convertir la columna 'Fecha' al formato YYYY-MM-DD
        df['Fecha'] = df['Fecha'].dt.strftime('%Y-%m-%d')

        # Verificar si existen datos para las fechas en el archivo CSV
        fechas_existen = verificar_existencia_fechas(df['Fecha'])

        if fechas_existen:
            # Si existen fechas, renderizamos el template con el mensaje de confirmación
            return render_template('cargar_csv.html', fechas_existen=fechas_existen)
        else:
            # Si no existen fechas, procedemos con la carga del archivo CSV
            # Insertar los datos en la base de datos por lotes
            cur = mysql.connection.cursor()
            batch_size = 1000  # Tamaño del lote, ajusta según sea necesario
            total_rows = len(df)
            print(f'Total de filas en el DataFrame: {total_rows}')

            for i in range(0, total_rows, batch_size):
                batch_df = df.iloc[i:i+batch_size]
                batch_rows = len(batch_df)
                print(f'Insertando lote de filas {i+1}-{i+batch_rows}')

                for _, fila in batch_df.iterrows():
                    try:
                        # Eliminar las comas de los valores numéricos
                        fila['Valore di Vendita'] = fila['Valore di Vendita'].replace('.', '')
                        fila['Valore di Vendita'] = fila['Valore di Vendita'].replace(',', '.')
                        fila['Ticket Medio'] = fila['Ticket Medio'].replace(',', '')

                        # Insertar cada fila del lote en la tabla de la base de datos
                        cur.execute("INSERT INTO datos_producto (codigo_cadena, codigo_articulo, codigo_ean, codigo_brand, nombre_fabricante, descripcion_brand, fecha, descripcion_articulo, stock_virtual, cantidad_stock, sellout, valor_venta, gln, codigo_cliente, tienda, tienda_motorola, semana, mes, dia, ano, promotor, gamma, modelo_color, tipologia, zona, ticket_medio, modelo) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                                        (fila['Código cadena'], fila['Código artículo'], fila['Código EAN'], fila['Código brand'], fila['Nombre fabricante'], fila['Descripción brand'], fila['Fecha'], fila['Descripción artículo'], fila['Stock Virtuale'], fila['Qtà Stock'], fila['Sellout'], fila['Valore di Vendita'], fila['GLN'], fila['Código cliente'], fila['Tienda'], fila['Tienda Motorola'], fila['Semana'], fila['Mes'], fila['dia'], fila['Año'], fila['Promotor'], fila['gamA'], fila['Modelo + Color'], fila['tipologia'], fila['Zona'], fila['Ticket Medio'], fila['modelo']))
                    except Exception as e:
                        mysql.connection.rollback()
                        raise e
                    mysql.connection.commit()

            cur.close()

            return 'Datos del archivo CSV cargados correctamente en la base de datos.'
    except Exception as e:
        return f'Error al cargar el archivo CSV: {str(e)}'


def verificar_existencia_fechas(fechas):
    # Realiza una consulta a la base de datos para verificar la existencia de las fechas
    cur = mysql.connection.cursor()
    fechas_existentes = []

    try:
        # Construye la consulta SQL para verificar las fechas existentes
        query = "SELECT DISTINCT fecha FROM datos_producto WHERE fecha IN %s"
        cur.execute(query, (tuple(fechas),))
        fechas_existentes = [fecha[0] for fecha in cur.fetchall()]
    except Exception as e:
        print(f'Error al verificar las fechas existentes: {str(e)}')
    finally:
        cur.close()

    return fechas_existentes


@app.route('/contar-filas')
def contar_filas():
    try:
        # Ejecuta la consulta SQL para contar las filas
        with mysql.connection.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM datos_producto")
            resultado = cur.fetchone()
            if resultado:
                num_filas = resultado[0]
                return f'Número de filas en la tabla datos_producto: {num_filas}'
            else:
                return 'No se encontraron filas en la tabla datos_producto'
    except Exception as e:
        return f'Error al contar las filas en la tabla datos_producto: {str(e)}'

@app.route('/vaciar-tabla', methods=['POST'])
@admin_required
def vaciar_tabla():
    try:
        # Crear el cursor y ejecutar la consulta para vaciar la tabla
        cur = mysql.connection.cursor()
        cur.execute("TRUNCATE TABLE datos_producto")
        mysql.connection.commit()
        cur.close()

        return 'Tabla datos_producto vaciada correctamente.'
    except Exception as e:
        return f'Error al vaciar la tabla datos_producto: {str(e)}'

def ejecutar_consulta(sql_query, params=None):
    # Obtener la conexión a la base de datos a través de la extensión MySQL de Flask
    conexion = mysql.connection
    cursor = conexion.cursor(dictionary=True)
    if params:
        cursor.execute(sql_query, params)
    else:
        cursor.execute(sql_query)
    resultados = cursor.fetchall()
    cursor.close()
    return resultados

@app.route('/ventas-usuario/<int:id_usuario>')
def ventas_usuario(id_usuario):
    try:
        # Consulta SQL para obtener las ventas del usuario
        sql_query = """
            SELECT datos_producto.fecha, datos_producto.descripcion_articulo, datos_producto.valor_venta, datos_producto.nombre_centro, cadenas.nombre_cadena
            FROM datos_producto
            INNER JOIN cadenas ON datos_producto.id_cadena = c.id_cadena
            INNER JOIN usuarios ON datos_producto.id_fabricante = usuarios.id_fabricante
            INNER JOIN cadenas ON datos_producto.tienda_motorola = CONCAT(cadenas.id_cadena, c.nombre_centro)
            WHERE usuario.id_usuario = %s
            """
        resultados = ejecutar_consulta(sql_query, (id_usuario,))
        return render_template('ventas_usuario.html', resultados=resultados)
    except Exception as e:
        return f'Error al obtener las ventas del usuario: {str(e)}'

@app.route("/registro")
def registro():
    try:
        # Realiza una consulta para obtener la lista de puntos de venta
        conexion = mysql.connection
        cursor = conexion.cursor()
        cursor.execute("SELECT id_centro, nombre_centro FROM centros")
        puntos_venta = cursor.fetchall()

        # Realiza una consulta para obtener la lista de fabricantes
        cursor.execute("SELECT id_fabricante, nombre_fabricante FROM fabricantes")
        fabricantes = cursor.fetchall()

        cursor.close()
        return render_template("admin/registro.html", puntos_venta=puntos_venta, fabricantes=fabricantes)
    except mysql.connector.Error as err:
        print(f"Error al obtener datos: {err}")
        return "Error al obtener datos"

@app.route("/crear-registro", methods=["POST"])
def crear_registro():
    if request.method == "POST":
        correo = request.form["txtCorreo"]
        password = request.form["txtPassword"]
        nombre = request.form["nombre"]
        apellido = request.form["apellido"]
        centro_id = request.form["punto_venta"]
        fabricante_id = request.form["fabricante"]

        try:
            # Inserta el nuevo registro en la tabla usuarios
            cursor = mysql.connection.cursor()
            cursor.execute("INSERT INTO usuarios (correo, password, nombre, apellido, id_centro, id_rol, id_fabricante) VALUES (%s, %s, %s, %s, %s, 2, %s)", (correo, password, nombre, apellido, centro_id, fabricante_id))
            mysql.connection.commit()
            cursor.close()
            return render_template("admin/admin.html", mensaje2="Usuario registrado exitosamente")
        except mysql.connect.Error as err:
            print(f"Error al insertar registro: {err}")
            return "Error al crear registro"
        finally:
            cursor.close()

@app.route("/mostrar-fabricantes")
@admin_required
def mostrar_fabricantes():
    try:
        # Realiza una consulta para obtener la lista de fabricantes
        conexion = mysql.connection
        cursor = conexion.cursor()
        cursor.execute("SELECT id_fabricante, nombre_fabricante FROM fabricantes")
        fabricantes = cursor.fetchall()

        cursor.close()
        return render_template("admin/nuevo_fabricante.html", fabricantes=fabricantes)
    except mysql.connect.Error as err:
        print(f"Error al obtener datos: {err}")
        return "Error al obtener datos"

@app.route("/crear-fabricante", methods=["POST"])
@admin_required
def crear_fabricante():
    if request.method == "POST":
        nombre_fabricante = request.form["nombre_fabricante"]

        try:
            # Inserta el nuevo registro en la tabla fabricantes
            cursor = mysql.connection.cursor()
            cursor.execute("INSERT INTO fabricantes (nombre_fabricante) VALUES (%s)", (nombre_fabricante,))
            mysql.connection.commit()
            cursor.close()
            return "Registro creado exitosamente"
        except mysql.connect.Error as err:
            print(f"Error al crear el registro: {err}")
            return "Error al crear el registro"

@app.route("/eliminar-fabricante/<int:id_fabricante>", methods=["POST"])
@admin_required
def eliminar_fabricante(id_fabricante):
    if request.method == "POST":
        try:
            # Eliminar el registro de la tabla fabricantes
            cursor = mysql.connection.cursor()
            cursor.execute("DELETE FROM fabricantes WHERE id_fabricante = %s", (id_fabricante,))
            mysql.connection.commit()
            cursor.close()
            return "Fabricante eliminado exitosamente"
        except mysql.connect.Error as err:
            print(f"Error al eliminar el fabricante: {err}")
            return "Error al eliminar el fabricante"


@app.route('/cargar-csv-target', methods=['POST'])
@admin_required
def cargar_csv_target():
    try:
        # Obtener el archivo CSV enviado desde el formulario
        archivo_csv = request.files['archivo_csv']

        # Leer el archivo CSV usando pandas
        df = pd.read_csv(archivo_csv, sep=';', decimal=',')

        # Procedemos con la carga del archivo CSV
        # Insertar los datos en la base de datos por lotes
        cur = mysql.connection.cursor()
        batch_size = 1000  # Tamaño del lote, ajusta según sea necesario
        total_rows = len(df)
        flash(f'Se han encontrado {total_rows} filas en el archivo CSV')  # Mensaje flash
        print(f'Total de filas en el DataFrame: {total_rows}')

        for i in range(0, total_rows, batch_size):
            batch_df = df.iloc[i:i+batch_size]
            batch_rows = len(batch_df)
            print(f'Insertando lote de filas {i+1}-{i+batch_rows}')

            for _, fila in batch_df.iterrows():
                try:
                    # Verificar si ya existe un registro con la misma combinación de año, mes y codigo_cliente
                    cur.execute("SELECT COUNT(*) FROM target_personales_eci WHERE ano = %s AND mes = %s AND codigo_cliente = %s", (fila['ano'], fila['mes'], fila['codigo_cliente']))
                    existente = cur.fetchone()[0]

                    if existente > 0:
                        # Si existe, sobrescribe el registro
                        cur.execute("UPDATE target_personales_eci SET id_fabricante = %s, importe = %s WHERE ano = %s AND mes = %s AND codigo_cliente = %s", (fila['id_fabricante'], fila['importe'], fila['ano'], fila['mes'], fila['codigo_cliente']))
                    else:
                        # Si no existe, inserta un nuevo registro
                        cur.execute("INSERT INTO target_personales_eci (id_fabricante, codigo_cliente, mes, ano, importe) VALUES (%s, %s, %s, %s, %s)", (fila['id_fabricante'], fila['codigo_cliente'], fila['mes'], fila['ano'], fila['importe']))

                    mysql.connection.commit()
                except Exception as e:
                    mysql.connection.rollback()
                    print(f'Error al insertar la fila: {str(e)}')  # Imprimir el error
                    raise e

        cur.close()

        # Después de cargar los datos, redirigir a una página que muestre los resultados
        return redirect(url_for('mostrar_ventas_target'))
    except Exception as e:
        print(f'Error al cargar el archivo CSV: {str(e)}')  # Imprimir el error
        flash('Error al cargar el archivo CSV', 'error')  # Mensaje flash de error
        return f'Error al cargar el archivo CSV: {str(e)}'

def format_currency(value):
    return f'€{value:.2f}'

app.jinja_env.filters['format_currency'] = format_currency

@app.route('/mostrar-ventas-target')
@admin_required
def mostrar_ventas_target():
    target_personales = obtener_target_personales_db()
    return render_template('admin/cargar_target_personales.html', target_personales=target_personales)

@app.route('/obtener-ventas-target')
def obtener_target_personales_db():
    cur = mysql.connection.cursor()

    # Ejecuta una consulta para obtener los datos de ventas de target_personales_eci
    cur.execute("SELECT f.nombre_fabricante, c.nombre_centro, t.mes, t.ano, t.importe FROM target_personales_eci t INNER JOIN fabricantes f ON t.id_fabricante = f.id_fabricante INNER JOIN centros c ON t.codigo_cliente = c.codigo_cliente")
    target_personales = cur.fetchall()
    cur.close()

    # Devuelve los datos de ventas de target_personales_eci
    return target_personales



@app.route("/ventas-usuario", methods=["GET"])
def mostrar_ventas_usuario():
    if "logueado" in session:
        # Obtener el ID del centro del usuario de la sesión
        id_centro = session.get("id_centro")
        id_fabricante = session.get("id_fabricante")

        # Crear un cursor para realizar consultas SQL
        conexion = mysql.connection
        cur = conexion.cursor()

        # Consultar el código de cliente asociado al ID del centro del usuario
        cur.execute("SELECT codigo_cliente FROM centros WHERE id_centro = %s", (id_centro,))
        codigo_cliente = cur.fetchone()

        cur.execute("SELECT nombre_fabricante FROM fabricantes WHERE id_fabricante = %s", (id_fabricante,))
        nombre_fabricante = cur.fetchone()

        if codigo_cliente:
            codigo_cliente = codigo_cliente[0]  # Obtener el código de cliente de la tupla

            # Consultar las ventas asociadas al código de cliente del usuario
            cur.execute("""
                SELECT codigo_cadena, nombre_fabricante, tienda_motorola, fecha, semana, mes, dia, ano, modelo_color, sellout, valor_venta
                FROM datos_producto
                WHERE codigo_cliente = %s AND sellout !=0
            """, (codigo_cliente,))

            # Obtener los resultados de la consulta
            ventas_usuario = cur.fetchall()

            # Obtener los meses disponibles
            meses = obtener_meses()

            # Cerrar el cursor después de la consulta
            cur.close()

            # Renderizar la plantilla con los resultados de las ventas del usuario y los meses disponibles
            return render_template("ventas_usuario.html", ventas_usuario=ventas_usuario, meses_disponibles=meses)

        elif nombre_fabricante:
            nombre_fabricante = nombre_fabricante[0]
            print("Nombre del fabricante del usuario:", nombre_fabricante)  # Agregar esta línea para depuración

            # Consultar las ventas asociadas al nombre del fabricante del usuario
            cur.execute("""
                SELECT codigo_cadena, nombre_fabricante, tienda_motorola, fecha, semana, mes, dia, ano, modelo_color, sellout, valor_venta
                FROM datos_producto
                WHERE nombre_fabricante = %s AND sellout != 0 AND codigo_cliente IS NULL AND nombre_fabricante = %s
            """, (nombre_fabricante, nombre_fabricante))

            # Obtener los resultados de la consulta
            ventas_usuario = cur.fetchall()

            # Obtener los meses disponibles
            meses = obtener_meses()

            # Cerrar el cursor después de la consulta
            cur.close()

            # Renderizar la plantilla con los resultados de las ventas del usuario y los meses disponibles
            return render_template("ventas_usuario.html", ventas_usuario=ventas_usuario, meses_disponibles=meses)

        else:
            return "Error: No se ha asignado un código de cliente ni un fabricante al usuario."  # Manejo del caso sin código de cliente ni fabricante asignado

    else:
        return redirect(url_for('login'))


@app.route('/filtrar-ventas', methods=['POST'])
def filtrar_ventas():
    if 'logueado' in session:
        if request.method == 'POST':
            codigo_cliente = session['codigo_cliente']
            nombre_fabricante = session["nombre_fabricante"]
            filtro = request.form.get('filtro')  # Obtener el tipo de filtro (mes o semana)

            # Inicializar las variables de filtro
            mes_seleccionado = None
            semana_seleccionada = None
            producto_seleccionado = request.form.get('producto')  # Obtener el producto seleccionado

            # Verificar qué filtro se está aplicando y asignar el valor correspondiente
            if filtro == 'mes':
                mes_seleccionado = request.form['mes']
                cur = mysql.connection.cursor()
                if producto_seleccionado:  # Verifica si se ha seleccionado un producto
                    cur.execute("SELECT codigo_cadena, nombre_fabricante, tienda_motorola, fecha, semana, mes, dia, ano, modelo_color, sellout, valor_venta, modelo FROM datos_producto WHERE codigo_cliente = %s AND nombre_fabricante = %s AND mes = %s AND modelo = %s AND sellout != 0", (codigo_cliente, nombre_fabricante, mes_seleccionado, producto_seleccionado))
                else:
                    cur.execute("SELECT codigo_cadena, nombre_fabricante, tienda_motorola, fecha, semana, mes, dia, ano, modelo_color, sellout, valor_venta, modelo FROM datos_producto WHERE codigo_cliente = %s AND nombre_fabricante = %s AND mes = %s AND sellout != 0", (codigo_cliente, nombre_fabricante, mes_seleccionado))
            elif filtro == 'semana':
                semana_seleccionada = request.form["semana"]
                cur = mysql.connection.cursor()
                if producto_seleccionado:  # Verifica si se ha seleccionado un producto
                    cur.execute("SELECT codigo_cadena, nombre_fabricante, tienda_motorola, fecha, semana, mes, dia, ano, modelo_color, sellout, valor_venta, modelo FROM datos_producto WHERE codigo_cliente = %s AND nombre_fabricante = %s AND semana = %s AND modelo = %s AND sellout != 0", (codigo_cliente, nombre_fabricante, semana_seleccionada, producto_seleccionado))
                else:
                    cur.execute("SELECT codigo_cadena, nombre_fabricante, tienda_motorola, fecha, semana, mes, dia, ano, modelo_color, sellout, valor_venta, modelo FROM datos_producto WHERE codigo_cliente = %s AND nombre_fabricante = %s AND semana = %s AND sellout != 0", (codigo_cliente, nombre_fabricante, semana_seleccionada))

            ventas_filtradas = cur.fetchall()
            cur.close()

            # Crear una lista de diccionarios para las ventas filtradas
            ventas_formateadas = []
            for venta in ventas_filtradas:
                venta_dict = {
                    "codigo_cadena": venta[0],
                    "nombre_fabricante": venta[1],
                    "tienda_motorola": venta[2],
                    "fecha": venta[3],
                    "semana": venta[4],
                    "mes": venta[5],
                    "dia": venta[6],
                    "ano": venta[7],
                    "modelo_color": venta[8],
                    "sellout": venta[9],
                    "valor_venta": venta[10],
                    "modelo": venta[11]
                }
                ventas_formateadas.append(venta_dict)

            # Devuelve las ventas formateadas en formato JSON
            return jsonify(ventas_formateadas)
        else:
            return "Error: Método de solicitud no válido."
    else:
        return redirect(url_for('login'))

@app.route('/obtener-meses', methods=['GET'])
def obtener_meses():
    # Crear un cursor para realizar consultas SQL
    conexion = mysql.connection
    cur = conexion.cursor()

    # Consultar los meses únicos en la tabla datos_producto
    cur.execute("SELECT DISTINCT mes FROM datos_producto")
    meses = [row[0] for row in cur.fetchall()]

    # Cerrar el cursor después de la consulta
    cur.close()

    # Devolver los meses como respuesta JSON
    return jsonify(meses)

@app.route('/obtener-semanas', methods=['GET'])
def obtener_semanas():
    # Crear un cursor para realizar consultas SQL
    conexion = mysql.connection
    cur = conexion.cursor()

    # Consultar los meses únicos en la tabla datos_producto
    cur.execute("SELECT DISTINCT semana FROM datos_producto")
    semanas = [row[0] for row in cur.fetchall()]

    # Cerrar el cursor después de la consulta
    cur.close()

    # Devolver los meses como respuesta JSON
    return jsonify(semanas)

@app.route('/obtener-productos', methods=['GET'])
def obtener_productos():
    # Crear un cursor para realizar consultas SQL
    conexion = mysql.connection
    cur = conexion.cursor()

    # Consultar los meses únicos en la tabla datos_producto
    cur.execute("SELECT DISTINCT modelo FROM datos_producto")
    productos = [row[0] for row in cur.fetchall()]

    # Cerrar el cursor después de la consulta
    cur.close()

    # Devolver los meses como respuesta JSON
    return jsonify(productos)

# Diccionario de meses en español
meses_espanol = {
    'january': 'enero',
    'february': 'febrero',
    'march': 'marzo',
    'april': 'abril',
    'may': 'mayo',
    'june': 'junio',
    'july': 'julio',
    'august': 'agosto',
    'september': 'septiembre',
    'october': 'octubre',
    'november': 'noviembre',
    'december': 'diciembre'
}

@app.route('/obtener_mes_ano_actual', methods=['GET'])
def obtener_mes_y_ano_actual():
    now = datetime.now()
    mes_actual = now.strftime('%B').lower()  # Convertir a minúsculas
    mes_actual_espanol = meses_espanol.get(mes_actual)  # Obtener el nombre en español o mantenerlo en inglés
    ano_actual = now.year

    return jsonify({"mes_actual": mes_actual_espanol, "ano": ano_actual})


@app.route('/obtener-mes-form-dash', methods=['GET'])
def obtener_mes_form_dash():
    conexion = mysql.connection
    cur = conexion.cursor()

    # Obtener el id_usuario de la sesión
    id_usuario = session.get('id')

    # Consultar la tabla mes_consulta_dash para obtener el mes_from_dash del usuario actual
    cur.execute("SELECT mes_form_dash FROM mes_consulta_dash WHERE id_usuario = %s", (id_usuario,))
    mes_form_dash_result = cur.fetchone()
    mes_form_dash = mes_form_dash_result[0] if mes_form_dash_result is not None else None

    cur.close()

    return jsonify({'id_usuario': id_usuario, 'mes_form_dash': mes_form_dash})

@app.route('/obtener-ventas-objetivo', methods=['POST'])
def obtener_ventas_objetivo():
    data = request.json
    mes = data['mes']
    nombre_fabricante = session.get('nombre_fabricante')

    conexion = mysql.connection
    cur = conexion.cursor()

    # Lógica para obtener las ventas del mes y fabricante desde la base de datos
    cur.execute("SELECT SUM(valor_venta) FROM datos_producto WHERE mes = %s AND ano = YEAR(CURRENT_DATE()) AND nombre_fabricante = %s", (mes, nombre_fabricante,))
    ventas_mes_result = cur.fetchone()
    ventas_mes = float(ventas_mes_result[0]) if ventas_mes_result is not None else 0.0

    # Lógica para obtener el objetivo del mes desde la base de datos
    cur.execute("SELECT importe FROM target_total_eci WHERE mes = %s AND ano = YEAR(CURRENT_DATE())", (mes,))
    objetivo_mes_result = cur.fetchone()
    objetivo_mes = float(objetivo_mes_result[0]) if objetivo_mes_result is not None else 0.0

    cur.close()

    return jsonify({'ventas_mes': ventas_mes, 'objetivo_mes': objetivo_mes})



def obtener_mes_actual():
    now = datetime.now()
    mes_actual = now.strftime('%B').lower()  # Convertir a minúsculas
    mes_actual_espanol = meses_espanol.get(mes_actual)  # Obtener el nombre en español o mantenerlo en inglés
    print("Mes actual:", mes_actual_espanol)  # Depuración
    return mes_actual_espanol

@app.route('/obtener-ventas-objetivo-personales', methods=['POST'])
def obtener_ventas_objetivo_personales():
    data = request.json
    mes = data['mes']

    conexion = mysql.connection
    cur = conexion.cursor()

    if 'logueado' in session:
        if request.method == 'POST':
            codigo_cliente = session['codigo_cliente']
            nombre_fabricante = session['nombre_fabricante']
            id_fabricante = session['id_fabricante']

            # Lógica para obtener las ventas del mes desde la base de datos
            cur.execute("SELECT SUM(valor_venta) FROM datos_producto WHERE mes = %s AND ano = YEAR(CURRENT_DATE()) AND codigo_cliente = %s AND nombre_fabricante = %s", (mes, codigo_cliente, nombre_fabricante,))
            ventas_mes_result = cur.fetchone()
            ventas_mes_usuario = ventas_mes_result[0] if ventas_mes_result is not None else 0

            # Lógica para obtener el objetivo del mes desde la base de datos
            cur.execute("SELECT importe FROM target_personales_eci WHERE mes = %s AND ano = YEAR(CURRENT_DATE()) AND codigo_cliente = %s AND id_fabricante = %s", (mes, codigo_cliente, id_fabricante,))
            objetivo_mes_result = cur.fetchone()
            objetivo_mes_usuario = objetivo_mes_result[0] if objetivo_mes_result is not None else 0

            cur.close()

            return jsonify({'ventas_mes_usuario': ventas_mes_usuario, 'objetivo_mes_usuario': objetivo_mes_usuario})


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000, threaded=True)

