const consultas = "http://127.0.0.1:3010";
const reportes = "http://127.0.0.1:3020";
const estado = document.getElementById("estado");

document.getElementById("acceso").addEventListener("submit", async (evento) => {
  evento.preventDefault();
  estado.textContent = "Entrando…";
  const acceso = await fetch("/api/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      correo: document.getElementById("correo").value,
      contrasena: document.getElementById("contrasena").value,
    }),
  });
  const cuerpo = await acceso.json();
  if (!acceso.ok) {
    estado.textContent = cuerpo.mensaje || "No se pudo entrar";
    return;
  }
  const headers = { Authorization: `Bearer ${cuerpo.token}`, Accept: "application/json" };
  const respuesta = await fetch(`${reportes}/api/v1/reports/campanias-por-estado`, { headers });
  const reporte = await respuesta.json();
  if (!respuesta.ok) {
    estado.textContent = reporte.error?.message || "El reporte no está disponible";
    return;
  }
  estado.textContent = `${reporte.message}. Caché: ${reporte.meta.cache}. Clave: ${reporte.meta.clave_cache}`;
  Highcharts.chart("grafica", {
    chart: { type: "column" },
    title: { text: "Campañas por estado" },
    xAxis: { categories: reporte.data.categories },
    yAxis: { title: { text: "Campañas" }, allowDecimals: false },
    series: reporte.data.series,
    credits: { enabled: false },
  });
  const lista = await fetch(`${consultas}/api/v1/queries/campanias?limit=5`, { headers });
  const consultasJson = await lista.json();
  if (lista.ok) {
    estado.textContent += `. Consulta de campañas: ${consultasJson.pagination.total} registros, caché ${consultasJson.meta.cache}.`;
  }
});
