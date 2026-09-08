import { Router } from "express";
import * as Auth from "../controladores/auth.controlador.js";
import { autenticar } from "../middlewares/autenticacion.js";

export const authRouter = Router();
authRouter.post("/login", Auth.login);
authRouter.post("/logout", autenticar, Auth.logout);
authRouter.get("/me", autenticar, Auth.me);
