ALTER TABLE organizacion.unidad_organizacional ADD COLUMN IF NOT EXISTS descripcion TEXT;
ALTER TABLE catalogo.instrumento ADD COLUMN IF NOT EXISTS descripcion TEXT;
ALTER TABLE catalogo.campania ADD COLUMN IF NOT EXISTS descripcion TEXT;
