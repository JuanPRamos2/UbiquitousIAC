const API = "";
const json = (path) => `${API}${path}${path.includes("?") ? "&" : "?"}format=json`;

const noticeEl = document.getElementById("notice");
const authPanel = document.getElementById("auth-panel");
const sessionPanel = document.getElementById("session-panel");
const sessionUser = document.getElementById("session-user");
const sessionTimer = document.getElementById("session-timer");

function showNotice(message, warn) {
  noticeEl.textContent = message;
  noticeEl.classList.toggle("hidden", !message);
  noticeEl.classList.toggle("warn", Boolean(warn));
}

async function api(path, options) {
  const response = await fetch(json(path), {
    credentials: "include",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    ...options,
  });
  const data = await response.json();
  return { response, data };
}

async function loadCaptcha() {
  const { data } = await api("/captcha");
  document.getElementById("captcha-question").textContent = data.question || "Captcha";
  document.getElementById("captcha-id").value = data.captchaId;
  document.getElementById("captcha-answer").value = "";
}

function renderSession(data) {
  const session = data.session || {};
  const user = data.user;
  if (session.notification && session.notification.message) {
    showNotice(session.notification.message, session.notification.requiresAction);
  } else if (data.message) {
    showNotice(data.message, false);
  }
  if (session.authenticated || session.canExtend) {
    authPanel.classList.add("hidden");
    sessionPanel.classList.remove("hidden");
    sessionUser.textContent = user
      ? `${user.full_name} · ${user.email} · ${user.role} · correo ${user.emailVerified ? "verificado" : "pendiente"}`
      : "Sesión presente";
    sessionTimer.textContent = session.authenticated
      ? `Restan ${session.remainingSeconds}s de ${session.idleTimeoutMinutes} minutos.`
      : "La sesión expiró. Extiéndala ahora o se cerrará.";
    return;
  }
  sessionPanel.classList.add("hidden");
  authPanel.classList.remove("hidden");
}

async function refreshSession() {
  const { data } = await api("/session");
  renderSession(data);
}

document.getElementById("login-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const { data } = await api("/login", {
    method: "POST",
    body: JSON.stringify({
      email: document.getElementById("login-email").value,
      password: document.getElementById("login-password").value,
    }),
  });
  if (!data.ok) {
    showNotice((data.errors || ["No se pudo iniciar sesión"]).join(" "), true);
    return;
  }
  renderSession(data);
});

document.getElementById("register-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const { data } = await api("/register", {
    method: "POST",
    body: JSON.stringify({
      nombre: document.getElementById("nombre").value,
      apellidoPaterno: document.getElementById("paterno").value,
      apellidoMaterno: document.getElementById("materno").value,
      email: document.getElementById("reg-email").value,
      password: document.getElementById("reg-password").value,
      captchaId: document.getElementById("captcha-id").value,
      captchaAnswer: document.getElementById("captcha-answer").value,
    }),
  });
  if (!data.ok) {
    showNotice((data.errors || ["No se pudo registrar"]).join(" "), true);
    await loadCaptcha();
    return;
  }
  const notice = data.notification || {};
  const verifyHref =
    (notice.body && notice.body.verifyUrl) ||
    (data._links && data._links.verify && data._links.verify.href);
  showNotice(
    (notice.message || "El usuario existe.") +
      (verifyHref ? " JSON verify: " + verifyHref : ""),
    false
  );
  await loadCaptcha();
});

document.getElementById("reload-captcha").addEventListener("click", (event) => {
  event.preventDefault();
  loadCaptcha();
});

document.getElementById("extend-btn").addEventListener("click", async () => {
  const { data } = await api("/session", { method: "POST" });
  renderSession(data);
});

document.getElementById("logout-btn").addEventListener("click", async () => {
  const { data } = await api("/logout", { method: "POST" });
  renderSession(data);
  showNotice(data.message || "Sesión cerrada", false);
});

loadCaptcha();
refreshSession();
setInterval(refreshSession, 10000);
