-- Recurso adicional para login/logout: las cuentas viven en usuarios.usuario.
-- El esquema oficial no incluía USUARIO; sin esto LOGIN usaba SEUDONIMO de forma incorrecta.
INSERT INTO auditoria.tipo_recurso (codigo, descripcion)
VALUES ('USUARIO', 'Cuenta de acceso. Referenciada por bitacora_auditoria.actor_id')
ON CONFLICT (codigo) DO NOTHING;
