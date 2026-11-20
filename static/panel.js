document.addEventListener("DOMContentLoaded", () => {
    cargarReservas();

    document.getElementById("tablaReservas").addEventListener("click", async event => {
        const boton = event.target.closest("[data-accion-pago]");
        if (!boton) return;

        const idReserva = boton.dataset.reservaId;
        const accion = boton.dataset.accionPago;
        const esVerificacion = accion === "verificar";
        const ruta = esVerificacion ? "confirmar-pagos" : "confirmar-saldo";
        const mensaje = esVerificacion
            ? `¿Verificaste en el banco los pagos pendientes de la reserva ${idReserva}?`
            : `¿Verificaste en el banco el pago del saldo restante de la reserva ${idReserva}?`;

        if (!window.confirm(mensaje)) return;

        boton.disabled = true;
        try {
            const respuesta = await fetch(`/api/reservas/${encodeURIComponent(idReserva)}/${ruta}`, {
                method: "POST"
            });
            const resultado = await respuesta.json();
            if (!respuesta.ok) {
                throw new Error(resultado.error || "No se pudo registrar el pago.");
            }

            alert(`Pago confirmado: Gs. ${Number(resultado.pagado).toLocaleString("es-PY")}`);
            await cargarReservas();
        } catch (error) {
            console.error(error);
            alert(error.message);
            boton.disabled = false;
        }
    });
});

function escaparHTML(valor) {
    return String(valor)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}

async function cargarReservas() {

    try {

        const respuesta = await fetch("/api/reservas");

        if (!respuesta.ok) {
            throw new Error("Error al obtener las reservas");
        }

        const reservas = await respuesta.json();

        const tabla =
            document.getElementById("tablaReservas");

        tabla.innerHTML = "";

        let ingresos = 0;

        reservas.forEach(reserva => {

            ingresos += Number(reserva.monto_pagado);

            tabla.innerHTML += `
            <tr>
                <td>${escaparHTML(reserva.id)}</td>
                <td>${escaparHTML(reserva.nombre)}</td>
                <td>${escaparHTML(reserva.documento)}</td>
                <td>${escaparHTML(reserva.entrada)}</td>
                <td>${escaparHTML(reserva.salida)}</td>
                <td>${escaparHTML(reserva.personas)}</td>
                <td>${escaparHTML(reserva.habitacion)}</td>
                <td>${reserva.factura_codigo
                    ? `<a href="/factura/${encodeURIComponent(reserva.factura_codigo)}" target="_blank" rel="noopener">${escaparHTML(reserva.factura_codigo)}</a>`
                    : "Sin factura"}</td>
                <td>${escaparHTML(reserva.metodo_pago)}</td>
                <td>Gs. ${Number(reserva.total).toLocaleString("es-PY")}</td>
                <td>Gs. ${Number(reserva.monto_pagado).toLocaleString("es-PY")}</td>
                <td>Gs. ${Number(reserva.monto_pendiente).toLocaleString("es-PY")}</td>
                <td>Gs. ${Number(reserva.saldo).toLocaleString("es-PY")}</td>
                <td>${escaparHTML(reserva.estado)}</td>
                <td>
                    ${Number(reserva.monto_pendiente) > 0
                        ? `<button type="button" class="btn-confirmar-pago" data-accion-pago="verificar" data-reserva-id="${escaparHTML(reserva.id)}">Verificar pago(s)</button>`
                        : ""}
                    ${Number(reserva.saldo) > 0
                        ? `<button type="button" class="btn-confirmar-pago" data-accion-pago="saldo" data-reserva-id="${escaparHTML(reserva.id)}">Confirmar saldo transferido</button>`
                        : ""}
                    ${Number(reserva.monto_pendiente) <= 0 && Number(reserva.saldo) <= 0
                        ? "Sin saldo"
                        : ""}
                </td>
            </tr>
            `;
        });

        document.getElementById("totalReservas").textContent =
            reservas.length;

        document.getElementById("totalClientes").textContent =
            reservas.length;

        document.getElementById("totalIngresos").textContent =
            "Gs. " + ingresos.toLocaleString("es-PY");

    }
    catch (error) {

        console.error(error);

        document.getElementById("tablaReservas").innerHTML = `
            <tr>
                <td colspan="15">
                    Error al cargar reservas
                </td>
            </tr>
        `;
    }
}