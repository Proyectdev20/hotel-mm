document.addEventListener("DOMContentLoaded", cargarReservas);

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
                <td>${reserva.id}</td>
                <td>${reserva.nombre}</td>
                <td>${reserva.documento}</td>
                <td>${reserva.entrada}</td>
                <td>${reserva.salida}</td>
                <td>${reserva.personas}</td>
                <td>Gs. ${Number(reserva.total).toLocaleString("es-PY")}</td>
                <td>${reserva.estado}</td>
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
                <td colspan="8">
                    Error al cargar reservas
                </td>
            </tr>
        `;
    }
}