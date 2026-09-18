const { app, BrowserWindow, Menu, shell } = require("electron");
const path = require("path");

const LIBRARY = process.env.LIBRARY_URL || "http://127.0.0.1:3000/library";
const SOAP = process.env.SOAP_URL || "http://127.0.0.1:5001/";

function createWindow() {
  const win = new BrowserWindow({
    width: 1360,
    height: 900,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  win.loadFile(path.join(__dirname, "catalog.html"));
  win.once("ready-to-show", () => win.show());

  const menu = Menu.buildFromTemplate([
    {
      label: "Librería",
      submenu: [
        {
          label: "Catálogo XML",
          click: () => win.loadFile(path.join(__dirname, "catalog.html")),
        },
        {
          label: "Abrir librería Node (:3000)",
          click: () => win.loadURL(LIBRARY),
        },
        { type: "separator" },
        { role: "reload" },
        { role: "toggleDevTools" },
        { role: "quit" },
      ],
    },
    {
      label: "Microservicio",
      submenu: [
        { label: "Flask SOAP (:5001)", click: () => win.loadURL(SOAP) },
        { label: "Flask SOAP (:5000)", click: () => win.loadURL("http://127.0.0.1:5000/") },
        { label: "GET /books XML", click: () => win.loadURL("http://127.0.0.1:5001/books") },
        {
          label: "GET /books-images XML",
          click: () => win.loadURL("http://127.0.0.1:5001/books-images"),
        },
      ],
    },
  ]);
  Menu.setApplicationMenu(menu);
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());
app.on("web-contents-created", (_event, contents) => {
  contents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
});
