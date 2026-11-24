const archData = {
    nodes: [
        { id: "python", type: "client", x: 16, y: 28, name: "Python_app", tech: "una sola URL", desc: "Deja de guardar seis puertos. El Bearer va en lo que está protegido." },
        { id: "electron", type: "client", x: 16, y: 132, name: "Electron_app", tech: "XML /books", desc: "Sigue pidiendo el catálogo en XML. Cambia la dirección, no el formato." },
        { id: "java", type: "client", x: 16, y: 236, name: "Java SOAP", tech: "POST /soap", desc: "Entra por la misma puerta. Las estadísticas siguen con WS-Security, sin JWT." },
        { id: "browser", type: "client", x: 16, y: 340, name: "Navegador", tech: "login y UI", desc: "Swagger y la pantalla de login usan el mismo HTTPS." },

        { id: "lb", type: "edge", x: 210, y: 168, name: "Cloud LB", tech: "HTTPS :443", desc: "Balanceador de Google. Termina TLS y revisa el /health de Nginx. No valida el JWT." },
        { id: "nginx", type: "proxy", x: 400, y: 168, name: "Nginx", tech: "proxy y reglas", desc: "Reenvía a 127.0.0.1, cierra /metrics, limita el login y reparte Books con least_conn." },

        { id: "login", type: "service", x: 620, y: 36, name: "Login :5000", tech: "emite el JWT", desc: "Único que firma el token. Guarda sesión y refresh en Redis. 20 minutos." },
        { id: "users", type: "service", x: 790, y: 36, name: "Users :5002", tech: "loopback", desc: "Sigue revisando el Bearer, el rol y el cambio de contraseña." },
        { id: "authors", type: "service", x: 960, y: 36, name: "Authors :5003", tech: "loopback", desc: "El GET es público. Escribir pide un administrador." },
        { id: "pedidos", type: "service", x: 620, y: 150, name: "Pedidos :5004", tech: "una instancia", desc: "Descuenta el stock en PostgreSQL. No hay una segunda copia." },
        { id: "pagos", type: "service", x: 790, y: 150, name: "Pagos :5005", tech: "una instancia", desc: "Marca la orden como pagada en la base. No llama a Pedidos por HTTP." },
        { id: "node", type: "legacy", x: 960, y: 150, name: "Node :3000", tech: "puerto cerrado", desc: "Sigue en la VM y habla directo con PostgreSQL. El 3000 ya no se publica." },

        { id: "booksa", type: "books", x: 620, y: 360, name: "Books A :5001", tech: "least_conn", desc: "Catálogo y SOAP. Con SOAP_DEMO apagado lee la misma base que B y C." },
        { id: "booksb", type: "books", x: 790, y: 360, name: "Books B :5101", tech: "réplica propuesta", desc: "Puerto nuevo. Comparte PostgreSQL y la caché de Redis." },
        { id: "booksc", type: "books", x: 960, y: 360, name: "Books C :5102", tech: "réplica propuesta", desc: "Si A deja de aceptar conexiones, el catálogo sigue en B o en C." },

        { id: "postgres", type: "database", x: 1188, y: 110, name: "PostgreSQL", tech: "library_db", desc: "Una sola base para los seis servicios y el monolito. El balanceador no la duplica." },
        { id: "redis", type: "cache", x: 1188, y: 340, name: "Redis", tech: "sesión y caché", desc: "session, refresh, jwt:revoked y la caché de 30 segundos del catálogo." }
    ],
    connections: [
        { from: "python", to: "lb", type: "https" },
        { from: "electron", to: "lb", type: "https" },
        { from: "java", to: "lb", type: "https" },
        { from: "browser", to: "lb", type: "https" },
        { from: "lb", to: "nginx", type: "http" },
        { from: "nginx", to: "login", type: "proxy" },
        { from: "nginx", to: "users", type: "proxy" },
        { from: "nginx", to: "authors", type: "proxy" },
        { from: "nginx", to: "pedidos", type: "proxy" },
        { from: "nginx", to: "pagos", type: "proxy" },
        { from: "nginx", to: "booksa", type: "proxy" },
        { from: "nginx", to: "booksb", type: "proxy" },
        { from: "nginx", to: "booksc", type: "proxy" },
        { from: "login", to: "postgres", type: "sql" },
        { from: "login", to: "redis", type: "jwt" },
        { from: "pedidos", to: "postgres", type: "sql" },
        { from: "pagos", to: "postgres", type: "sql" },
        { from: "booksa", to: "redis", type: "jwt" },
        { from: "node", to: "postgres", type: "direct" }
    ]
};

const svgNodes = document.getElementById("layer-nodes");
const svgConns = document.getElementById("layer-connections");
const svgBgs = document.getElementById("layer-backgrounds");
const svgPackets = document.getElementById("layer-packets");
const tooltip = document.getElementById("tooltip");
const learnPanel = document.getElementById("learning-panel");

const NODE_W = 148;
const NODE_H = 58;
const nodeElements = {};
const config = { currentScene: 0 };
const bookLoad = { booksa: 0, booksb: 0, booksc: 0 };
const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
let trafficTimer = null;
const LAST_SCENE = 8;

function initArchitecture() {
    addRect(svgBgs, { x: 590, y: 12, width: 548, height: 430, className: "vm-box" });
    addLabel(svgBgs, 864, 34, "VM · FLASK EN 127.0.0.1", "vm-label");
    addRect(svgBgs, { x: 604, y: 330, width: 520, height: 100, className: "books-box" });
    addLabel(svgBgs, 864, 350, "BOOKS · LEAST CONNECTIONS", "books-label");

    archData.connections.forEach((conn) => {
        const from = nodeById(conn.from);
        const to = nodeById(conn.to);
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        const x1 = from.x + NODE_W;
        const y1 = from.y + NODE_H / 2;
        const x2 = to.x;
        const y2 = to.y + NODE_H / 2;
        const bend = Math.max(40, Math.abs(x2 - x1) * 0.35);
        path.setAttribute("d", `M ${x1} ${y1} C ${x1 + bend} ${y1}, ${x2 - bend} ${y2}, ${x2} ${y2}`);
        path.setAttribute("class", `connection conn-${conn.type}`);
        path.id = `conn-${conn.from}-${conn.to}`;
        path.dataset.from = conn.from;
        path.dataset.to = conn.to;
        svgConns.appendChild(path);
    });

    archData.nodes.forEach((node) => {
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("transform", `translate(${node.x}, ${node.y})`);
        g.id = `node-${node.id}`;

        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("width", NODE_W);
        rect.setAttribute("height", NODE_H);
        rect.setAttribute("rx", "12");
        rect.setAttribute("class", `node-rect node-${node.type}`);

        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", NODE_W / 2);
        text.setAttribute("y", NODE_H / 2 - 2);
        text.setAttribute("class", "node-text");
        text.textContent = node.name;

        const sub = document.createElementNS("http://www.w3.org/2000/svg", "text");
        sub.setAttribute("x", NODE_W / 2);
        sub.setAttribute("y", NODE_H / 2 + 16);
        sub.setAttribute("class", "node-subtext");
        sub.textContent = node.tech;

        g.append(rect, text, sub);
        svgNodes.appendChild(g);
        nodeElements[node.id] = g;
        g.addEventListener("mouseenter", (event) => showTooltip(event, node));
        g.addEventListener("mouseleave", hideTooltip);
        g.addEventListener("click", () => bounceNode(node.id));
    });
}

function addRect(parent, box) {
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", box.x);
    rect.setAttribute("y", box.y);
    rect.setAttribute("width", box.width);
    rect.setAttribute("height", box.height);
    rect.setAttribute("class", box.className);
    parent.appendChild(rect);
}

function addLabel(parent, x, y, text, className) {
    const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
    label.setAttribute("x", x);
    label.setAttribute("y", y);
    label.setAttribute("text-anchor", "middle");
    label.setAttribute("class", className);
    label.textContent = text;
    parent.appendChild(label);
}

function nodeById(id) {
    return archData.nodes.find((node) => node.id === id);
}

function showTooltip(event, node) {
    tooltip.innerHTML = `<h4>${node.name}</h4><p>${node.desc}</p>`;
    tooltip.style.left = `${event.clientX + 16}px`;
    tooltip.style.top = `${event.clientY + 16}px`;
    tooltip.classList.remove("hidden");
}

function hideTooltip() {
    tooltip.classList.add("hidden");
}

function bounceNode(id) {
    const rect = document.querySelector(`#node-${id} .node-rect`);
    if (!rect) return;
    gsap.fromTo(rect,
        { scale: 0.96, transformOrigin: "center center" },
        { scale: 1, duration: reduceMotion ? 0.01 : 0.28, ease: "power1.out", transformOrigin: "center center" }
    );
}

function sendPacket(fromId, toId, label, color, duration, onComplete) {
    const from = nodeById(fromId);
    const to = nodeById(toId);
    if (!from || !to) {
        if (onComplete) onComplete();
        return;
    }
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    const width = Math.max(54, label.length * 7 + 16);
    rect.setAttribute("width", width);
    rect.setAttribute("height", 22);
    rect.setAttribute("rx", 11);
    rect.setAttribute("fill", color);
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", width / 2);
    text.setAttribute("y", 15);
    text.setAttribute("fill", "#fff");
    text.setAttribute("font-size", "11px");
    text.setAttribute("font-family", "sans-serif");
    text.setAttribute("font-weight", "700");
    text.setAttribute("text-anchor", "middle");
    text.textContent = label;
    g.append(rect, text);
    svgPackets.appendChild(g);
    gsap.set(g, { x: from.x + NODE_W / 2 - width / 2, y: from.y + NODE_H / 2 - 11 });
    gsap.to(g, {
        x: to.x + NODE_W / 2 - width / 2,
        y: to.y + NODE_H / 2 - 11,
        duration: reduceMotion ? 0.05 : duration,
        ease: "power1.inOut",
        onStart: () => bounceNode(fromId),
        onComplete: () => {
            bounceNode(toId);
            gsap.to(g, {
                y: "-=16",
                opacity: 0,
                duration: reduceMotion ? 0.01 : 0.25,
                onComplete: () => g.remove()
            });
            if (onComplete) onComplete();
        }
    });
}

function runPath(steps, done) {
    const go = (index) => {
        if (index >= steps.length) {
            if (done) done();
            return;
        }
        const step = steps[index];
        sendPacket(step.from, step.to, step.label, step.color, step.duration || 0.65, () => go(index + 1));
    };
    go(0);
}

function door(from, to, label, color) {
    return [
        { from, to: "lb", label: "HTTPS", color: "var(--https-color)", duration: 0.55 },
        { from: "lb", to: "nginx", label: label, color, duration: 0.5 },
        { from: "nginx", to, label, color, duration: 0.6 }
    ];
}

function back(from, to, label, color) {
    return [
        { from, to: "nginx", label, color, duration: 0.5 },
        { from: "nginx", to: "lb", label, color, duration: 0.45 },
        { from: "lb", to, label, color, duration: 0.5 }
    ];
}

function leastBooks() {
    return Object.entries(bookLoad).sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0]))[0][0];
}

function resetOpacities() {
    gsap.to(".node-rect, .node-text, .node-subtext, .connection", { opacity: 1, duration: 0.35 });
    markDown("pedidos", false);
}

function dimAllExcept(ids) {
    const keep = new Set(ids);
    gsap.to(".node-rect, .node-text, .node-subtext", { opacity: 0.16, duration: 0.35 });
    document.querySelectorAll(".connection").forEach((path) => {
        const visible = keep.has(path.dataset.from) && keep.has(path.dataset.to);
        gsap.to(path, { opacity: visible ? 0.9 : 0.05, duration: 0.35 });
    });
    ids.forEach((id) => {
        gsap.to(`#node-${id} .node-rect, #node-${id} .node-text, #node-${id} .node-subtext`, { opacity: 1, duration: 0.35 });
    });
}

function markDown(id, down) {
    const rect = document.querySelector(`#node-${id} .node-rect`);
    if (rect) rect.classList.toggle("is-down", down);
}

function stopTraffic() {
    if (trafficTimer) {
        clearInterval(trafficTimer);
        trafficTimer = null;
    }
}

function showLearnBox(title, text) {
    document.getElementById("learn-title").textContent = title;
    document.getElementById("learn-text").textContent = text;
    learnPanel.classList.remove("hidden");
}

function hideLearnBox() {
    learnPanel.classList.add("hidden");
}

const simulations = {
    login() {
        resetOpacities();
        dimAllExcept(["python", "lb", "nginx", "login", "postgres", "redis"]);
        showLearnBox("Login", "La contraseña se comprueba en PostgreSQL. Redis guarda la sesión y el refresh. El token de 20 minutos vuelve al cliente por la misma puerta. Nginx no firma nada.");
        runPath([
            ...door("python", "login", "POST /login", "var(--json-color)"),
            { from: "login", to: "postgres", label: "bcrypt", color: "var(--sql-color)", duration: 0.45 },
            { from: "postgres", to: "login", label: "ok", color: "var(--sql-color)", duration: 0.4 },
            { from: "login", to: "redis", label: "sesión", color: "var(--jwt-color)", duration: 0.45 },
            ...back("login", "python", "JWT", "var(--jwt-color)")
        ]);
    },
    books() {
        resetOpacities();
        bookLoad.booksa = 2;
        bookLoad.booksb = 0;
        bookLoad.booksc = 1;
        const chosen = leastBooks();
        bookLoad[chosen] += 1;
        dimAllExcept(["electron", "lb", "nginx", chosen, "redis"]);
        showLearnBox("Tres Books", `A tiene más conexiones abiertas, así que least_conn manda este GET a ${nodeById(chosen).name}. Las tres usan la misma base y la misma caché. En modo demo cada una tendría su propio catálogo en memoria.`);
        runPath([
            ...door("electron", chosen, "GET /books", "var(--xml-color)"),
            { from: chosen, to: "redis", label: "caché", color: "var(--redis-color)", duration: 0.4 },
            { from: "redis", to: chosen, label: "HIT", color: "var(--redis-color)", duration: 0.35 },
            ...back(chosen, "electron", "XML", "var(--xml-color)")
        ]);
    },
    compra() {
        resetOpacities();
        dimAllExcept(["python", "lb", "nginx", "login", "booksa", "pedidos", "pagos", "postgres", "redis"]);
        showLearnBox("Compra", "El cliente encadena los pasos. Pedidos descuenta el stock. Pagos escribe la orden como pagada en PostgreSQL y no le habla a Pedidos.");
        runPath([
            ...door("python", "login", "/login", "var(--json-color)"),
            { from: "login", to: "redis", label: "sesión", color: "var(--jwt-color)", duration: 0.35 },
            ...back("login", "python", "JWT", "var(--jwt-color)"),
            ...door("python", "booksa", "/books", "var(--json-color)"),
            ...back("booksa", "python", "precio", "var(--json-color)"),
            ...door("python", "pedidos", "Bearer", "var(--jwt-color)"),
            { from: "pedidos", to: "postgres", label: "stock", color: "var(--sql-color)", duration: 0.4 },
            ...back("pedidos", "python", "201", "var(--json-color)"),
            ...door("python", "pagos", "Bearer", "var(--jwt-color)"),
            { from: "pagos", to: "postgres", label: "pagado", color: "var(--sql-color)", duration: 0.45 },
            ...back("pagos", "python", "201", "var(--json-color)")
        ]);
    },
    caida() {
        resetOpacities();
        markDown("pedidos", true);
        dimAllExcept(["python", "lb", "nginx", "pedidos", "pagos", "booksa", "postgres"]);
        showLearnBox("Pedidos no responde", "Nginx devuelve 503 y no inventa otra instancia. El catálogo sigue. Un pago de una orden que ya existe también, porque Pagos escribe la base directo. Ese POST no se reintenta solo.");
        runPath([
            ...door("python", "nginx", "/pedidos", "var(--json-color)").slice(0, 2),
            { from: "nginx", to: "lb", label: "503", color: "#ef4444", duration: 0.45 },
            { from: "lb", to: "python", label: "503", color: "#ef4444", duration: 0.45 },
            ...door("python", "booksa", "/books", "var(--json-color)"),
            ...back("booksa", "python", "200", "var(--json-color)"),
            ...door("python", "pagos", "/pagos", "var(--jwt-color)"),
            { from: "pagos", to: "postgres", label: "pagado", color: "var(--sql-color)", duration: 0.45 }
        ]);
    },
    soap() {
        resetOpacities();
        dimAllExcept(["java", "lb", "nginx", "booksa"]);
        showLearnBox("SOAP", "POST /soap pasa por el balanceador y por Nginx, y llega a Books. No se le exige el JWT del login. La operación de estadísticas sigue pidiendo su usuario WS-Security.");
        runPath([
            ...door("java", "booksa", "SOAP", "var(--xml-color)"),
            ...back("booksa", "java", "XML", "var(--xml-color)")
        ]);
    }
};

function playScene(index) {
    stopTraffic();
    config.currentScene = index;
    document.querySelectorAll(".timeline-step").forEach((el) => {
        el.classList.toggle("active", Number(el.dataset.scene) === index);
    });
    resetOpacities();

    if (index === 0) {
        hideLearnBox();
        showLearnBox("Una sola puerta", "Hoy cada cliente conoce un puerto. Aquí todos llegan al balanceador. Nginx decide el Flask. Los procesos dejan de escucharse desde Internet.");
        return;
    }
    if (index === 1) {
        dimAllExcept(["python", "electron", "java", "browser", "lb"]);
        showLearnBox("Clientes", "Python, Electron, Java y el navegador usan el mismo HTTPS. Electron sigue pidiendo XML. Java sigue en /soap. El cliente ya no elige el puerto 5004.");
        return;
    }
    if (index === 2) {
        dimAllExcept(["lb", "nginx"]);
        showLearnBox("Balanceador", "Google Cloud termina el TLS y hace el health check contra el /health de Nginx, no contra el de un Flask: los seis ya tienen esa ruta y chocarían. Este balanceador no entiende un pedido ni revisa el token.");
        return;
    }
    if (index === 3) {
        dimAllExcept(["nginx", "login", "users", "authors", "pedidos", "pagos", "booksa"]);
        showLearnBox("Reverse proxy", "Nginx abre otra conexión hacia 127.0.0.1. /books va a Books, /pedidos al 5004 y /pagos al 5005. El cliente no ve esos puertos.");
        return;
    }
    if (index === 4) {
        dimAllExcept(["nginx", "login", "pedidos", "pagos"]);
        showLearnBox("Reglas de API", "En la misma instalación: CORS, límite de intentos en el login, /metrics cerrado y el encabezado Bearer en las rutas protegidas. La firma, la revocación en Redis, el rol y el dueño del recurso los sigue revisando cada Flask.");
        return;
    }
    if (index === 5) {
        simulations.books();
        return;
    }
    if (index === 6) {
        simulations.compra();
        return;
    }
    if (index === 7) {
        simulations.caida();
        return;
    }
    showLearnBox("Así queda", "Una entrada HTTPS, Flask en loopback y tres Books. Pedidos y Pagos siguen en un proceso. PostgreSQL y Redis también. Esto todavía no está medido con otra corrida de Locust.");
    const flows = [
        () => sendPacket("electron", "lb", "XML", "var(--xml-color)", 1.1),
        () => sendPacket("lb", "nginx", "HTTPS", "var(--https-color)", 0.8),
        () => sendPacket("booksa", "redis", "caché", "var(--redis-color)", 0.7),
        () => sendPacket("python", "lb", "JWT", "var(--jwt-color)", 1)
    ];
    trafficTimer = setInterval(() => {
        if (config.currentScene === LAST_SCENE) flows[Math.floor(Math.random() * flows.length)]();
    }, 2600);
}

document.querySelectorAll(".timeline-step").forEach((el) => {
    el.addEventListener("click", () => playScene(Number(el.dataset.scene)));
});
document.getElementById("btn-next-step").addEventListener("click", hideLearnBox);
document.getElementById("btn-next").addEventListener("click", () => {
    if (config.currentScene < LAST_SCENE) playScene(config.currentScene + 1);
});
document.getElementById("btn-prev").addEventListener("click", () => {
    if (config.currentScene > 0) playScene(config.currentScene - 1);
});
document.getElementById("btn-replay").addEventListener("click", () => playScene(config.currentScene));
document.getElementById("btn-explore").addEventListener("click", (event) => {
    event.currentTarget.classList.add("active");
    document.getElementById("btn-learn").classList.remove("active");
    stopTraffic();
    hideLearnBox();
    resetOpacities();
});
document.getElementById("btn-learn").addEventListener("click", (event) => {
    event.currentTarget.classList.add("active");
    document.getElementById("btn-explore").classList.remove("active");
    playScene(0);
});
document.getElementById("sim-login").addEventListener("click", () => simulations.login());
document.getElementById("sim-books").addEventListener("click", () => simulations.books());
document.getElementById("sim-compra").addEventListener("click", () => simulations.compra());
document.getElementById("sim-caida").addEventListener("click", () => simulations.caida());
document.getElementById("sim-soap").addEventListener("click", () => simulations.soap());

initArchitecture();
playScene(0);
