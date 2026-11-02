document.addEventListener("DOMContentLoaded", cargarReservas);

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

            ingresos += Number(reserva.total);

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
                <td>${escaparHTML(reserva.estado)}</td>
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
                <td colspan="11">
                    Error al cargar reservas
                </td>
            </tr>
        `;
    }
}