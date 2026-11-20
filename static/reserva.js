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
    const numeroTarjeta = porId("numeroTarjeta");
    const vencimientoTarjeta = porId("vencimientoTarjeta");
    const cvvTarjeta = porId("cvvTarjeta");
    const opcionesFormaPago = porId("opcionesFormaPago");
    const opcionPagoTotal = porId("opcionPagoTotal");
    const avisoPagoHotel = porId("avisoPagoHotel");
    const metodoAnticipoHotel = porId("metodoAnticipoHotel");
    const metodoAnticipo = porId("metodoAnticipo");
    const datosTransferencia = porId("datosTransferencia");
    const copiarAlias = porId("copiarAlias");
    const estadoCopiado = porId("estadoCopiado");

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

    const montoAhora =
        porId("montoAhora");

    const saldoPendiente =
        porId("saldoPendiente");

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

        const total =
            noches > 0
                ? noches * elegida.precio
                : 0;

        const pagoSeleccionado =
            document.querySelector(
                'input[name="tipo_pago"]:checked'
            );

        const esParcial =
            pagoSeleccionado &&
            pagoSeleccionado.value === "50";

        const pagado =
            esParcial
                ? Math.round(total * 0.50)
                : total;

        totalElemento.textContent =
            formatoGs(total);
        montoAhora.textContent =
            formatoGs(pagado);
        saldoPendiente.textContent =
            formatoGs(total - pagado);
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

        const esPagoEnHotel =
            metodo === "Pago en el hotel";

        const metodoParaAnticipo =
            esPagoEnHotel
                ? metodoAnticipo.value
                : metodo;

        const usaTransferencia =
            metodoParaAnticipo === "Transferencia bancaria";
        const usaTarjeta =
            metodoParaAnticipo === "Tarjeta de crédito" ||
            metodoParaAnticipo === "Tarjeta de débito";

        const opcionTotal =
            form.querySelector('input[name="tipo_pago"][value="total"]');
        const opcionMitad =
            form.querySelector('input[name="tipo_pago"][value="50"]');

        opcionesFormaPago.hidden = false;
        opcionPagoTotal.hidden = esPagoEnHotel;
        avisoPagoHotel.hidden = !esPagoEnHotel;
        metodoAnticipoHotel.hidden = !esPagoEnHotel;

        if (esPagoEnHotel) {
            opcionMitad.checked = true;
            opcionTotal.disabled = true;
        } else {
            opcionTotal.disabled = false;
        }

        datosTransferencia.hidden = !usaTransferencia;
        datosTarjeta.hidden = !usaTarjeta;
        [numeroTarjeta, vencimientoTarjeta, cvvTarjeta].forEach(campo => {
            campo.required = usaTarjeta;
            if (!usaTarjeta) campo.value = "";
        });

        actualizarResumen();
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

    metodoAnticipo.addEventListener(
        "change",
        mostrarCamposPago
    );

    numeroTarjeta.addEventListener("input", () => {
        const numeros = numeroTarjeta.value.replace(/\D/g, "").slice(0, 16);
        numeroTarjeta.value = numeros.replace(/(\d{4})(?=\d)/g, "$1 ").trim();
    });

    vencimientoTarjeta.addEventListener("input", () => {
        const numeros = vencimientoTarjeta.value.replace(/\D/g, "").slice(0, 4);
        vencimientoTarjeta.value = numeros.length > 2
            ? `${numeros.slice(0, 2)}/${numeros.slice(2)}`
            : numeros;
    });

    cvvTarjeta.addEventListener("input", () => {
        cvvTarjeta.value = cvvTarjeta.value.replace(/\D/g, "").slice(0, 4);
    });

    copiarAlias.addEventListener("click", async () => {
        try {
            await navigator.clipboard.writeText(
                porId("aliasTransferencia").textContent
            );
            estadoCopiado.textContent = " Alias copiado.";
        } catch (error) {
            estadoCopiado.textContent = " No se pudo copiar. Copia el alias manualmente.";
            console.error("No se pudo copiar el alias:", error);
        }
    });

    form
        .querySelectorAll(
            'input[name="tipo_pago"]'
        )
        .forEach(radio => {
            radio.addEventListener(
                "change",
                actualizarResumen
            );
        });

    // ========================================================
    // ENVÍO ASÍCRONO CORREGIDO (CALCULA EL TOTAL ANTES DE MANDAR)
    // ========================================================
    form.addEventListener("submit", async (e) => {
        e.preventDefault();

        const seleccionado = document.querySelector('input[name="pago"]:checked');
        const metodoBase = seleccionado ? seleccionado.value : "Tarjeta de crédito";
        const saldoEnHotel = metodoBase === "Pago en el hotel";
        const metodoPagoText = saldoEnHotel
            ? metodoAnticipo.value
            : metodoBase;
        const formaPago = document.querySelector('input[name="tipo_pago"]:checked');
        const tipoPago = saldoEnHotel
            ? "50"
            : (formaPago ? formaPago.value : "total");

        if (saldoEnHotel && !metodoPagoText) {
            if (mensaje) {
                mensaje.textContent = "Selecciona un método adicional para abonar el 50% de anticipo. El saldo restante se paga en el hotel.";
                mensaje.className = "mensaje error";
                mensaje.style.display = "block";
            }
            return;
        }

        const datosPayload = {
            nombre: nombre.value,
            documento: documento.value,
            correo: correo.value,
            telefono: telefono.value,
            entrada: entrada.value,
            salida: salida.value,
            habitacion: habitacion.value,
            personas: personas.value,
            metodoPago: metodoPagoText,
            tipoPago: tipoPago,
            saldoEnHotel: saldoEnHotel
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
                    mensaje.innerHTML = `✅ Reserva registrada. El pago queda pendiente de verificación por el hotel. 
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