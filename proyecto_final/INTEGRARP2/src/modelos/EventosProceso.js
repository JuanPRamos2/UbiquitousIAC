export async function registrarEventoProceso(doc, coleccion) {
  const evento = { ...doc, fecha: new Date() };
  if (coleccion && typeof coleccion.insertOne === "function") {
    const resultado = await coleccion.insertOne(evento);
    return { id: String(resultado.insertedId), ...evento };
  }
  return { id: "sin-coleccion", ...evento };
}

export async function listarEventosProceso(coleccion, limite = 50) {
  if (!coleccion || typeof coleccion.find !== "function") return [];
  return coleccion.find({}).sort({ fecha: -1 }).limit(Number(limite) || 50).toArray();
}
