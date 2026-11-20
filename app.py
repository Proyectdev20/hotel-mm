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
DEMO_PAYMENT_ENABLED = os.environ.get("DEMO_PAYMENT_ENABLED", "false").strip().lower() == "true"


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


def asegurar_columna_estado_pago(conn):
    cur = conn.cursor()
    cur.execute("""
        ALTER TABLE pagos
        ADD COLUMN IF NOT EXISTS estado VARCHAR(20) NOT NULL DEFAULT 'Confirmado'
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
        return render_template(
            "consultar_factura.html",
            error="Ingresa el código de factura para realizar la búsqueda."
        )
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
        asegurar_columna_estado_pago(conn)
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
                p.metodo_pago,
                p.monto_pagado,
                p.monto_pendiente
            FROM facturas f
            INNER JOIN reservas r ON f.id_reserva = r.id_reserva
            INNER JOIN clientes c ON r.id_cliente = c.id_cliente
            LEFT JOIN (
                SELECT
                    id_reserva,
                    STRING_AGG(DISTINCT metodo_pago, ', ') AS metodo_pago,
                    COALESCE(SUM(monto) FILTER (WHERE estado = 'Confirmado'), 0) AS monto_pagado,
                    COALESCE(SUM(monto) FILTER (WHERE estado = 'Pendiente'), 0) AS monto_pendiente
                FROM pagos
                GROUP BY id_reserva
            ) p ON r.id_reserva = p.id_reserva
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
                monto_pagado=float(datos[9]) if datos[9] is not None else 0,
                monto_pendiente=float(datos[10]) if datos[10] is not None else 0,
                saldo_monto=max(
                    0,
                    float(datos[7])
                    - (float(datos[9]) if datos[9] is not None else 0)
                    - (float(datos[10]) if datos[10] is not None else 0)
                ),
                factura_codigo=codigo
            )
        else:
            return render_template(
                "consultar_factura.html",
                codigo=codigo,
                error="No encontramos una factura con ese código. Revísalo e inténtalo nuevamente."
            ), 404

    except Exception as e:
        print("❌ Error al recuperar la factura:", e)
        return "Ocurrió un error interno al procesar la factura.", 500


@app.route("/factura/<codigo>/pagar-saldo")
def pagar_saldo(codigo):
    try:
        conn = conexion()
        asegurar_columna_estado_pago(conn)
        cur = conn.cursor()
        cur.execute("""
            SELECT
                f.total,
                COALESCE(p.monto_pagado, 0),
                COALESCE(p.monto_pendiente, 0)
            FROM facturas f
            INNER JOIN reservas r ON f.id_reserva = r.id_reserva
            LEFT JOIN (
                SELECT
                    id_reserva,
                    SUM(monto) FILTER (WHERE estado = 'Confirmado') AS monto_pagado,
                    SUM(monto) FILTER (WHERE estado = 'Pendiente') AS monto_pendiente
                FROM pagos
                GROUP BY id_reserva
            ) p ON r.id_reserva = p.id_reserva
            WHERE f.codigo = %s
        """, (codigo,))
        datos = cur.fetchone()
        cur.close()
        conn.close()

        if not datos:
            return render_template(
                "consultar_factura.html",
                codigo=codigo,
                error="No encontramos una factura con ese código. Revísalo e inténtalo nuevamente."
            ), 404

        total, pagado, pendiente = (float(valor or 0) for valor in datos)
        saldo = max(0, total - pagado - pendiente)
        return render_template(
            "pagar_saldo.html",
            factura_codigo=codigo,
            saldo_monto=saldo,
            monto_pendiente=pendiente,
            demo_payment_enabled=DEMO_PAYMENT_ENABLED
        )
    except Exception as e:
        print("Error al consultar el saldo de la factura:", e)
        return "Ocurrió un error interno al consultar el saldo.", 500


@app.route("/factura/<codigo>/pagar-saldo/demo", methods=["POST"])
def simular_pago_saldo(codigo):
    if not DEMO_PAYMENT_ENABLED:
        return "La simulación de pagos está deshabilitada.", 404

    metodo_pago = request.form.get("metodoPagoSaldo", "")
    metodos_demo = {
        "Tarjeta de crédito",
        "Tarjeta de débito",
        "Transferencia bancaria"
    }
    if metodo_pago not in metodos_demo:
        return "Selecciona un método de pago válido.", 400

    conn = conexion()
    asegurar_columna_estado_pago(conn)
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT r.id_reserva, r.total
            FROM facturas f
            INNER JOIN reservas r ON f.id_reserva = r.id_reserva
            WHERE f.codigo = %s
            FOR UPDATE OF r
        """, (codigo,))
        reserva = cur.fetchone()
        if not reserva:
            conn.rollback()
            return "La factura solicitada no existe.", 404

        id_reserva, total = reserva
        cur.execute("""
            SELECT
                COALESCE(SUM(monto) FILTER (WHERE estado = 'Confirmado'), 0),
                COALESCE(SUM(monto) FILTER (WHERE estado = 'Pendiente'), 0)
            FROM pagos
            WHERE id_reserva = %s
        """, (id_reserva,))
        pagado, pendiente = cur.fetchone()
        saldo = max(0, total - pagado - pendiente)

        cur.execute("""
            UPDATE pagos
            SET estado = 'Confirmado'
            WHERE id_reserva = %s AND estado = 'Pendiente'
        """, (id_reserva,))
        if saldo > 0:
            cur.execute("""
                INSERT INTO pagos (id_reserva, metodo_pago, monto, estado)
                VALUES (%s, %s, %s, %s)
            """, (
                id_reserva,
                f"Demostración: {metodo_pago}",
                saldo,
                "Confirmado"
            ))

        cur.execute(
            "UPDATE reservas SET estado = %s WHERE id_reserva = %s",
            ("Confirmada", id_reserva)
        )
        conn.commit()
        return redirect(url_for("ver_factura", codigo=codigo))
    except Exception as e:
        conn.rollback()
        print("Error al simular el pago de demostración:", e)
        return "No se pudo completar la simulación del pago.", 500
    finally:
        cur.close()
        conn.close()


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
        asegurar_columna_estado_pago(conn)
        cur = conn.cursor()

        # 1. Total de reservas registradas
        cur.execute("SELECT COUNT(*) FROM reservas;")
        resultado_res = cur.fetchone()
        total_reservas = resultado_res[0] if (resultado_res and resultado_res) else 0

        # 2. Cantidad de clientes uniques registrados
        cur.execute("SELECT COUNT(*) FROM clientes;")
        resultado_cli = cur.fetchone()
        total_clientes = resultado_cli[0] if (resultado_cli and resultado_cli) else 0

        # 3. Sumatoria de los pagos realmente percibidos
        cur.execute("""
            SELECT COALESCE(SUM(monto), 0)
            FROM pagos
            WHERE estado = 'Confirmado'
        """)
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
        asegurar_columna_estado_pago(conn)
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
        metodo_pago = datos["metodoPago"]
        saldo_en_hotel = bool(datos.get("saldoEnHotel", False))
        tipo_pago = (
            "50"
            if metodo_pago == "Pago en el hotel" or saldo_en_hotel
            else datos.get("tipoPago", "total")
        )

        if tipo_pago not in ("total", "50"):
            conn.rollback()
            return jsonify({"error": "Forma de pago no válida"}), 400

        monto_pagado = precio_total if tipo_pago == "total" else round(precio_total * 0.50)
        saldo_pendiente = precio_total - monto_pagado
        estado_reserva = "Confirmada"

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
            precio_total, estado_reserva, habitacion_recibida
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
            INSERT INTO pagos (id_reserva, metodo_pago, monto, estado)
            VALUES (%s,%s,%s,%s)
        """, (id_reserva, metodo_pago, monto_pagado, "Pendiente"))

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            "codigo": codigo,
            "total": precio_total,
            "pagado": 0,
            "pago_pendiente": monto_pagado,
            "saldo": saldo_pendiente,
            "tipo_pago": tipo_pago
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
    asegurar_columna_estado_pago(conn)
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
            p.metodo_pago,
            p.monto_pagado,
            p.monto_pendiente
        FROM reservas r
        INNER JOIN clientes c
            ON r.id_cliente = c.id_cliente
        LEFT JOIN facturas f
            ON r.id_reserva = f.id_reserva
        LEFT JOIN (
            SELECT
                id_reserva,
                STRING_AGG(DISTINCT metodo_pago, ', ') AS metodo_pago,
                COALESCE(SUM(monto) FILTER (WHERE estado = 'Confirmado'), 0) AS monto_pagado,
                COALESCE(SUM(monto) FILTER (WHERE estado = 'Pendiente'), 0) AS monto_pendiente
            FROM pagos
            GROUP BY id_reserva
        ) p
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
            "metodo_pago": fila[11] or "No especificado",
            "monto_pagado": float(fila[12]) if fila[12] is not None else 0,
            "monto_pendiente": float(fila[13]) if fila[13] is not None else 0,
            "saldo": max(
                0,
                float(fila[6])
                - (float(fila[12]) if fila[12] is not None else 0)
                - (float(fila[13]) if fila[13] is not None else 0)
            )
        })

    cur.close()
    conn.close()

    return jsonify(reservas)


@app.route("/api/reservas/<int:id_reserva>/confirmar-saldo", methods=["POST"])
@administrador_requerido
def confirmar_saldo_reserva(id_reserva):
    conn = conexion()
    asegurar_columna_estado_pago(conn)
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT total FROM reservas WHERE id_reserva = %s FOR UPDATE",
            (id_reserva,)
        )
        reserva = cur.fetchone()
        if not reserva:
            conn.rollback()
            return jsonify({"error": "La reserva no existe"}), 404

        cur.execute("""
            SELECT
                COALESCE(SUM(monto) FILTER (WHERE estado = 'Confirmado'), 0),
                COALESCE(SUM(monto) FILTER (WHERE estado = 'Pendiente'), 0)
            FROM pagos
            WHERE id_reserva = %s
        """, (id_reserva,))
        total_pagado, total_pendiente = cur.fetchone()
        saldo = reserva[0] - total_pagado - total_pendiente
        if saldo <= 0:
            conn.rollback()
            return jsonify({"error": "La reserva no tiene saldo pendiente"}), 409

        cur.execute("""
            INSERT INTO pagos (id_reserva, metodo_pago, monto, estado)
            VALUES (%s, %s, %s, %s)
        """, (id_reserva, "Transferencia bancaria", saldo, "Confirmado"))
        if total_pagado + saldo >= reserva[0] and total_pendiente == 0:
            cur.execute(
                "UPDATE reservas SET estado = %s WHERE id_reserva = %s",
                ("Confirmada", id_reserva)
            )

        conn.commit()
        return jsonify({"pagado": float(saldo), "saldo": 0})
    except Exception as e:
        conn.rollback()
        print("Error al confirmar el saldo de la reserva:", e)
        return jsonify({"error": "No se pudo registrar el pago confirmado"}), 500
    finally:
        cur.close()
        conn.close()


@app.route("/api/reservas/<int:id_reserva>/confirmar-pagos", methods=["POST"])
@administrador_requerido
def confirmar_pagos_pendientes(id_reserva):
    conn = conexion()
    asegurar_columna_estado_pago(conn)
    cur = conn.cursor()

    try:
        cur.execute(
            "SELECT total FROM reservas WHERE id_reserva = %s FOR UPDATE",
            (id_reserva,)
        )
        reserva = cur.fetchone()
        if not reserva:
            conn.rollback()
            return jsonify({"error": "La reserva no existe"}), 404

        cur.execute("""
            UPDATE pagos
            SET estado = 'Confirmado'
            WHERE id_reserva = %s AND estado = 'Pendiente'
            RETURNING monto
        """, (id_reserva,))
        pagos_confirmados = cur.fetchall()
        if not pagos_confirmados:
            conn.rollback()
            return jsonify({"error": "No hay pagos pendientes para verificar"}), 409

        monto_confirmado = sum(pago[0] for pago in pagos_confirmados)
        cur.execute("""
            SELECT COALESCE(SUM(monto), 0)
            FROM pagos
            WHERE id_reserva = %s AND estado = 'Confirmado'
        """, (id_reserva,))
        total_pagado = cur.fetchone()[0]
        if total_pagado >= reserva[0]:
            cur.execute(
                "UPDATE reservas SET estado = %s WHERE id_reserva = %s",
                ("Confirmada", id_reserva)
            )

        conn.commit()
        return jsonify({"pagado": float(monto_confirmado)})
    except Exception as e:
        conn.rollback()
        print("Error al verificar pagos de la reserva:", e)
        return jsonify({"error": "No se pudieron verificar los pagos"}), 500
    finally:
        cur.close()
        conn.close()

# =========================================
# INICIAR FLASK
# =========================================

if __name__ == "__main__":
    app.run(debug=False)