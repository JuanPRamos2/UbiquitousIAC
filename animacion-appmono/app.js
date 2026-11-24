// --- DATOS DE LA ARQUITECTURA ---
const archData = {
    nodes: [
        // Clientes
        { id: "python", type: "client", x: 100, y: 150, name: "Python_app", tech: "Tkinter / JSON", desc: "App escritorio autentiacada." },
        { id: "electron", type: "client", x: 100, y: 350, name: "Electron_app", tech: "Electron / XML", desc: "Catálogo público multiplataforma." },
        { id: "monolito", type: "client", x: 100, y: 600, name: "web-monolito", tech: "Node / Express / EJS", desc: "Panel admin (Render SSR). No usa APIs." },
        
        // Servicios GCP
        { id: "login", type: "service", x: 450, y: 150, name: "Login :5000", tech: "Flask", desc: "Emisión y validación de JWT." },
        { id: "users", type: "service", x: 650, y: 150, name: "Users :5002", tech: "Flask", desc: "CRUD perfiles de usuario." },
        { id: "books", type: "service", x: 450, y: 350, name: "Books :5001", tech: "Flask", desc: "Catálogo JSON/XML." },
        { id: "authors", type: "service", x: 650, y: 350, name: "Authors :5003", tech: "Flask", desc: "Gestión de autores." },
        { id: "pedidos", type: "service", x: 450, y: 550, name: "Pedidos :5004", tech: "Flask", desc: "Carrito y órdenes." },
        { id: "pagos", type: "service", x: 650, y: 550, name: "Pagos :5005", tech: "Flask", desc: "Transacciones." },
        
        // DB y Cache
        { id: "redis", type: "cache", x: 950, y: 150, name: "Redis Cache", tech: "Memory Store", desc: "Sesiones, JWT, Cache ultrarrápido." },
        { id: "postgres", type: "database", x: 950, y: 450, name: "Cloud SQL", tech: "PostgreSQL", desc: "Base de datos centralizada." },
        { id: "smtp", type: "external", x: 950, y: 650, name: "SMTP Postfix", tech: "Email", desc: "Verificación de cuentas." }
    ],
    connections: [
        // Clientes a APIs
        { from: "python", to: "login", type: "json" },
        { from: "python", to: "books", type: "json" },
        { from: "python", to: "pedidos", type: "json" },
        { from: "electron", to: "books", type: "xml" },
        
        // Monolito Directo
        { from: "monolito", to: "postgres", type: "direct" },
        
        // Servicios a BD
        { from: "login", to: "postgres", type: "sql" },
        { from: "users", to: "postgres", type: "sql" },
        { from: "books", to: "postgres", type: "sql" },
        { from: "authors", to: "postgres", type: "sql" },
        { from: "pedidos", to: "postgres", type: "sql" },
        { from: "pagos", to: "postgres", type: "sql" },
        
        // Microservicios internos
        { from: "login", to: "redis", type: "json" },
        { from: "books", to: "redis", type: "json" },
        { from: "pedidos", to: "pagos", type: "json" },
        { from: "login", to: "smtp", type: "json" }
    ]
};

// --- MOTOR DE LA APLICACIÓN ---
const svgNodes = document.getElementById('layer-nodes');
const svgConns = document.getElementById('layer-connections');
const svgBgs = document.getElementById('layer-backgrounds');
const svgPackets = document.getElementById('layer-packets');
const tooltip = document.getElementById('tooltip');

const NODE_W = 140, NODE_H = 60;
const nodeElements = {};
const config = { currentScene: 0, learnMode: false };

// Inicialización visual
function initArchitecture() {
    // 1. Dibujar Caja VPC GCP
    const vpc = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    vpc.setAttribute("x", "380"); vpc.setAttribute("y", "70");
    vpc.setAttribute("width", "480"); vpc.setAttribute("height", "580");
    vpc.setAttribute("class", "gcp-box");
    svgBgs.appendChild(vpc);

    const vpcLabel = document.createElementNS("http://www.w3.org/2000/svg", "text");
    vpcLabel.setAttribute("x", "620"); vpcLabel.setAttribute("y", "100");
    vpcLabel.setAttribute("class", "gcp-label");
    vpcLabel.setAttribute("text-anchor", "middle");
    vpcLabel.textContent = "GOOGLE CLOUD PLATFORM (VPC)";
    svgBgs.appendChild(vpcLabel);

    // 2. Dibujar Conexiones
    archData.connections.forEach(conn => {
        const from = archData.nodes.find(n => n.id === conn.from);
        const to = archData.nodes.find(n => n.id === conn.to);
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        
        // Calcula puntos de anclaje (simplificado: centro a centro)
        const x1 = from.x + (from.id === 'monolito' ? NODE_W : NODE_W/2);
        const y1 = from.y + NODE_H/2;
        const x2 = to.x + NODE_W/2;
        const y2 = to.y + NODE_H/2;

        let d = '';
        if (conn.type === 'direct') {
            // Línea especial recta para monolito
            d = `M ${x1} ${y1} L ${x2} ${y2}`;
        } else {
            // Curva Bezier
            d = `M ${x1} ${y1} C ${(x1+x2)/2} ${y1}, ${(x1+x2)/2} ${y2}, ${x2} ${y2}`;
        }

        path.setAttribute("d", d);
        path.setAttribute("class", `connection conn-${conn.type}`);
        path.id = `conn-${conn.from}-${conn.to}`;
        svgConns.appendChild(path);
    });

    // 3. Dibujar Nodos
    archData.nodes.forEach(n => {
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("transform", `translate(${n.x}, ${n.y})`);
        g.id = `node-${n.id}`;
        
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("width", NODE_W);
        rect.setAttribute("height", NODE_H);
        rect.setAttribute("class", `node-rect node-${n.type}`);
        
        const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
        text.setAttribute("x", NODE_W/2);
        text.setAttribute("y", NODE_H/2 - 2);
        text.setAttribute("class", "node-text");
        text.textContent = n.name;

        const subText = document.createElementNS("http://www.w3.org/2000/svg", "text");
        subText.setAttribute("x", NODE_W/2);
        subText.setAttribute("y", NODE_H/2 + 15);
        subText.setAttribute("class", "node-subtext");
        subText.textContent = n.tech;

        g.appendChild(rect);
        g.appendChild(text);
        g.appendChild(subText);
        svgNodes.appendChild(g);

        nodeElements[n.id] = g;

        // Interactividad (Hover Tooltips)
        g.addEventListener('mouseenter', (e) => showTooltip(e, n));
        g.addEventListener('mouseleave', hideTooltip);
        g.addEventListener('click', () => bounceNode(n.id));
    });
}

function showTooltip(e, node) {
    tooltip.innerHTML = `<h4>${node.name.toUpperCase()}</h4><p><strong>Tipo:</strong> ${node.type}</p><p><strong>Tech:</strong> ${node.tech}</p><p>${node.desc}</p>`;
    tooltip.style.left = `${e.pageX + 15}px`;
    tooltip.style.top = `${e.pageY + 15}px`;
    tooltip.classList.remove('hidden');
}

function hideTooltip() { tooltip.classList.add('hidden'); }

// --- ANIMACIONES BASE (GSAP) ---

function bounceNode(id) {
    gsap.fromTo(`#node-${id}`, 
        { scale: 0.9, transformOrigin: "center" },
        { scale: 1, duration: 0.4, ease: "back.out(1.7)", transformOrigin: "center" }
    );
}

// Simulación de paquetes de datos viajando por las líneas
function sendPacket(fromId, toId, label, color, duration = 1.5, onComplete = null) {
    const from = archData.nodes.find(n => n.id === fromId);
    const to = archData.nodes.find(n => n.id === toId);
    if(!from || !to) return;

    // Crear paquete
    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("width", 60); rect.setAttribute("height", 24);
    rect.setAttribute("rx", 12);
    rect.setAttribute("fill", color);
    
    const text = document.createElementNS("http://www.w3.org/2000/svg", "text");
    text.setAttribute("x", 30); text.setAttribute("y", 16);
    text.setAttribute("fill", "white");
    text.setAttribute("font-size", "11px");
    text.setAttribute("font-family", "sans-serif");
    text.setAttribute("font-weight", "bold");
    text.setAttribute("text-anchor", "middle");
    text.textContent = label;

    g.appendChild(rect);
    g.appendChild(text);
    svgPackets.appendChild(g);

    // Centrar paquete en el nodo origen
    gsap.set(g, { x: from.x + NODE_W/2 - 30, y: from.y + NODE_H/2 - 12 });

    // Animación de viaje
    gsap.to(g, {
        x: to.x + NODE_W/2 - 30,
        y: to.y + NODE_H/2 - 12,
        duration: duration,
        ease: "power1.inOut",
        onStart: () => bounceNode(fromId),
        onComplete: () => {
            bounceNode(toId);
            // Pequeño efecto de impacto (fade out arriba)
            gsap.to(g, { y: "-=20", opacity: 0, duration: 0.3, onComplete: () => g.remove() });
            if(onComplete) onComplete();
        }
    });
}

// --- SIMULACIONES ESPECÍFICAS ---
const simulations = {
    api: () => {
        resetOpacities();
        sendPacket('python', 'books', 'GET /books', 'var(--json-color)', 1, () => {
            sendPacket('books', 'postgres', 'SELECT', 'var(--sql-color)', 0.8, () => {
                sendPacket('postgres', 'books', 'Rows', 'var(--sql-color)', 0.8, () => {
                    sendPacket('books', 'python', '200 JSON', 'var(--json-color)', 1);
                });
            });
        });
    },
    electron: () => {
        resetOpacities();
        sendPacket('electron', 'books', 'GET (XML)', 'var(--xml-color)', 1, () => {
            sendPacket('books', 'electron', 'XML Data', 'var(--xml-color)', 1);
        });
    },
    login: () => {
        resetOpacities();
        sendPacket('python', 'login', 'POST /login', 'var(--json-color)', 1, () => {
            sendPacket('login', 'postgres', 'Verify', 'var(--sql-color)', 0.5, () => {
                sendPacket('postgres', 'login', 'OK', 'var(--sql-color)', 0.5, () => {
                    sendPacket('login', 'redis', 'Save Session', 'var(--redis-color)', 0.5, () => {
                        // Crear JWT Físico
                        sendPacket('login', 'python', 'JWT Token', 'var(--jwt-color)', 1.2, () => {
                            showLearnBox('¡JWT Recibido!', 'El cliente Python ahora guardará este token amarillo y lo enviará en la cabecera Authorization en cada petición futura.');
                        });
                    });
                });
            });
        });
    },
    cache: () => {
        resetOpacities();
        // Primera vuelta lenta
        showLearnBox('1. Cache Miss', 'La primera vez, el servicio consulta PostgreSQL (Lento: 300ms).');
        sendPacket('books', 'postgres', 'SELECT', 'var(--sql-color)', 1.5, () => {
            sendPacket('postgres', 'books', 'Result', 'var(--sql-color)', 1.5, () => {
                sendPacket('books', 'redis', 'Save Cache', 'var(--redis-color)', 0.5, () => {
                    // Segunda vuelta rápida
                    setTimeout(() => {
                        showLearnBox('2. Cache Hit!', 'La siguiente petición la responde Redis casi al instante (Rápido: 20ms).');
                        sendPacket('books', 'redis', 'GET /books', 'var(--redis-color)', 0.2, () => {
                            sendPacket('redis', 'books', 'Cached Data', 'var(--redis-color)', 0.2);
                        });
                    }, 2000);
                });
            });
        });
    },
    order: () => {
        resetOpacities();
        sendPacket('python', 'pedidos', 'POST Order', 'var(--json-color)', 1, () => {
            sendPacket('pedidos', 'postgres', 'INSERT', 'var(--sql-color)', 0.5, () => {
                sendPacket('pedidos', 'pagos', 'Process', 'var(--json-color)', 0.8, () => {
                    sendPacket('pagos', 'postgres', 'UPDATE', 'var(--sql-color)', 0.5, () => {
                        sendPacket('pagos', 'pedidos', 'OK', 'var(--json-color)', 0.8, () => {
                            sendPacket('pedidos', 'python', '201 Created', 'var(--json-color)', 1);
                        });
                    });
                });
            });
        });
    },
    monolith: () => {
        dimAllExcept(['monolito', 'postgres']);
        showLearnBox('El Monolito Web', 'A diferencia de Python o Electron, el monolito Node.js tiene acceso directo a PostgreSQL. Renderiza el HTML (EJS) directamente en el servidor sin consumir los microservicios Flask.');
        // Línea gruesa
        const path = document.getElementById('conn-monolito-postgres');
        gsap.to(path, { strokeWidth: 8, stroke: '#ef4444', duration: 0.5, yoyo: true, repeat: 3 });
        
        sendPacket('monolito', 'postgres', 'SQL Directo', 'var(--sql-color)', 0.8, () => {
            sendPacket('postgres', 'monolito', 'Data', 'var(--sql-color)', 0.8);
        });
    }
};

// --- CONTROL DE ESCENAS ---
function resetOpacities() {
    gsap.to('.node-rect, .node-text, .node-subtext, .connection', { opacity: 1, duration: 0.5 });
    hideLearnBox();
}

function dimAllExcept(ids) {
    gsap.to('.node-rect, .node-text, .node-subtext', { opacity: 0.2, duration: 0.5 });
    gsap.to('.connection', { opacity: 0.1, duration: 0.5 });
    ids.forEach(id => {
        gsap.to(`#node-${id} *`, { opacity: 1, duration: 0.5 });
    });
}

function playScene(index) {
    config.currentScene = index;
    document.querySelectorAll('.timeline-step').forEach(el => el.classList.remove('active'));
    document.querySelector(`[data-scene="${index}"]`).classList.add('active');
    
    resetOpacities();

    switch(index) {
        case 0: // Intro
            gsap.from('#layer-nodes g, #layer-backgrounds *', { opacity: 0, y: 30, stagger: 0.1, duration: 0.8 });
            gsap.from('.connection', { opacity: 0, duration: 1, delay: 1 });
            break;
        case 1: // Clientes
            dimAllExcept(['python', 'electron', 'monolito']);
            showLearnBox('Clientes', 'El sistema tiene 3 entradas principales. Dos aplicaciones de escritorio y una plataforma web monolítica de administración.');
            break;
        case 2: // Cloud
            dimAllExcept(['login', 'users', 'books', 'authors', 'pedidos', 'pagos']);
            showLearnBox('Microservicios GCP', 'La lógica de negocio está dividida en servicios independientes escritos en Python (Flask), expuestos a través de puertos específicos en una VPC.');
            break;
        case 3: // API Sim
            simulations.api();
            showLearnBox('Flujo API', 'Las peticiones viajan mediante JSON por HTTP. Los servicios consultan PostgreSQL y retornan las respuestas.');
            break;
        case 4: // DB
            dimAllExcept(['postgres', 'login', 'books', 'users', 'monolito']);
            showLearnBox('PostgreSQL Centralizado', 'A pesar de usar microservicios para la lógica, la base de datos relacional se mantiene centralizada en Cloud SQL (PostgreSQL).');
            break;
        case 5: // Cache
            simulations.cache();
            break;
        case 6: // Auth
            simulations.login();
            break;
        case 7: // Monolito
            simulations.monolith();
            break;
        case 8: // Full
            resetOpacities();
            showLearnBox('Arquitectura Completa', 'Todos los componentes trabajando en conjunto. (Modo Explorar activo: Usa los botones superiores para interactuar).');
            // Random traffic background
            setInterval(() => {
                if(config.currentScene === 8) {
                    const flows = [
                        () => sendPacket('electron', 'books', 'XML', 'var(--xml-color)', 1.5),
                        () => sendPacket('books', 'redis', 'Cache', 'var(--redis-color)', 0.5),
                        () => sendPacket('login', 'smtp', 'Email', 'var(--smtp-color)', 2),
                        () => sendPacket('python', 'users', 'JWT', 'var(--jwt-color)', 1.2)
                    ];
                    flows[Math.floor(Math.random() * flows.length)]();
                }
            }, 3000);
            break;
    }
}

// UI Helpers
const learnPanel = document.getElementById('learning-panel');
function showLearnBox(title, text) {
    document.getElementById('learn-title').textContent = title;
    document.getElementById('learn-text').textContent = text;
    learnPanel.classList.remove('hidden');
    gsap.fromTo(learnPanel, { x: -20, opacity: 0 }, { x: 0, opacity: 1, duration: 0.3 });
}
function hideLearnBox() { learnPanel.classList.add('hidden'); }

// Listeners
document.querySelectorAll('.timeline-step').forEach(el => {
    el.addEventListener('click', (e) => {
        playScene(parseInt(e.target.getAttribute('data-scene')));
    });
});

document.getElementById('btn-next-step').addEventListener('click', () => hideLearnBox());

document.getElementById('btn-next').addEventListener('click', () => {
    if(config.currentScene < 8) playScene(config.currentScene + 1);
});
document.getElementById('btn-prev').addEventListener('click', () => {
    if(config.currentScene > 0) playScene(config.currentScene - 1);
});
document.getElementById('btn-replay').addEventListener('click', () => playScene(config.currentScene));

document.getElementById('btn-explore').addEventListener('click', (e) => {
    e.target.classList.add('active');
    document.getElementById('btn-learn').classList.remove('active');
    config.learnMode = false;
    hideLearnBox();
    resetOpacities();
});

document.getElementById('btn-learn').addEventListener('click', (e) => {
    e.target.classList.add('active');
    document.getElementById('btn-explore').classList.remove('active');
    config.learnMode = true;
    playScene(0);
});

// Start
initArchitecture();
setTimeout(() => playScene(0), 500);
