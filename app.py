from flask import Flask
from flask import render_template
from flask import request
from flask import jsonify
from flask import redirect
from flask import session
from flask import url_for
from functools import wraps
import os
import secrets
from datetime import date

import psycopg2

app = Flask(__name__)
app.secret_key = os.environ.get("HOTEL_SECRET_KEY", "hotel-mm-development-key")


def administrador_requerido(vista):
    @wraps(vista)
    def protegida(*args, **kwargs):
        if not session.get("administrador_id"):
            return redirect(url_for("login", siguiente=request.path))
        return vista(*args, **kwargs)
    return protegida

# =========================================
# CONEXIÓN A POSTGRESQL
# =========================================

def conexion():
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return psycopg2.connect(database_url)

    return psycopg2.connect(
        host="localhost",
        database="Hotel_MM",
        user="postgres",
        password=os.environ.get("DB_PASSWORD"),
        port=os.environ.get("DB_PORT", "5432")
    )


def asegurar_columna_habitacion(conn):
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE reservas
        ADD COLUMN IF NOT EXISTS tipo_habitacion VARCHAR(50)
    """)
    conn.commit()
    cur.close()


# =========================================
# RUTAS HTML
# =========================================

@app.route("/")
def inicio():
    return render_template("index.html")

@app.route("/reserva")
def reserva():
    return render_template("reserva.html")

@app.route("/consultar-factura", methods=["GET", "POST"])
def consultar_factura():
    if request.method == "POST":
        codigo = request.form.get("codigo", "").strip()
        if codigo:
            return redirect(url_for("ver_factura", codigo=codigo))
    return render_template("consultar_factura.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]

        conn = conexion()
        cur = conn.cursor()
        asegurar_columna_habitacion(conn)

        cur.execute("""
            SELECT *
            FROM funcionarios
            WHERE usuario = %s
            AND password = %s
        """, (usuario, password))

        funcionario = cur.fetchone()

        cur.close()
        conn.close()

        if funcionario:
            session["administrador_id"] = funcionario[0]
            return redirect(url_for("panel"))

        return "Usuario o contraseña incorrectos"

    return render_template("login.html")

@app.route("/panel")
@administrador_requerido
def panel():
    return render_template("panel.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("inicio"))


# =========================================
# VISTA DE IMPRESIÓN DE FACTURA (CLIENTE)
# =========================================

@app.route("/factura/<codigo>")
def ver_factura(codigo):
    """
    Busca los datos unificados de la factura en la base de datos 
    y renderiza la plantilla optimizada para la impresión del cliente.
    """
    try:
        conn = conexion()
        cur = conn.cursor()

        # Consulta corregida usando p.id_reserva para unirse según tu pgAdmin
        cur.execute("""
            SELECT 
                c.nombre, 
                c.documento, 
                c.correo, 
                c.telefono,
                r.fecha_entrada, 
                r.fecha_salida, 
                r.cantidad_huespedes,
                f.total, 
                p.metodo_pago
            FROM facturas f
            INNER JOIN reservas r ON f.id_reserva = r.id_reserva
            INNER JOIN clientes c ON r.id_cliente = c.id_cliente
            LEFT JOIN pagos p ON r.id_reserva = p.id_reserva
            WHERE f.codigo = %s
        """, (codigo,))

        datos = cur.fetchone()
        cur.close()
        conn.close()

        if datos:
            # Enviamos los datos ordenados indexando las posiciones de la tupla resultado
            return render_template("factura.html",
                cliente_nombre=datos[0],
                cliente_documento=datos[1],
                cliente_correo=datos[2],
                cliente_telefono=datos[3],
                fecha_entrada=str(datos[4]),
                fecha_salida=str(datos[5]),
                cantidad_huespedes=datos[6],
                # Jinja realiza operaciones con literales float en la plantilla.
                # Convertimos el NUMERIC de PostgreSQL para evitar un TypeError
                # al calcular subtotal e IVA.
                total_monto=float(datos[7]),
                metodo_pago=datos[8] or "No especificado",
                factura_codigo=codigo
            )
        else:
            return "La factura solicitada no existe en el sistema.", 404

    except Exception as e:
        print("❌ Error al recuperar la factura:", e)
        return "Ocurrió un error interno al procesar la factura.", 500


# =========================================
# DATOS DE SOLO LECTURA PARA EL PANEL
# =========================================

@app.route("/api/dashboard/estadisticas", methods=["GET"])
@administrador_requerido
def obtener_estadisticas_dashboard():
    """
    Ruta segura de solo lectura con extracción indexada. 
    Muestra las métricas en tiempo real de tu base de datos.
    """
    try:
        conn = conexion()
        cur = conn.cursor()

        # 1. Total de reservas registradas
        cur.execute("SELECT COUNT(*) FROM reservas;")
        resultado_res = cur.fetchone()
        total_reservas = resultado_res[0] if (resultado_res and resultado_res) else 0

        # 2. Cantidad de clientes uniques registrados
        cur.execute("SELECT COUNT(*) FROM clientes;")
        resultado_cli = cur.fetchone()
        total_clientes = resultado_cli[0] if (resultado_cli and resultado_cli) else 0

        # 3. Sumatoria de todos los ingresos percibidos
        cur.execute("SELECT SUM(total) FROM facturas;")
        resultado_ing = cur.fetchone()
        total_ingresos = resultado_ing[0] if (resultado_ing and resultado_ing) else 0

        cur.close()
        conn.close()

        # Retornamos los datos limpios en formato JSON
        return jsonify({
            "reservas_totales": total_reservas,
            "clientes_registrados": total_clientes,
            "ingresos_totales": float(total_ingresos)
        })

    except Exception as e:
        print("Error de lectura en el dashboard:", e)
        return jsonify({
            "reservas_totales": 0,
            "clientes_registrados": 0,
            "ingresos_totales": 0.0
        }), 200


# =========================================
# GUARDAR RESERVA
# =========================================

@app.route("/api/reservas", methods=["POST"])
def guardar_reserva():
    try:
        datos = request.get_json()

        conn = conexion()
        cur = conn.cursor()
        # 1. CLIENTE - Extrae el ID entero puro usando [0]
        cur.execute("""
            INSERT INTO clientes (nombre, documento, correo, telefono)
            VALUES (%s,%s,%s,%s)
            RETURNING id_cliente
        """, (datos["nombre"], datos["documento"], datos["correo"], datos["telefono"]))

        id_cliente = cur.fetchone()[0]

        # 2. PROCESAMIENTO SEGURO DEL PRECIO DE LA HABITACIÓN
        mapa_precios = {
            "350000": 350000,
            "500000": 500000,
            "750000": 750000
        }

        habitacion_recibida = str(datos["habitacion"]).strip()
        precio_noche = mapa_precios.get(habitacion_recibida)
        if precio_noche is None:
            conn.rollback()
            return jsonify({"error": "Tipo de habitación no válido"}), 400

        fecha_entrada = date.fromisoformat(datos["entrada"])
        fecha_salida = date.fromisoformat(datos["salida"])
        noches = (fecha_salida - fecha_entrada).days
        if noches <= 0:
            conn.rollback()
            return jsonify({"error": "La fecha de salida debe ser posterior a la entrada"}), 400

        precio_total = noches * precio_noche

        # 3. RESERVA - Extrae el ID entero puro usando [0]
        cur.execute("""
            INSERT INTO reservas (
                id_cliente, fecha_entrada, fecha_salida, cantidad_huespedes,
                total, estado, tipo_habitacion
            )
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            RETURNING id_reserva
        """, (
            id_cliente, datos["entrada"], datos["salida"], datos["personas"],
            precio_total, "Confirmada", habitacion_recibida
        ))

        id_reserva = cur.fetchone()[0]

        # 4. FACTURA - Vinculación del código incremental con [0]
        codigo = f"FAC-{secrets.token_urlsafe(8)}"

        cur.execute("""
            INSERT INTO facturas (id_reserva, codigo, subtotal, iva, total)
            VALUES (%s,%s,%s,%s,%s)
            RETURNING id_factura
        """, (id_reserva, codigo, precio_total, 0, precio_total))

        id_factura = cur.fetchone()[0]

        # 5. PAGO - Sincronizado exactamente con las columnas de tu pgAdmin
        cur.execute("""
            INSERT INTO pagos (id_reserva, metodo_pago, monto)
            VALUES (%s,%s,%s)
        """, (id_reserva, datos["metodoPago"], precio_total))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "codigo": codigo,
            "total": precio_total
        })

    except Exception as e:
        print("❌ Error crítico en guardar_reserva:", e)
        return jsonify({"error": "No se pudo procesar el registro en la base de datos"}), 500


# =========================================
# LISTAR RESERVAS
# =========================================

@app.route("/api/reservas", methods=["GET"])
@administrador_requerido
def listar_reservas():
    conn = conexion()
    asegurar_columna_habitacion(conn)
    cur = conn.cursor()
    nombres_habitacion = {
        "350000": "Estándar",
        "500000": "Deluxe",
        "750000": "Suite presidencial"
    }

    cur.execute("""
        SELECT
            r.id_reserva,
            c.nombre,
            c.documento,
            r.fecha_entrada,
            r.fecha_salida,
            r.cantidad_huespedes,
            r.total,
            r.estado,
            r.tipo_habitacion,
            f.codigo,
            f.total,
            p.metodo_pago
        FROM reservas r
        INNER JOIN clientes c
            ON r.id_cliente = c.id_cliente
        LEFT JOIN facturas f
            ON r.id_reserva = f.id_reserva
        LEFT JOIN pagos p
            ON r.id_reserva = p.id_reserva
        ORDER BY r.id_reserva DESC
    """)

    filas = cur.fetchall()
    reservas = []

    for fila in filas:
        reservas.append({
            "id": fila[0],
            "nombre": fila[1],
            "documento": fila[2],
            "entrada": str(fila[3]),
            "salida": str(fila[4]),
            "personas": fila[5],
            "total": float(fila[6]),
            "estado": fila[7],
            "habitacion": nombres_habitacion.get(
                str(fila[8]), fila[8]
            ) if fila[8] else "No registrada",
            "factura_codigo": fila[9],
            "factura_total": float(fila[10]) if fila[10] is not None else None,
            "metodo_pago": fila[11] or "No especificado"
        })

    cur.close()
    conn.close()

    return jsonify(reservas)

# =========================================
# INICIAR FLASK
# =========================================

if __name__ == "__main__":
    app.run(debug=False)