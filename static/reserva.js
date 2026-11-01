document.addEventListener("DOMContentLoaded", () => {

    console.log("reserva.js cargado");

    const form = document.getElementById("formReserva");

    if (!form) {
        console.error("No se encontró el formulario");
        return;
    }

    const porId = id => document.getElementById(id);

    const nombre = porId("nombre");
    const documento = porId("documento");
    const correo = porId("correo");
    const telefono = porId("telefono");
    const entrada = porId("entrada");
    const salida = porId("salida");
    const habitacion = porId("habitacion");
    const personas = porId("personas");
    const mensaje = porId("mensaje");
    const datosTarjeta = porId("datosTarjeta");

    const botonEnviar =
        form.querySelector('button[type="submit"]');

    const nombreHabitacion =
        porId("nombreHabitacion");

    const precioNoche =
        porId("precioNoche");

    const resumenPersonas =
        porId("resumenPersonas");

    const nochesElemento =
        porId("noches");

    const resumenEntrada =
        porId("resumenEntrada");

    const resumenSalida =
        porId("resumenSalida");

    const totalElemento =
        porId("total");

    const precios = {
        "350000": {
            nombre: "Estándar",
            precio: 350000
        },

        "500000": {
            nombre: "Deluxe",
            precio: 500000
        },

        "750000": {
            nombre: "Suite presidencial",
            precio: 750000
        }
    };

    const formatoGs =
        valor => "Gs. " +
        Number(valor).toLocaleString("es-PY");

    const ahora = new Date();

    ahora.setMinutes(
        ahora.getMinutes() -
        ahora.getTimezoneOffset()
    );

    const hoyISO =
        ahora.toISOString().slice(0, 10);

    entrada.min = hoyISO;
    salida.min = hoyISO;

    function fechaLegible(valor) {

        if (!valor)
            return "No seleccionada";

        const [anio, mes, dia] =
            valor.split("-");

        return `${dia}/${mes}/${anio}`;
    }

    function calcularNoches() {

        if (!entrada.value || !salida.value)
            return 0;

        const e =
            new Date(`${entrada.value}T00:00:00`);

        const s =
            new Date(`${salida.value}T00:00:00`);

        return Math.round(
            (s - e) / 86400000
        );
    }

    function actualizarResumen() {

        const elegida =
            precios[habitacion.value] ||
            precios["350000"];

        const noches =
            calcularNoches();

        nombreHabitacion.textContent =
            elegida.nombre;

        precioNoche.textContent =
            formatoGs(elegida.precio);

        resumenPersonas.textContent =
            personas.value;

        nochesElemento.textContent =
            Math.max(0, noches);

        resumenEntrada.textContent =
            fechaLegible(entrada.value);

        resumenSalida.textContent =
            fechaLegible(salida.value);

        totalElemento.textContent =
            formatoGs(
                noches > 0
                    ? noches * elegida.precio
                    : 0
            );
    }

    function actualizarFechas() {

        salida.min =
            entrada.value || hoyISO;

        if (
            entrada.value &&
            salida.value &&
            salida.value <= entrada.value
        ) {
            salida.value = "";
        }

        actualizarResumen();
    }

    function mostrarCamposPago() {

        const seleccionado =
            document.querySelector(
                'input[name="pago"]:checked'
            );

        if (!seleccionado) return;

        const metodo =
            seleccionado.value;

        console.log("Método:", metodo);

        const usaTarjeta =
            metodo === "Tarjeta de crédito" ||
            metodo === "Tarjeta de débito";

        console.log(
            "Usa tarjeta:",
            usaTarjeta
        );

        if (datosTarjeta) {

            datosTarjeta.style.display =
                usaTarjeta
                    ? "block"
                    : "none";
        }

        if (!usaTarjeta) {

            const titular =
                porId("titular");

            const tarjetaInput =
                porId("tarjeta");

            const vencimientoInput =
                porId("vencimiento");

            const cvv =
                porId("cvv");

            if (titular) titular.value = "";
            if (tarjetaInput) tarjetaInput.value = "";
            if (vencimientoInput) vencimientoInput.value = "";
            if (cvv) cvv.value = "";
        }
    }

    [entrada,
     salida,
     habitacion,
     personas].forEach(campo => {

        campo.addEventListener(
            "change",
            () => {

                if (campo === entrada) {
                    actualizarFechas();
                } else {
                    actualizarResumen();
                }
            }
        );

    });

    form
        .querySelectorAll(
            'input[name="pago"]'
        )
        .forEach(radio => {

            radio.addEventListener(
                "change",
                mostrarCamposPago
            );

        });

    const tarjeta =
        porId("tarjeta");

    if (tarjeta) {

        tarjeta.addEventListener(
            "input",
            () => {

                const numeros =
                    tarjeta.value
                        .replace(/\D/g, "")
                        .slice(0, 16);

                tarjeta.value =
                    numeros
                        .replace(
                            /(\d{4})(?=\d)/g,
                            "$1 "
                        )
                        .trim();
            }
        );
    }

    const vencimiento =
        porId("vencimiento");

    if (vencimiento) {

        vencimiento.addEventListener(
            "input",
            () => {

                let numeros =
                    vencimiento.value
                        .replace(/\D/g, "")
                        .slice(0, 4);

                if (numeros.length > 2) {

                    numeros =
                        numeros.slice(0, 2)
                        + "/"
                        + numeros.slice(2);
                }

                vencimiento.value =
                    numeros;
            }
        );
    }

    // ========================================================
    // ENVÍO ASÍCRONO CORREGIDO (CALCULA EL TOTAL ANTES DE MANDAR)
    // ========================================================
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const seleccionado = document.querySelector('input[name="pago"]:checked');
        const metodoPagoText = seleccionado ? seleccionado.value : "Tarjeta de crédito";

        const datosPayload = {
            nombre: nombre.value,
            documento: documento.value,
            correo: correo.value,
            telefono: telefono.value,
            entrada: entrada.value,
            salida: salida.value,
            habitacion: habitacion.value,
            personas: personas.value,
            metodoPago: metodoPagoText
        };

        try {
            const respuesta = await fetch('/api/reservas', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(datosPayload)
            });

            if (respuesta.ok) {
                const resultado = await respuesta.json();
                if (mensaje) {
                    const urlFactura = `/factura/${encodeURIComponent(resultado.codigo)}`;
                    mensaje.innerHTML = `✅ ¡Pago confirmado! 
                        <a href="${urlFactura}" target="_blank" rel="noopener">
                            Ver factura ${resultado.codigo}
                        </a>`;
                    mensaje.style.display = 'block';
                    mensaje.className = "mensaje exito";
                }

                form.reset();
                mostrarCamposPago();
                actualizarResumen();

                const urlFactura = `/factura/${encodeURIComponent(resultado.codigo)}`;
                window.location.href = urlFactura;
            } else {
                alert("Error en el servidor al intentar registrar la reserva.");
            }
        } catch (error) {
            console.error("Error de comunicación:", error);
            alert("No se pudo conectar con el servidor del hotel.");
        }
    });

    console.log("JS funcionando");

    mostrarCamposPago();
    actualizarResumen();
});