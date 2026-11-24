import { v4 as uuid } from "uuid";

export function correlacion(req, res, next) {
  req.correlacionId = req.headers["x-correlation-id"] || uuid();
  res.setHeader("x-correlation-id", req.correlacionId);
  next();
}
