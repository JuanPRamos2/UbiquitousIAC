const TOKEN_KEY = "nexum_token";
const NOTIF_KEY = "nexum_notif_leidas";
const state = {
  token: sessionStorage.getItem(TOKEN_KEY),
  me: null,
  seccion: "inicio",
  demo: sessionStorage.getItem(TOKEN_KEY) === "demo",
};

const CUENTAS_DEMO = {
  "ana.perez@empresa.com": {
    usuario_id: "USR-00001",
    perfil: "COLAB",
    nombre: "Ana",
    seudonimo_id: "SEUD-2026-014892",
    unidad_organizacional_id: "UO-CALLCENTER-TURNO-B",
  },
  "lucia.hernandez@empresa.com": {
    usuario_id: "USR-00011",
    perfil: "LIDER_TURNO",
    nombre: "Lucía",
    seudonimo_id: "SEUD-2026-009331",
    unidad_organizacional_id: "UO-CALLCENTER-TURNO-B",
  },
  "roberto.garcia@empresa.com": {
    usuario_id: "USR-00027",
    perfil: "AUDITOR",
    nombre: "Roberto",
    seudonimo_id: "SEUD-2026-002104",
    unidad_organizacional_id: "UO-CALLCENTER-TURNO-B",
  },
  "carlos.ramirez@empresa.com": {
    usuario_id: "USR-00002",
    perfil: "ADMIN_SISTEMA",
    nombre: "Carlos",
    unidad_organizacional_id: "UO-CALLCENTER-TURNO-B",
  },
};

async function hayApi() {
  try {
    const res = await fetch("/api/salud");
    const data = await res.json();
    return Boolean(data && typeof data.ok === "boolean");
  } catch {
    return false;
  }
}

function sesionDemo(correo, contrasena) {
  if (contrasena !== "demo123") return null;
  const cuenta = CUENTAS_DEMO[String(correo || "").trim().toLowerCase()];
  if (!cuenta) return null;
  return { token: "demo", correo, ...cuenta };
}

const MENSAJES = {
  CREDENCIALES_INVALIDAS: "Contraseña incorrecta. Usa demo123.",
  CUENTA_BLOQUEADA: "La cuenta está temporalmente bloqueada. Intente de nuevo más tarde.",
  SIN_TOKEN: "Su sesión ha caducado. Inicie sesión nuevamente.",
  TOKEN_INVALIDO: "Su sesión ha caducado. Inicie sesión nuevamente.",
  TOKEN_REVOCADO: "La sesión se cerró. Inicie sesión nuevamente.",
  YA_RESPONDIO: "Ya respondiste esta campaña. Solo se permite una respuesta por periodo.",
  SIN_CONSENTIMIENTO: "Necesitas consentimiento vigente para responder.",
  RBAC: "No tiene permiso para consultar esta sección.",
  CAMPANIA_INVALIDA: "La evaluación no está disponible en este momento.",
  CAMPANIA_NO_ASIGNADA: "Esta evaluación no corresponde a su equipo.",
  SEUDONIMO_INVALIDO: "No se encontró el participante indicado.",
  SEUDONIMO_AJENO: "No puede responder en nombre de otra persona.",
  PAYLOAD_INVALIDO: "Revise los datos e intente de nuevo.",
  K_INVALIDO: "El umbral debe ser un entero entre 2 y 50.",
  SIN_UNIDAD: "Su cuenta no tiene un equipo asignado.",
  SIN_SEUDONIMO: "Su cuenta no está habilitada para esta evaluación.",
  VALOR_FUERA_DE_ESCALA: "Alguna respuesta quedó fuera del rango permitido.",
  REACTIVO_FALTANTE: "Complete todas las preguntas obligatorias.",
  REACTIVO_DESCONOCIDO: "El cuestionario no coincide con la evaluación actual.",
  ERROR_TECNICO: "El servicio no está disponible por un momento. Intente de nuevo.",
  SIN_SESION: "Inicie sesión para continuar.",
};

const PERFIL_ETIQUETA = {
  COLAB: "Colaborador",
  LIDER_TURNO: "Líder de Turno",
  AUDITOR: "Auditor de Cumplimiento",
  ADMIN_SISTEMA: "Administrador del Sistema",
};

const MENU = {
  COLAB: [
    { id: "inicio", label: "Inicio" },
    { id: "consentimiento", label: "Mi consentimiento" },
    { id: "encuesta", label: "Responder encuesta" },
    { id: "misAccesos", label: "Quién vio mis datos" },
    { id: "notificaciones", label: "Notificaciones" },
  ],
  LIDER_TURNO: [
    { id: "inicio", label: "Inicio" },
    { id: "agregados", label: "Resultados por unidad" },
    { id: "reportes", label: "Reportes" },
    { id: "notificaciones", label: "Notificaciones" },
  ],
  AUDITOR: [
    { id: "inicio", label: "Inicio" },
    { id: "bitacora", label: "Bitácora de auditoría" },
    { id: "consentimientos", label: "Evidencia de consentimiento" },
    { id: "reportes", label: "Reportes" },
    { id: "notificaciones", label: "Notificaciones" },
  ],
  ADMIN_SISTEMA: [
    { id: "inicio", label: "Inicio" },
    { id: "usuarios", label: "Usuarios y perfiles" },
    { id: "unidades", label: "Unidades organizacionales" },
    { id: "instrumentos", label: "Instrumentos" },
    { id: "parametros", label: "Parámetros del sistema" },
    { id: "bitacora", label: "Bitácora de auditoría" },
    { id: "notificaciones", label: "Notificaciones" },
  ],
};

const ACCION_ETIQUETA = {
  LOGIN_EXITOSO: "LOGIN_EXITOSO",
  LOGIN_FALLIDO: "LOGIN_FALLIDO",
  LOGOUT: "LOGOUT",
  CREACION_RESPUESTA: "CREACION_RESPUESTA",
  CONSULTA_AGREGADO: "CONSULTA_AGREGADO",
  CONSULTA_HISTORIAL_CONSENTIMIENTO: "CONSULTA_HISTORIAL_CONSENTIMIENTO",
  CAMBIO_UMBRAL_K: "CAMBIO_UMBRAL_K",
  CAMBIO_CONSENTIMIENTO: "CAMBIO_CONSENTIMIENTO",
};

const ESCALA = ["Nunca", "Casi nunca", "A veces", "Casi siempre", "Siempre"];

const $ = (id) => document.getElementById(id);

function esc(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function mensajeAmigable(data) {
  if (data?.error && MENSAJES[data.error]) return MENSAJES[data.error];
  return "No fue posible completar la operación. Intente de nuevo.";
}

function toast(texto) {
  const t = $("toast");
  if (!t) return;
  t.textContent = texto || "";
  t.classList.add("show");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.remove("show"), 2600);
}

function errorLogin(texto) {
  const el = $("login-error");
  if (!el) return;
  el.hidden = !texto;
  el.textContent = texto || "";
}

function formatFecha(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso || "—");
  return d.toLocaleString("es-MX", { dateStyle: "short", timeStyle: "short" });
}

function formatDia(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso || "—");
  return d.toLocaleDateString("es-MX", { dateStyle: "medium" });
}

function primerNombre(me) {
  if (me?.nombre) return String(me.nombre).split(" ")[0];
  const correo = String(me?.correo || $("correo")?.value || "");
  const parte = correo.split("@")[0] || "usuario";
  return parte.split(".")[0].replace(/^./, (c) => c.toUpperCase());
}

async function api(path, opts = {}) {
  if (state.demo) {
    throw new Error("MODO_DEMO");
  }
  const headers = { ...(opts.headers || {}) };
  if (opts.body) headers["Content-Type"] = "application/json";
  if (state.token) headers.Authorization = `Bearer ${state.token}`;
  let res;
  try {
    res = await fetch(`/api${path}`, { ...opts, headers });
  } catch {
    throw new Error("No hay conexión con la plataforma. Intente más tarde.");
  }
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && path !== "/auth/login") {
    state.token = null;
    sessionStorage.removeItem(TOKEN_KEY);
    irPublico();
    irLogin();
    throw new Error(MENSAJES.TOKEN_INVALIDO);
  }
  if (!res.ok) throw new Error(mensajeAmigable(data));
  return data;
}

async function apiOpcional(path, opts = {}) {
  try {
    return await api(path, opts);
  } catch {
    return null;
  }
}

function asList(value) {
  if (Array.isArray(value)) return value;
  if (Array.isArray(value?.data)) return value.data;
  return [];
}

async function listaCatalogo(path) {
  return asList(await apiOpcional(path));
}

async function cargarCampanias() {
  return listaCatalogo("/catalogos/campanias");
}

async function cargarUnidades() {
  const lista = await listaCatalogo("/catalogos/unidades");
  if (lista.length) return lista;
  if (state.me?.unidad_organizacional_id) {
    return [{ unidad_organizacional_id: state.me.unidad_organizacional_id, nombre: "Su unidad" }];
  }
  return [];
}

async function cargarInstrumentos() {
  return listaCatalogo("/catalogos/instrumentos");
}

async function cargarK() {
  const full = await apiOpcional("/agregados/parametros");
  const n = Number(full?.k);
  if (Number.isFinite(n) && n > 0) return n;
  const only = await apiOpcional("/agregados/parametros/k");
  const k = Number(only?.k);
  return Number.isFinite(k) && k > 0 ? k : 5;
}

async function cargarConsentimientoPropio() {
  const a = await apiOpcional("/encuestas/consentimiento");
  if (a && typeof a.participando === "boolean") return a;
  const b = await apiOpcional("/portal/consentimiento");
  if (b && typeof b.participando === "boolean") return b;
  return { participando: true, historial: [], version_vigente: null };
}

async function guardarConsentimientoPropio(aceptar) {
  const opts = { method: "POST", body: JSON.stringify({ aceptar }) };
  try {
    return await api("/encuestas/consentimiento", opts);
  } catch {
    return api("/portal/consentimiento", opts);
  }
}

async function cargarCuentas() {
  const a = await apiOpcional("/catalogos/cuentas");
  if (a?.usuarios || a?.perfiles) return { usuarios: a.usuarios || [], perfiles: a.perfiles || [] };
  return { usuarios: [], perfiles: [] };
}

async function cargarConfiguracion() {
  const parametros = (await apiOpcional("/agregados/parametros")) || {};
  const portal = await apiOpcional("/portal/configuracion");
  const versiones =
    asList(portal?.versiones).length > 0
      ? asList(portal.versiones)
      : await listaCatalogo("/catalogos/versiones-consentimiento");
  return {
    k: Number(portal?.k || parametros.k || (await cargarK())),
    version_activa_consentimiento:
      portal?.version_activa_consentimiento || parametros.version_activa_consentimiento || null,
    versiones,
  };
}

async function cargarBitacora() {
  return asList(await apiOpcional("/auditoria"));
}

function irPublico() {
  $("publico").classList.add("on");
  $("login").classList.remove("on");
  $("app").classList.remove("on");
  window.scrollTo(0, 0);
}

function irLogin() {
  $("publico").classList.remove("on");
  $("login").classList.add("on");
  $("app").classList.remove("on");
  $("loginBox").hidden = false;
  $("recuperar").hidden = true;
  errorLogin("");
  window.scrollTo(0, 0);
}

function mostrarApp() {
  $("publico").classList.remove("on");
  $("login").classList.remove("on");
  $("app").classList.add("on");
}

function head(titulo, sub) {
  return `<div class="page-head"><h1>${titulo}</h1><p>${sub}</p></div>`;
}

function tarjetasMetricas(arr) {
  return `<div class="grid2" style="margin-bottom:18px">${arr
    .map(
      ([v, l]) =>
        `<div class="card metric" style="margin:0"><div class="v">${esc(v)}</div><div class="l">${esc(l)}</div></div>`
    )
    .join("")}</div>`;
}

function tagEstado(estado) {
  const ok = estado === "ACEPTADO" || estado === "EXITO" || estado === "Activa" || estado === "Activo";
  const warn = estado === "GRUPO_INSUFICIENTE" || estado === "Pendiente";
  const cls = ok ? "tag-ok" : warn ? "tag-warn" : "tag-off";
  return `<span class="tag ${cls}">${esc(estado)}</span>`;
}

function riesgoDe(promedio) {
  const n = Number(promedio);
  if (!Number.isFinite(n)) return { texto: "—", cls: "" };
  if (n < 2.5) return { texto: "ALTO", cls: "amber" };
  if (n < 3.5) return { texto: "MEDIO", cls: "amber" };
  return { texto: "BAJO", cls: "teal" };
}

function notifLeidas() {
  try {
    return JSON.parse(sessionStorage.getItem(NOTIF_KEY) || "{}");
  } catch {
    return {};
  }
}

function guardarNotifLeidas(mapa) {
  sessionStorage.setItem(NOTIF_KEY, JSON.stringify(mapa));
}

function claveNotif(item) {
  return `${state.me?.usuario_id || "x"}:${item.t}`;
}

function noLeidas(lista) {
  const leidas = notifLeidas();
  return lista.filter((n) => !leidas[claveNotif(n)]).length;
}

async function notificacionesPerfil() {
  const p = state.me.perfil;
  const campanias = await cargarCampanias();
  const k = await cargarK();
  const camp = campanias[0];
  if (p === "COLAB") {
    const cons = await cargarConsentimientoPropio();
    return [
      camp
        ? {
            t: "Nueva campaña disponible",
            m: `${camp.nombre} ya está abierta. Cierra el ${formatDia(camp.fecha_fin)}.`,
            f: "Campaña vigente",
          }
        : null,
      {
        t: cons.participando ? "Tu consentimiento sigue vigente" : "Tu consentimiento está revocado",
        m: cons.participando
          ? "No necesitas hacer nada. Puedes revisarlo cuando quieras."
          : "Sin consentimiento vigente no se muestran encuestas.",
        f: cons.version_vigente || "Aviso de privacidad",
      },
    ].filter(Boolean);
  }
  if (p === "LIDER_TURNO") {
    return [
      {
        t: "Umbral de grupo",
        m: `Los resultados de tu unidad solo se muestran con al menos ${k} respuestas.`,
        f: `k = ${k}`,
      },
      {
        t: "Consulta agregada",
        m: "Usa Resultados por unidad para ver promedios. Los grupos pequeños se suprimen.",
        f: "Regla de privacidad",
      },
    ];
  }
  if (p === "AUDITOR") {
    return [
      {
        t: "Consulta suprimida",
        m: "Las consultas con menos de k respuestas se registran como GRUPO_INSUFICIENTE.",
        f: "Bitácora",
      },
    ];
  }
  return [
    {
      t: "Parámetros del sistema",
      m: `El umbral k vigente es ${k}. Cada cambio queda en la bitácora.`,
      f: "Administración",
    },
  ];
}

function pintarNav() {
  const n = $("nav");
  n.innerHTML = "";
  const items = MENU[state.me.perfil] || [];
  for (const item of items) {
    const b = document.createElement("button");
    b.type = "button";
    if (item.id === "notificaciones") {
      b.innerHTML = "Notificaciones";
      notificacionesPerfil().then((lista) => {
        const nl = noLeidas(lista);
        if (nl) {
          b.innerHTML = `Notificaciones <span style="background:var(--amber);color:#fff;font-size:10px;font-weight:600;padding:1px 7px;border-radius:9px;margin-left:4px">${nl}</span>`;
        }
      });
    } else {
      b.textContent = item.label;
    }
    if (item.id === state.seccion) b.className = "sel";
    b.onclick = () => {
      state.seccion = item.id;
      pintarNav();
      render();
    };
    n.appendChild(b);
  }
}

async function entrar(me) {
  state.me = me;
  state.seccion = "inicio";
  mostrarApp();
  $("uName").textContent = me.nombre ? `${me.nombre}` : primerNombre(me);
  $("uRole").textContent = PERFIL_ETIQUETA[me.perfil] || me.perfil;
  pintarNav();
  await render();
}

function dibujarColumnas(id, categorias, valores) {
  const el = document.getElementById(id);
  if (!el) return;
  if (typeof Highcharts !== "undefined") {
    Highcharts.chart(id, {
      credits: { enabled: false },
      title: { text: null },
      chart: { type: "column", height: 300, style: { fontFamily: "Inter,sans-serif" }, backgroundColor: "transparent" },
      xAxis: { categories: categorias, lineColor: "#DCE1E8" },
      yAxis: { min: 0, max: 5, title: { text: "Promedio (1–5)" }, gridLineColor: "#EDEFF3" },
      legend: { enabled: false },
      series: [{ name: "Promedio", data: valores, color: "#1F3864", borderRadius: 3 }],
    });
    return;
  }
  el.innerHTML = categorias
    .map((c, i) => {
      const v = Number(valores[i] || 0);
      const ancho = Math.max(0, Math.min(100, (v / 5) * 100));
      return `<div class="bar-row"><div class="lab"><span>${esc(c)}</span><span class="n">${esc(v)}</span></div><div class="bar"><i style="width:${ancho}%"></i></div></div>`;
    })
    .join("");
}

async function consultarAgregado(unidadId, campaniaId) {
  return apiOpcional(`/agregados/${encodeURIComponent(unidadId)}/${encodeURIComponent(campaniaId)}`);
}

async function nombresReactivos(campania) {
  if (!campania?.instrumento_id) return {};
  const r = await apiOpcional(
    `/catalogos/instrumentos/${encodeURIComponent(campania.instrumento_id)}/versiones/${Number(campania.version_instrumento)}/reactivos`
  );
  return Object.fromEntries((r?.data || []).map((x) => [x.reactivo_id, { texto: x.texto, dim: x.dimension }]));
}

function cardAgregado(unidad, campania, data, nombres, k) {
  if (!data?.visible) {
    return `<div class="card"><h2>${esc(unidad.nombre)}</h2>
      <p class="card-sub">${esc(campania.nombre)}</p>
      <div class="suppressed"><div class="big">Resultado suprimido</div>
      <div class="small">Este grupo no alcanza el umbral mínimo de ${esc(data?.k || k)} respuestas.
      Mostrar el promedio permitiría deducir respuestas individuales.</div></div>
      <p class="note">La consulta quedó registrada en la bitácora con resultado <span class="mono">GRUPO_INSUFICIENTE</span>.</p></div>`;
  }
  const detalle = Object.entries(data.detalle || {});
  const chartId = `gdim-${unidad.unidad_organizacional_id}-${campania.campania_id}`.replace(/[^a-zA-Z0-9_-]/g, "");
  const cats = detalle.map(([id]) => nombres[id]?.dim || nombres[id]?.texto || id);
  const vals = detalle.map(([, v]) => Number(v));
  const riesgo = riesgoDe(data.promedio_global);
  setTimeout(() => dibujarColumnas(chartId, cats, vals), 30);
  return `<div class="card"><h2>${esc(unidad.nombre)}</h2>
    <p class="card-sub">${esc(campania.nombre)} · ${esc(data.total_respuestas)} respuestas</p>
    <div class="grid2" style="margin-bottom:20px">
      <div class="metric" style="padding:0"><div class="v">${esc(data.promedio_global)}</div><div class="l">Promedio general (escala 1–5)</div></div>
      <div class="metric" style="padding:0"><div class="v ${riesgo.cls}">${riesgo.texto}</div><div class="l">Nivel de riesgo del grupo</div></div>
    </div>
    <div id="${chartId}" class="chart"></div>
    <p class="note">Promedios de ${esc(data.total_respuestas)} personas. El sistema no expone respuestas individuales ni la lista de participantes.</p></div>`;
}

function tablaBitacora(rows) {
  if (!rows.length) {
    return `<div class="suppressed"><div class="big">Sin registros</div>
      <div class="small">Todavía no hay eventos que mostrar en este periodo.</div></div>`;
  }
  const puedeSeud = ["AUDITOR", "ADMIN_SISTEMA", "COLAB"].includes(state.me.perfil);
  return `<table><thead><tr><th>Fecha</th><th>Actor</th><th>Perfil</th><th>Acción</th><th>Recurso</th><th>Resultado</th></tr></thead><tbody>
  ${rows
    .map((b) => {
      let rec = b.recurso || "—";
      if (/^SEUD-/.test(rec) && !puedeSeud) rec = "Seudónimo protegido";
      return `<tr><td class="mono">${esc(formatFecha(b.timestamp))}</td>
        <td class="mono">${esc(b.actor_id === "DESCONOCIDO" ? "No identificado" : b.actor_id)}</td>
        <td>${esc(PERFIL_ETIQUETA[b.actor_perfil] || b.actor_perfil || "—")}</td>
        <td class="mono">${esc(ACCION_ETIQUETA[b.accion] || b.accion)}</td>
        <td class="mono">${esc(rec)}</td>
        <td>${tagEstado(b.resultado)}</td></tr>`;
    })
    .join("")}
  </tbody></table>`;
}

async function render() {
  const view = $("view");
  view.innerHTML = `<p class="note">Cargando…</p>`;
  try {
    const fn = V[state.seccion];
    view.innerHTML = fn ? await fn() : head("Sección", "No disponible.");
    bindView();
  } catch (e) {
    view.innerHTML = head("No se pudo abrir esta sección", esc(e.message)) +
      `<p><button class="btn" type="button" id="reintentar">Reintentar</button></p>`;
    $("reintentar").onclick = () => render();
  }
}

function bindView() {
  $("view").querySelectorAll("[data-go]").forEach((b) => {
    b.onclick = () => {
      state.seccion = b.dataset.go;
      pintarNav();
      render();
    };
  });
}

const V = {};

V.inicio = async () => {
  const p = state.me.perfil;
  const k = await cargarK();
  if (p === "COLAB") {
    const [cons, campanias] = await Promise.all([cargarConsentimientoPropio(), cargarCampanias()]);
    const camp = campanias[0];
    let ya = false;
    if (camp) {
      const est = await apiOpcional(`/encuestas/estado?campania_id=${encodeURIComponent(camp.campania_id)}`);
      ya = Boolean(est?.ya_respondio);
    }
    const seud = cons.participando ? state.me.seudonimo_id || "—" : "—";
    return (
      head(`Hola, ${esc(primerNombre(state.me))}`, "Tu participación es voluntaria y puedes retirarla cuando quieras.") +
      `<div class="privacy"><div class="h">Tus respuestas están seudonimizadas</div>
        <div class="b">Se guardan bajo el identificador <span class="mono">${esc(seud)}</span>, separado de tu expediente.
        Tu líder de turno solo ve promedios de al menos ${esc(k)} personas.</div></div>
      <div class="grid2">
        <div class="card"><h2>Consentimiento</h2><p class="card-sub">Versión ${esc(cons.version_vigente || cons.version_activa || "—")}</p>
          ${tagEstado(cons.participando ? "ACEPTADO" : "REVOCADO")}
          <p class="note">${cons.participando ? "Vigente. Puedes responder las encuestas de la campaña." : "Sin consentimiento vigente no se muestran encuestas."}</p>
          <p style="margin-top:14px"><button class="btn btn-ghost btn-sm" data-go="consentimiento">Ver o cambiar</button></p></div>
        <div class="card"><h2>${esc(camp?.nombre || "Encuesta")}</h2>
          <p class="card-sub">${esc(camp ? `${formatDia(camp.fecha_inicio)} — ${formatDia(camp.fecha_fin)}` : "Sin campaña abierta")}</p>
          ${
            !camp
              ? `<span class="tag tag-off">No disponible</span>`
              : ya
                ? `<span class="tag tag-ok">Enviada</span><p class="note">Gracias por participar. Solo puedes responder una vez por campaña.</p>`
                : `<span class="tag tag-warn">Pendiente</span><p class="note">Toma unos 4 minutos.</p>
                   <p style="margin-top:14px"><button class="btn btn-teal btn-sm" data-go="encuesta">Responder ahora</button></p>`
          }
        </div>
      </div>`
    );
  }
  if (p === "LIDER_TURNO") {
    const [unidades, campanias] = await Promise.all([cargarUnidades(), cargarCampanias()]);
    const htmlCards = await Promise.all(
      unidades.map(async (u) => {
        const camp = campanias[0];
        if (!camp) return "";
        const data = await consultarAgregado(u.unidad_organizacional_id, camp.campania_id);
        const nombres = await nombresReactivos(camp);
        return cardAgregado(u, camp, data, nombres, k);
      })
    );
    return (
      head("Panel de turno", "Resultados agregados de las unidades a tu cargo.") +
      `<div class="privacy"><div class="h">Solo ves promedios de grupo</div>
        <div class="b">No tienes acceso a respuestas individuales ni a la lista de quién participó. Los grupos con menos de ${esc(k)} respuestas se suprimen.</div></div>
      ${tarjetasMetricas([
        [String(unidades.length || 0), "Unidad a tu cargo"],
        [String(k), "Umbral k vigente"],
        ["0", "Respuestas individuales visibles"],
      ])}
      ${htmlCards.join("") || `<div class="card"><p class="note">No hay unidades o campañas visibles.</p></div>`}`
    );
  }
  if (p === "AUDITOR") {
    const bit = await cargarBitacora();
    const insuf = bit.filter((x) => x.resultado === "GRUPO_INSUFICIENTE").length;
    return (
      head("Panel de auditoría", "Trazabilidad de accesos y evidencia de consentimiento.") +
      `<div class="privacy"><div class="h">Acceso a metadatos, no a respuestas</div>
        <div class="b">Puedes verificar quién consultó qué y cuándo, y la evidencia de consentimiento. El contenido de las encuestas no es accesible desde ningún perfil de auditoría.</div></div>
      ${tarjetasMetricas([
        [String(bit.length), "Eventos registrados"],
        [String(insuf), "Consulta suprimida"],
        [String(k), "Umbral k"],
      ])}
      <div class="card"><h2>Eventos recientes</h2><p class="card-sub">Bitácora de auditoría</p>${tablaBitacora(bit)}</div>`
    );
  }
  const cuentas = await cargarCuentas();
  const bit = await cargarBitacora();
  return (
    head("Administración", "Usuarios, catálogos y parámetros del sistema.") +
    tarjetasMetricas([
      [String(cuentas.usuarios.length || 0), "Usuarios activos"],
      [String(cuentas.perfiles.length || 0), "Perfiles"],
      [String(k), "Umbral k vigente"],
    ]) +
    `<div class="card"><h2>Actividad reciente</h2><p class="card-sub">Últimos eventos registrados</p>${tablaBitacora(bit.slice(0, 5))}</div>`
  );
};

V.consentimiento = async () => {
  const c = await cargarConsentimientoPropio();
  const act = Boolean(c.participando);
  return (
    head("Mi consentimiento", "Decides tú, y puedes cambiarlo cuando quieras sin dar explicaciones.") +
    `<div class="card">
      <h2>Estado actual</h2><p class="card-sub">Versión ${esc(c.version_vigente || c.version_activa || "—")}</p>
      ${tagEstado(act ? "ACEPTADO" : "REVOCADO")}
      <p class="note">${
        act
          ? "Mientras esté vigente puedes responder las encuestas de la campaña."
          : "Sin consentimiento vigente no se te mostrarán encuestas. Tus respuestas anteriores no se borran, pero no se recolectan nuevas."
      }</p>
      <p style="margin-top:18px">
        ${
          act
            ? `<button class="btn btn-ghost" type="button" id="btn-revocar">Revocar consentimiento</button>`
            : `<button class="btn btn-teal" type="button" id="btn-aceptar">Otorgar consentimiento</button>`
        }
      </p>
    </div>
    <div class="card"><h2>Historial</h2><p class="card-sub">Revocar no borra los registros anteriores</p>
    <table><thead><tr><th>Versión</th><th>Fecha</th><th>Estado</th></tr></thead><tbody>
    ${(c.historial || [])
      .map(
        (h) =>
          `<tr><td class="mono">${esc(h.version_consentimiento_id)}</td><td class="mono">${esc(formatFecha(h.fecha_aceptacion))}</td><td>${tagEstado(h.estado)}</td></tr>`
      )
      .join("") || `<tr><td colspan="3">Sin historial.</td></tr>`}
    </tbody></table></div>`
  );
};

V.encuesta = async () => {
  const [cons, campanias] = await Promise.all([cargarConsentimientoPropio(), cargarCampanias()]);
  if (!cons.participando) {
    return (
      head("Responder encuesta", "") +
      `<div class="privacy blocked"><div class="h">Necesitas consentimiento vigente</div>
      <div class="b">La encuesta no se muestra porque tu consentimiento está revocado. Puedes otorgarlo de nuevo cuando quieras.</div></div>
      <button class="btn" data-go="consentimiento">Ir a mi consentimiento</button>`
    );
  }
  const campania = campanias[0];
  if (!campania) {
    return head("Responder encuesta", "Por ahora no hay evaluaciones abiertas para su equipo.") +
      `<div class="suppressed"><div class="big">Sin campaña activa</div><div class="small">Cuando haya una evaluación abierta, aparecerá aquí.</div></div>`;
  }
  const est = await apiOpcional(`/encuestas/estado?campania_id=${encodeURIComponent(campania.campania_id)}`);
  if (est?.ya_respondio) {
    return (
      head("Responder encuesta", "") +
      `<div class="privacy"><div class="h">Ya respondiste esta campaña</div>
      <div class="b">Cada persona responde una sola vez por campaña. Tus respuestas se guardaron bajo tu seudónimo.</div></div>`
    );
  }
  const r = await api(
    `/catalogos/instrumentos/${encodeURIComponent(campania.instrumento_id)}/versiones/${Number(campania.version_instrumento)}/reactivos`
  );
  const preguntas = asList(r);
  return (
    head(esc(campania.nombre), "Responde con honestidad. Nadie puede vincular estas respuestas contigo.") +
    `<div class="privacy"><div class="h">Se guardará como ${esc(state.me.seudonimo_id || "seudónimo")}</div>
      <div class="b">Tu nombre y tu número de empleado no se envían junto con las respuestas.</div></div>
    <div class="card"><form id="f-enc">
    ${preguntas
      .map(
        (item, i) => `<div class="q"><div class="qt">${i + 1}. ${esc(item.texto)}</div>
        <div class="qd">Dimensión: ${esc(item.dimension || "—")}</div>
        <div class="scale">${ESCALA.map(
          (t, j) =>
            `<label><input type="radio" name="${esc(item.reactivo_id)}" value="${j + 1}" required><span>${t}</span></label>`
        ).join("")}</div></div>`
      )
      .join("")}
    <p style="margin-top:20px"><button class="btn btn-teal" type="submit">Enviar respuestas</button></p>
    </form></div>`
  );
};

V.misAccesos = async () => {
  const data = await apiOpcional("/encuestas/mis-accesos");
  const filas = asList(data);
  return (
    head("Quién vio mis datos", "Registro de cada consulta relacionada con tu información.") +
    `<div class="privacy"><div class="h">Transparencia verificable</div>
     <div class="b">Esta lista no es una promesa del aviso de privacidad: es la bitácora real del sistema.</div></div>
    <div class="card">${tablaBitacora(filas)}</div>`
  );
};

V.agregados = async () => {
  const [unidades, campanias, k] = await Promise.all([cargarUnidades(), cargarCampanias(), cargarK()]);
  const html = [];
  html.push(
    head("Resultados por unidad", "Un resultado solo se muestra si el grupo alcanza el umbral mínimo.") +
      `<div class="toolbar"><span class="note right" style="margin:0">Umbral vigente: k = ${esc(k)}</span></div>`
  );
  if (!unidades.length || !campanias.length) {
    html.push(`<div class="card"><p class="note">No hay equipos o evaluaciones visibles para su perfil.</p></div>`);
    return html.join("");
  }
  for (const u of unidades) {
    for (const c of campanias) {
      const data = await consultarAgregado(u.unidad_organizacional_id, c.campania_id);
      const nombres = await nombresReactivos(c);
      html.push(cardAgregado(u, c, data, nombres, k));
    }
  }
  return html.join("");
};

V.reportes = async () => {
  const [unidades, campanias, k] = await Promise.all([cargarUnidades(), cargarCampanias(), cargarK()]);
  const visible = [];
  const participacion = [];
  for (const u of unidades) {
    const c = campanias[0];
    if (!c) continue;
    const data = await consultarAgregado(u.unidad_organizacional_id, c.campania_id);
    participacion.push({ nombre: u.nombre, n: data?.visible ? data.total_respuestas : 0, visible: Boolean(data?.visible), data, campania: c, unidad: u });
    if (data?.visible) visible.push({ unidad: u, campania: c, data });
  }
  setTimeout(() => {
    const primero = visible[0];
    if (primero) {
      const det = Object.entries(primero.data.detalle || {});
      dibujarColumnas(
        "g1",
        det.map(([id]) => id),
        det.map(([, v]) => Number(v))
      );
    }
    if (typeof Highcharts !== "undefined" && $("g2")) {
      Highcharts.chart("g2", {
        credits: { enabled: false },
        title: { text: null },
        chart: { type: "bar", height: 300, style: { fontFamily: "Inter,sans-serif" }, backgroundColor: "transparent" },
        xAxis: { categories: participacion.map((x) => x.nombre), lineColor: "#DCE1E8" },
        yAxis: {
          min: 0,
          title: { text: "Respuestas" },
          gridLineColor: "#EDEFF3",
          plotLines: [{ value: k, color: "#8A5A00", width: 2, dashStyle: "Dash", label: { text: "umbral k=" + k, style: { color: "#8A5A00", fontSize: "11px" } } }],
        },
        legend: { enabled: false },
        series: [{ name: "Respuestas", data: participacion.map((x) => x.n), color: "#0F6B62", borderRadius: 3 }],
      });
    }
  }, 40);
  return (
    head("Reportes", "Visualización de resultados agregados. Solo se grafican grupos que superan el umbral.") +
    `<div class="grid2">
      <div class="card"><h2>Bienestar por dimensión</h2><p class="card-sub">Escala 1–5 · grupos que superan k</p><div id="g1" class="chart"></div></div>
      <div class="card"><h2>Participación por unidad</h2><p class="card-sub">Respuestas recibidas vs. umbral k=${esc(k)}</p><div id="g2" class="chart"></div></div>
    </div>
    <p class="note">Las gráficas se generan con Highcharts. Las unidades que no alcanzan el umbral mínimo no exponen promedios.</p>`
  );
};

V.instrumentos = async () => {
  const instrumentos = await cargarInstrumentos();
  const campanias = await cargarCampanias();
  let reactivosHtml = "";
  const nom035 = campanias.find((c) => c.instrumento_id) || campanias[0];
  if (nom035) {
    const r = await apiOpcional(
      `/catalogos/instrumentos/${encodeURIComponent(nom035.instrumento_id)}/versiones/${Number(nom035.version_instrumento)}/reactivos`
    );
    const preguntas = asList(r);
    reactivosHtml = `<div class="card"><h2>Reactivos de ${esc(nom035.nombre)}</h2>
      <p class="card-sub">Versión ${esc(nom035.version_instrumento)}</p>
      <table><thead><tr><th>Clave</th><th>Texto</th><th>Dimensión</th></tr></thead><tbody>
      ${preguntas.map((x) => `<tr><td class="mono">${esc(x.reactivo_id)}</td><td>${esc(x.texto)}</td><td>${esc(x.dimension || "—")}</td></tr>`).join("")}
      </tbody></table></div>`;
  }
  return (
    head("Instrumentos", "Cuestionarios disponibles y sus versiones.") +
    `<div class="card"><table><thead><tr><th>Clave</th><th>Nombre</th><th>Tipo</th><th>Estado</th></tr></thead><tbody>
    ${instrumentos
      .map(
        (i) =>
          `<tr><td class="mono">${esc(i.instrumento_id)}</td><td>${esc(i.nombre)}</td><td>${esc(i.tipo)}</td>
           <td>${tagEstado(i.activo === false ? "Inactivo" : "Activo")}</td></tr>`
      )
      .join("")}
    </tbody></table></div>${reactivosHtml}`
  );
};

V.unidades = async () => {
  const [unidades, campanias] = await Promise.all([cargarUnidades(), cargarCampanias()]);
  return (
    head("Unidades organizacionales", "Áreas y turnos. El tamaño del grupo alimenta la verificación del umbral.") +
    `<div class="card"><table><thead><tr><th>Clave</th><th>Nombre</th><th>Nivel</th></tr></thead><tbody>
    ${unidades
      .map(
        (u) =>
          `<tr><td class="mono">${esc(u.unidad_organizacional_id)}</td><td>${esc(u.nombre)}</td>
           <td class="mono">${esc(u.nivel_jerarquico ?? "—")}</td></tr>`
      )
      .join("")}
    </tbody></table>
    <p class="note">Una unidad con colaboradores activos no puede eliminarse, solo inactivarse.</p></div>
    <div class="card"><h2>Campañas</h2><p class="card-sub">Aplicaciones de un instrumento a una o varias unidades.</p>
    <table><thead><tr><th>Clave</th><th>Nombre</th><th>Periodo</th></tr></thead><tbody>
    ${campanias
      .map(
        (c) =>
          `<tr><td class="mono">${esc(c.campania_id)}</td><td>${esc(c.nombre)}</td>
           <td class="mono">${esc(formatDia(c.fecha_inicio))} → ${esc(formatDia(c.fecha_fin))}</td></tr>`
      )
      .join("")}
    </tbody></table></div>`
  );
};

V.usuarios = async () => {
  const data = await cargarCuentas();
  return (
    head("Usuarios y perfiles", "Un usuario tiene un perfil principal que define su menú y sus permisos.") +
    `<div class="card"><h2>Perfiles</h2><p class="card-sub">Nivel de acceso institucional</p>
    <table><thead><tr><th>Perfil</th><th>Nivel</th></tr></thead><tbody>
    ${(data.perfiles || []).map((p) => `<tr><td>${esc(p.nombre)}</td><td class="mono">${esc(p.nivel_acceso)}</td></tr>`).join("")}
    </tbody></table></div>
    <div class="card"><h2>Cuentas</h2>
    <table><thead><tr><th>Clave</th><th>Correo</th><th>Perfil</th><th>Estado</th></tr></thead><tbody>
    ${(data.usuarios || [])
      .map(
        (u) =>
          `<tr><td class="mono">${esc(u.usuario_id)}</td><td class="mono">${esc(u.correo)}</td>
           <td>${esc(u.perfil_nombre || PERFIL_ETIQUETA[u.perfil] || u.perfil)}</td>
           <td>${tagEstado(u.activo ? "Activo" : "Inactivo")}</td></tr>`
      )
      .join("")}
    </tbody></table><p class="note">Cada cambio de perfil se registra en la bitácora de auditoría.</p></div>`
  );
};

V.parametros = async () => {
  const cfg = await cargarConfiguracion();
  return (
    head("Parámetros del sistema", "Configuración que afecta a toda la plataforma.") +
    `<div class="privacy"><div class="h">El umbral k protege a los grupos pequeños</div>
     <div class="b">Ningún resultado agregado se muestra si el grupo tiene menos de k respuestas. Bajarlo aumenta el riesgo de reidentificación.</div></div>
    <div class="card"><h2>Umbral mínimo de grupo</h2><p class="card-sub">Clave <span class="mono">k</span> en parametro_global</p>
    <form id="fk" class="toolbar">
      <input id="kIn" name="k" type="number" min="2" max="50" value="${esc(cfg.k)}" style="width:110px">
      <button class="btn btn-sm" type="submit">Guardar cambio</button>
    </form>
    <p class="note">Valor actual: ${esc(cfg.k)}. Al guardar se registra un evento <span class="mono">CAMBIO_UMBRAL_K</span> en la bitácora.</p></div>
    <div class="card"><h2>Versión activa del consentimiento</h2><p class="card-sub">Documento que firman los colaboradores</p>
    <form id="fver">
      <select id="ver" name="version">${(cfg.versiones || [])
        .map(
          (v) =>
            `<option value="${esc(v.version_consentimiento_id)}" ${
              v.version_consentimiento_id === cfg.version_activa_consentimiento ? "selected" : ""
            }>${esc(v.version_consentimiento_id)}</option>`
        )
        .join("")}</select>
      <p style="margin-top:14px"><button class="btn btn-sm" type="submit">Guardar aviso activo</button></p>
    </form>
    <p class="mono" style="margin-top:12px">${esc(cfg.version_activa_consentimiento || "—")}</p></div>`
  );
};

V.bitacora = async () => {
  const filas = await cargarBitacora();
  const acciones = [...new Set(filas.map((b) => b.accion).filter(Boolean))];
  return (
    head("Bitácora de auditoría", "Cada acceso a información personal o agregada queda registrado.") +
    `<div class="toolbar">
      <select id="fAcc"><option value="">Todas las acciones</option>
        ${acciones.map((a) => `<option value="${esc(a)}">${esc(a)}</option>`).join("")}</select>
    </div><div class="card" id="tbl-bit">${tablaBitacora(filas)}</div>`
  );
};

V.consentimientos = async () => {
  const lista = asList(await apiOpcional("/auditoria/consentimientos"));
  return (
    head("Evidencia de consentimiento", "Quién consintió, cuándo y bajo qué versión del aviso.") +
    `<div class="privacy"><div class="h">Solo metadatos</div>
     <div class="b">Se muestra la evidencia del otorgamiento, nunca el contenido de las respuestas asociadas al seudónimo.</div></div>
    <div class="card">
      <form id="f-cons" class="toolbar">
        <input id="codigo" name="codigo" placeholder="Consultar un seudónimo" autocomplete="off">
        <button class="btn btn-sm" type="submit">Consultar</button>
      </form>
      <div id="out-cons">
        <table><thead><tr><th>Seudónimo</th><th>Versión</th><th>Fecha</th><th>Estado</th></tr></thead><tbody>
        ${
          lista.length
            ? lista
                .map(
                  (r) =>
                    `<tr><td class="mono">${esc(r.seudonimo_id)}</td><td class="mono">${esc(r.version_consentimiento_id)}</td>
                     <td class="mono">${esc(formatFecha(r.fecha_aceptacion))}</td><td>${tagEstado(r.estado)}</td></tr>`
                )
                .join("")
            : `<tr><td colspan="4">No hay registros para mostrar.</td></tr>`
        }
        </tbody></table>
        <p class="note">El registro revocado se conserva: revocar no elimina la evidencia histórica.</p>
      </div>
    </div>`
  );
};

V.notificaciones = async () => {
  const list = await notificacionesPerfil();
  const leidas = notifLeidas();
  const n = noLeidas(list);
  return (
    head("Notificaciones", "Avisos del sistema relacionados con tu perfil.") +
    `<div class="toolbar"><span class="note" style="margin:0">${n} sin leer</span>
     ${n ? `<button class="btn btn-ghost btn-sm right" type="button" id="btn-leidas">Marcar todas como leídas</button>` : ""}</div>
    <div class="card">${
      list.length
        ? list
            .map((item) => {
              const read = Boolean(leidas[claveNotif(item)]);
              return `<div class="notif ${read ? "read" : ""}"><div class="dot"></div>
                <div class="body"><div class="t">${esc(item.t)}</div><div class="m">${esc(item.m)}</div><div class="f">${esc(item.f)}</div></div></div>`;
            })
            .join("")
        : `<div class="suppressed"><div class="big">Sin notificaciones</div><div class="small">Cuando haya algo que avisarte, aparecerá aquí.</div></div>`
    }</div>`
  );
};

$("view").addEventListener("submit", async (ev) => {
  if (ev.target.id === "f-enc") {
    ev.preventDefault();
    try {
      const campanias = await cargarCampanias();
      const campania = campanias[0];
      const respuestas = [...ev.target.querySelectorAll("input[type=radio]:checked")].map((i) => ({
        reactivo_id: i.name,
        valor: Number(i.value),
      }));
      await api("/encuestas/respuestas", {
        method: "POST",
        body: JSON.stringify({
          seudonimo_id: state.me.seudonimo_id,
          campania_id: campania.campania_id,
          respuestas,
        }),
      });
      toast("Respuestas enviadas");
      state.seccion = "inicio";
      pintarNav();
      await render();
    } catch (e) {
      toast(e.message);
    }
  }
  if (ev.target.id === "fk") {
    ev.preventDefault();
    try {
      const body = { k: Number($("kIn").value) };
      try {
        await api("/agregados/parametros", { method: "PATCH", body: JSON.stringify(body) });
      } catch {
        await api("/agregados/parametros/k", { method: "PATCH", body: JSON.stringify(body) });
      }
      toast("Umbral actualizado a k = " + body.k);
      await render();
    } catch (e) {
      toast(e.message);
    }
  }
  if (ev.target.id === "fver") {
    ev.preventDefault();
    try {
      const body = { version_activa_consentimiento: $("ver").value };
      try {
        await api("/agregados/parametros", { method: "PATCH", body: JSON.stringify(body) });
      } catch {
        await api("/portal/configuracion", { method: "PATCH", body: JSON.stringify(body) });
      }
      toast("Aviso activo actualizado");
      await render();
    } catch (e) {
      toast(e.message);
    }
  }
  if (ev.target.id === "f-cons") {
    ev.preventDefault();
    const caja = $("out-cons");
    const id = String(new FormData(ev.target).get("codigo") || "").trim();
    if (!id) return;
    caja.innerHTML = `<p class="note">Consultando…</p>`;
    try {
      const data = await api(`/auditoria/consentimientos/${encodeURIComponent(id)}`);
      const filas = asList(data);
      if (!filas.length) {
        caja.innerHTML = `<div class="suppressed"><div class="big">Sin registros</div><div class="small">No hay evidencia para este seudónimo.</div></div>`;
        return;
      }
      caja.innerHTML = `<table><thead><tr><th>Seudónimo</th><th>Versión</th><th>Fecha</th><th>Estado</th></tr></thead><tbody>
        ${filas
          .map(
            (f) =>
              `<tr><td class="mono">${esc(f.seudonimo_id || id)}</td><td class="mono">${esc(f.version_consentimiento_id)}</td>
               <td class="mono">${esc(formatFecha(f.fecha_aceptacion))}</td><td>${tagEstado(f.estado)}</td></tr>`
          )
          .join("")}</tbody></table>`;
    } catch (e) {
      caja.innerHTML = `<p class="note">${esc(e.message)}</p>`;
    }
  }
});

$("view").addEventListener("click", async (ev) => {
  const t = ev.target;
  if (!(t instanceof HTMLElement)) return;
  if (t.id === "btn-revocar") {
    if (!confirm("¿Revocar tu consentimiento? Dejarás de recibir encuestas. Tus respuestas anteriores no se eliminan.")) return;
    try {
      await guardarConsentimientoPropio(false);
      toast("Consentimiento revocado");
      await render();
    } catch (e) {
      toast(e.message);
    }
  }
  if (t.id === "btn-aceptar") {
    try {
      await guardarConsentimientoPropio(true);
      toast("Consentimiento otorgado");
      await render();
    } catch (e) {
      toast(e.message);
    }
  }
  if (t.id === "btn-leidas") {
    const list = await notificacionesPerfil();
    const mapa = notifLeidas();
    list.forEach((n) => {
      mapa[claveNotif(n)] = true;
    });
    guardarNotifLeidas(mapa);
    toast("Notificaciones marcadas como leídas");
    pintarNav();
    await render();
  }
});

$("view").addEventListener("change", (ev) => {
  if (ev.target.id === "fAcc") {
    const acc = ev.target.value;
    cargarBitacora().then((filas) => {
      const rows = acc ? filas.filter((b) => b.accion === acc) : filas;
      $("tbl-bit").innerHTML = tablaBitacora(rows);
    });
  }
});

function wirePublico() {
  document.querySelectorAll('a[href="#login"]').forEach((a) => {
    a.addEventListener("click", (e) => {
      e.preventDefault();
      irLogin();
    });
  });
  $("link-publico").onclick = (e) => {
    e.preventDefault();
    irPublico();
  };
  $("link-recuperar").onclick = (e) => {
    e.preventDefault();
    $("loginBox").hidden = true;
    $("recuperar").hidden = false;
  };
  $("link-volver-login").onclick = (e) => {
    e.preventDefault();
    $("loginBox").hidden = false;
    $("recuperar").hidden = true;
  };
  $("btn-recuperar").onclick = () => {
    const m = $("rmail").value.trim();
    if (!m || !m.includes("@")) {
      toast("Escribe un correo válido");
      return;
    }
    $("loginBox").hidden = false;
    $("recuperar").hidden = true;
    toast("Si el correo existe, enviamos un enlace de recuperación");
  };
}

$("form-login").onsubmit = async (ev) => {
  ev.preventDefault();
  errorLogin("");
  const correo = String($("correo").value || "").trim();
  const contrasena = String($("contrasena").value || "");
  if (!correo || !contrasena) {
    errorLogin("Ingrese su correo y contraseña.");
    return;
  }
  try {
    const vivo = await hayApi();
    if (!vivo) {
      const out = sesionDemo(correo, contrasena);
      if (!out) {
        errorLogin(
          "En este sitio no hay servidor. Usa demo123 y una cuenta de la lista, o abre la app con Docker en local."
        );
        return;
      }
      state.demo = true;
      state.token = out.token;
      sessionStorage.setItem(TOKEN_KEY, out.token);
      sessionStorage.setItem("nexum_demo_correo", correo);
      await entrar(out);
      toast("Recorrido local: las encuestas reales requieren Docker.");
      return;
    }
    state.demo = false;
    const out = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({ correo, contrasena }),
    });
    state.token = out.token;
    sessionStorage.setItem(TOKEN_KEY, out.token);
    out.correo = correo;
    await entrar(out);
  } catch (e) {
    errorLogin(e.message);
  }
};

$("btn-salir").onclick = async () => {
  if (!confirm("¿Cerrar tu sesión?")) return;
  try {
    await api("/auth/logout", { method: "POST" });
  } catch (_) {}
  state.token = null;
  state.me = null;
  state.demo = false;
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem("nexum_demo_correo");
  irPublico();
  toast("Sesión cerrada");
};

wirePublico();

hayApi().then((vivo) => {
  const aviso = $("aviso-sitio");
  if (aviso && !vivo) {
    aviso.hidden = false;
    aviso.innerHTML =
      "<strong>Este sitio no ejecuta el servidor.</strong> Entra con <strong>demo123</strong> para recorrer las pantallas. Datos reales: Docker en tu máquina.";
  }
});

if (location.hash === "#login" && !state.token) irLogin();

if (state.token === "demo") {
  const out = sesionDemo(sessionStorage.getItem("nexum_demo_correo"), "demo123");
  if (out) {
    state.demo = true;
    entrar(out);
  } else {
    state.token = null;
    state.demo = false;
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem("nexum_demo_correo");
    irPublico();
  }
} else if (state.token) {
  api("/auth/me")
    .then(entrar)
    .catch(() => {
      state.token = null;
      sessionStorage.removeItem(TOKEN_KEY);
      irPublico();
    });
}
