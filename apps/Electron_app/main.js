const { app, BrowserWindow, Menu, shell } = require("electron");

const LIBRARY = process.env.LIBRARY_URL || "http://127.0.0.1:3000/library";
const SOAP = process.env.SOAP_URL || "http://127.0.0.1:5001/";
const BOOKS_JSON = process.env.BOOKS_JSON_URL || "http://127.0.0.1:5001/books?format=json";

function createWindow() {
  const win = new BrowserWindow({
    width: 1280,
    height: 840,
    webPreferences: { contextIsolation: true },
  });

  win.loadFile("start.html");

  const menu = Menu.buildFromTemplate([
    {
      label: "Librería",
      submenu: [
        {
          label: "Abrir librería (:3000)",
          click: () => win.loadURL(LIBRARY),
        },
        {
          label: "Inicio Electron",
          click: () => win.loadFile("start.html"),
        },
        { type: "separator" },
        { role: "reload" },
        { role: "quit" },
      ],
    },
    {
      label: "SOAP / JSON",
      submenu: [
        {
          label: "Flask SOAP (:5001)",
          click: () => win.loadURL(SOAP),
        },
        {
          label: "Flask SOAP (:5000)",
          click: () => win.loadURL("http://127.0.0.1:5000/"),
        },
        {
          label: "Catálogo JSON",
          click: () => win.loadURL(BOOKS_JSON),
        },
        {
          label: "Catálogo XML",
          click: () => win.loadURL("http://127.0.0.1:5001/books"),
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
