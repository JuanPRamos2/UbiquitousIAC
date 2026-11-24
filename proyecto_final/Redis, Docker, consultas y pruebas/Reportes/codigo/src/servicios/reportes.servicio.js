import { HttpError } from "../../../comun/src/errores.js";
import { alcanceUnidad, PERFILES_AUDITORIA } from "../../../comun/src/perfiles.js";

function serie(name, data) {
  return { name, data };
}

function grafica(categories, series, extra = {}) {
  return { categories, series, ...extra };
}

async function cachear(cache, contador, recurso, partes, calcular) {
  const resultado = await cache.obtener(recurso, partes, calcular);
  await contador.incrementar();
  return resultado;
}

export function crearServicioReportes({ repo, cache, contador }) {
  function unidadDe(actor, pedida) {
    return alcanceUnidad(actor, pedida, HttpError);
  }

  return {
    async resumen(actor) {
      const unidad = actor.perfil === "LIDER" ? unidadDe(actor, null) : null;
      const resultado = await cachear(cache, contador, "resumen", { unidad, perfil: actor.perfil }, async () => {
        const conteos = await repo.conteos(unidad);
        const categories = ["Campañas", "Unidades activas", "Intervenciones", "Resultados protegidos"];
        const data = [conteos.campanias, conteos.unidades, conteos.intervenciones, conteos.resultados];
        let nota = "Los resultados protegidos aparecen cuando el proceso principal ya los publicó.";
        if (PERFILES_AUDITORIA.includes(actor.perfil)) {
          const eventos = await repo.eventosAuditoria();
          categories.push("Eventos de auditoría");
          data.push(eventos);
        }
        if (unidad) nota = `${nota} El líder ve intervenciones y resultados solo de su unidad.`;
        return grafica(categories, [serie("Registros", data)], {
          nota,
          unidad_organizacional_id: unidad,
        });
      });
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async campaniasPorEstado(actor) {
      const resultado = await cachear(cache, contador, "campanias-estado", { perfil: actor.perfil }, async () => {
        const filas = await repo.campaniasPorEstado();
        return grafica(
          filas.map((fila) => fila.estado),
          [serie("Campañas", filas.map((fila) => fila.total))],
          { nota: "Distribución real del catálogo de campañas." }
        );
      });
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async intervencionesPorEstado(actor) {
      const unidad = actor.perfil === "LIDER" ? unidadDe(actor, null) : null;
      const resultado = await cachear(cache, contador, "intervenciones-estado", { unidad, perfil: actor.perfil }, async () => {
        const filas = await repo.intervencionesPorEstado(unidad);
        const nota = filas.length
          ? "Planes organizacionales agrupados por estado."
          : "No hay planes de intervención registrados.";
        return grafica(
          filas.map((fila) => fila.estado),
          [serie("Intervenciones", filas.map((fila) => fila.total))],
          { nota, unidad_organizacional_id: unidad }
        );
      });
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async reglasPorNivel(actor) {
      const resultado = await cachear(cache, contador, "reglas-nivel", { perfil: actor.perfil }, async () => {
        const filas = await repo.reglasPorNivel();
        return grafica(
          filas.map((fila) => fila.nivel),
          [serie("Reglas activas", filas.map((fila) => fila.total))],
          { nota: "Motor de reglas organizacionales. No identifica personas." }
        );
      });
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async fuentes(actor) {
      const resultado = await cachear(cache, contador, "fuentes", { perfil: actor.perfil }, async () => {
        const filas = await repo.fuentes();
        return grafica(
          filas.map((fila) => fila.categoria),
          [serie("Fuentes", filas.map((fila) => fila.total))],
          { nota: "Fuentes permitidas frente a fuentes prohibidas por vigilancia." }
        );
      });
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async tendencia(actor, filtros) {
      const unidad = unidadDe(actor, filtros.unidad_organizacional_id);
      const resultado = await cachear(
        cache,
        contador,
        "tendencia",
        { unidad, dimension: filtros.dimension_id || null, perfil: actor.perfil, usuario: actor.usuario_id },
        async () => {
          const k = await repo.umbralK();
          const participacion = await repo.participacion(unidad);
          const protegidos = await repo.tendencia(unidad, filtros.dimension_id);
          const porCampania = new Map(protegidos.map((fila) => [fila.campania_id, fila.valor_protegido]));
          const haySupresion = participacion.some((fila) => fila.n < k);
          const hayValor = protegidos.length > 0;
          return grafica(
            participacion.map((fila) => fila.nombre),
            [
              serie(
                "Participación suficiente",
                participacion.map((fila) => (fila.n >= k ? 1 : null))
              ),
              serie(
                "Valor protegido",
                participacion.map((fila) => (porCampania.has(fila.campania_id) ? porCampania.get(fila.campania_id) : null))
              ),
            ],
            {
              nota: [
                "1 significa que el grupo alcanzó el umbral k. El tamaño exacto no se publica.",
                haySupresion ? "Un punto vacío indica grupo insuficiente." : null,
                hayValor
                  ? "El valor protegido sale de resultados ya publicados."
                  : "Aún no hay valores protegidos publicados por el proceso principal.",
              ]
                .filter(Boolean)
                .join(" "),
              unidad_organizacional_id: unidad,
            }
          );
        }
      );
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async auditoriaPorAccion(actor, filtros) {
      const resultado = await cachear(
        cache,
        contador,
        "auditoria-accion",
        { filtros, perfil: actor.perfil },
        async () => {
          const filas = await repo.auditoriaPorAccion(filtros.desde, filtros.hasta);
          return grafica(
            filas.map((fila) => fila.accion),
            [serie("Eventos", filas.map((fila) => fila.total))],
            { nota: "Conteo de la bitácora. No incluye el contenido de las respuestas." }
          );
        }
      );
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async auditoriaPorPeriodo(actor, filtros) {
      const resultado = await cachear(
        cache,
        contador,
        "auditoria-periodo",
        { filtros, perfil: actor.perfil },
        async () => {
          const filas = await repo.auditoriaPorPeriodo(filtros.desde, filtros.hasta);
          return grafica(
            filas.map((fila) => fila.dia),
            [serie("Eventos", filas.map((fila) => fila.total))],
            { nota: "Eventos de auditoría agrupados por día." }
          );
        }
      );
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async publicacion(actor) {
      const unidad = actor.perfil === "LIDER" ? unidadDe(actor, null) : null;
      const resultado = await cachear(cache, contador, "publicacion", { unidad, perfil: actor.perfil }, async () => {
        const filas = await repo.publicacion(unidad);
        const nota = filas.length
          ? "Estados de publicación ya calculados. Este reporte no vuelve a gastar presupuesto de privacidad."
          : "Todavía no hay filas en agregado.resultado_protegido. Las publica el proceso principal.";
        return grafica(
          filas.map((fila) => fila.estado),
          [serie("Resultados", filas.map((fila) => fila.total))],
          { nota, unidad_organizacional_id: unidad }
        );
      });
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async solicitudes(actor) {
      const resultado = await cachear(cache, contador, "solicitudes", { perfil: actor.perfil }, async () => {
        const filas = await repo.solicitudesPorEstado();
        const nota = filas.length
          ? "Solicitudes de apoyo en MongoDB, agrupadas por estado y sin seudónimo."
          : "MongoDB no tiene solicitudes de apoyo todavía.";
        return grafica(
          filas.map((fila) => fila.estado),
          [serie("Solicitudes", filas.map((fila) => fila.total))],
          { nota }
        );
      });
      return { data: resultado.valor, cache: resultado.cache, clave: resultado.clave };
    },

    async observabilidad() {
      return contador.leer();
    },
  };
}
