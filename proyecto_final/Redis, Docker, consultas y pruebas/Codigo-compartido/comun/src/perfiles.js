export const PERFILES = {
  COLABORADOR: "COLABORADOR",
  LIDER: "LIDER",
  ESPECIALISTA: "ESPECIALISTA",
  AUDITOR: "AUDITOR",
  ADMINISTRADOR: "ADMINISTRADOR",
};

export const TODOS_LOS_PERFILES = Object.values(PERFILES);

export const PERFILES_ORGANIZACION = [
  PERFILES.LIDER,
  PERFILES.ESPECIALISTA,
  PERFILES.AUDITOR,
  PERFILES.ADMINISTRADOR,
];

export const PERFILES_AUDITORIA = [PERFILES.AUDITOR, PERFILES.ADMINISTRADOR];

export const PERFILES_AGREGADO = PERFILES_ORGANIZACION;

export function crearAutorizar(HttpError) {
  return (...perfiles) => {
    const permitidos = perfiles.flat();
    return (req, _res, next) => {
      if (!req.actor) return next(new HttpError(401, "SIN_SESION", "No autenticado"));
      if (!permitidos.includes(req.actor.perfil)) {
        return next(new HttpError(403, "RBAC", "Perfil sin permiso para este recurso"));
      }
      return next();
    };
  };
}

export function alcanceUnidad(actor, unidadPedida, HttpError) {
  if (actor.perfil !== PERFILES.LIDER) return unidadPedida || null;
  if (!actor.unidad_organizacional_id) {
    throw new HttpError(403, "RBAC", "El líder no tiene una unidad de alcance asignada");
  }
  if (unidadPedida && unidadPedida !== actor.unidad_organizacional_id) {
    throw new HttpError(403, "RBAC", "Solo puedes consultar información de tu unidad");
  }
  return actor.unidad_organizacional_id;
}
