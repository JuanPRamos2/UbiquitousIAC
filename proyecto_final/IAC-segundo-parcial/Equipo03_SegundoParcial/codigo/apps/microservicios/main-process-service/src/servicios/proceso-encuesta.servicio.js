/**
 * Proceso de evaluacion: registrar una respuesta y resumir las entregas.
 *
 * La regla D-01 se verifica aqui, antes de tocar cualquier base: si el
 * cuerpo trae empleado_id la peticion se rechaza completa. No se "limpia"
 * el campo en silencio a proposito: un cliente que manda empleado_id esta
 * programado con un modelo equivocado del sistema y conviene que lo sepa.
 */
import { ErrorApi } from "@bienestar/comun/errores.js";
import * as EncuestaModelo from "@bienestar/comun/modelos/Encuesta.js";
import { registrarEventoProceso } from "@bienestar/comun/modelos/EventosProceso.js";
import { contextoOperativo } from "@bienestar/comun/modelos/Usuario.js";
import { guardarAutoreporte } from "@bienestar/comun/servicios/encuesta.servicio.js";

export async function registrarRespuesta({ actor, cuerpo, correlacionId, colEventos, colRespuestas }) {
  if (!cuerpo || typeof cuerpo !== "object") {
    throw new ErrorApi("CUERPO_REQUERIDO", "El cuerpo de la peticion es obligatorio.", 400);
  }
  if ("empleado_id" in cuerpo) {
    throw new ErrorApi("PRIVACIDAD_D01",
      "No se admite 'empleado_id' en este servicio: la respuesta se registra " +
      "contra el seudonimo y la correspondencia con la persona no sale de " +
      "PostgreSQL.", 400,
      [{ campo: "empleado_id", problema: "identificador directo de persona" }]);
  }

  const resultado = await guardarAutoreporte({ actor, cuerpo, correlacionId, colRespuestas });

  // El evento se emite despues de que la respuesta quedo registrada. Si
  // fallara la emision, la respuesta NO se pierde: el evento es
  // trazabilidad y se puede reconstruir, la respuesta de la persona no.
  let eventoId = null;
  try {
    const evento = await registrarEventoProceso({
      seudonimo_id: resultado.seudonimo_id,
      correlacion_id: correlacionId,
      tipo: "RESPUESTA_REGISTRADA",
      detalle: {
        campania_id: resultado.campania_id,
        instrumento_id: resultado.instrumento_id,
        version_instrumento: resultado.version_instrumento,
        documento_id: resultado.documento_id,
      },
    }, colEventos);
    eventoId = evento.id;
  } catch { /* trazabilidad degradada, respuesta intacta */ }

  return { ...resultado, evento_id: eventoId };
}

export async function resumenAgregados({ consulta = {}, colRespuestas }) {
  const filtros = {
    campania_id: consulta.campania_id || undefined,
    desde: consulta.desde || undefined,
    hasta: consulta.hasta || undefined,
  };
  const grupos = await EncuestaModelo.agregarRespuestasPorUnidadCampania(filtros, colRespuestas);

  // Este resumen cuenta ENTREGAS, no puntajes: cuantas personas
  // respondieron por unidad y campania. Los puntajes solo salen del
  // mecanismo de agregacion protegida de PostgreSQL, que aplica umbral k y
  // privacidad diferencial. Contar entregas no revela ninguna respuesta,
  // pero un conteo muy bajo si revelaria que en esa unidad respondio
  // practicamente una persona, asi que se marca.
  const UMBRAL_AVISO = 5;
  const resumen = grupos.map((g) => ({
    ...g,
    suficiente_para_publicar: g.respuestas >= UMBRAL_AVISO,
  }));

  return {
    total_grupos: resumen.length,
    campania_id: filtros.campania_id || null,
    umbral_aviso: UMBRAL_AVISO,
    nota: "Son conteos de entrega. Los puntajes se consultan en el panel de " +
          "agregados protegidos, nunca aqui.",
    agregados: resumen,
  };
}

export async function respuestasPropias({ actor, colRespuestas }) {
  const ctx = await contextoOperativo(actor?.sub || actor?.usuario_id);
  if (!ctx?.seudonimo_id) {
    throw new ErrorApi("SIN_SEUDONIMO",
      "La cuenta no tiene participacion operativa en el programa.", 403);
  }
  const documentos = await EncuestaModelo.buscarPorSeudonimo(ctx.seudonimo_id, colRespuestas);
  // Se devuelve el acuse, no las respuestas: que una persona pueda releer
  // lo que contesto esta bien, pero el contrato de esta ruta es el
  // comprobante de participacion y no el contenido.
  return {
    seudonimo_id: ctx.seudonimo_id,
    total: documentos.length,
    respuestas: documentos.map((d) => ({
      campania_id: d.campania_id,
      instrumento_id: d.instrumento_id,
      version_instrumento: d.version_instrumento,
      fecha: d.fecha,
      reactivos_respondidos: Object.keys(d.valores || {}).length,
    })),
  };
}
