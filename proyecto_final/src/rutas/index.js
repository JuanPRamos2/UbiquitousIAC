import { Router } from "express";
import { authRouter } from "./auth.rutas.js";
import { catalogoRouter } from "./catalogo.rutas.js";
import { encuestaRouter } from "./encuesta.rutas.js";
import { agregadoRouter } from "./agregado.rutas.js";
import { auditoriaRouter } from "./auditoria.rutas.js";

import { portalRouter } from "./portal.rutas.js";

export const api = Router();
api.use("/auth", authRouter);
api.use("/catalogos", catalogoRouter);
api.use("/encuestas", encuestaRouter);
api.use("/agregados", agregadoRouter);
api.use("/auditoria", auditoriaRouter);
api.use("/portal", portalRouter);
