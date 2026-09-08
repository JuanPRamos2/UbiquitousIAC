-- Enlaces demo para que líderes y auditores tengan unidad (el script oficial deja usuario_id NULL).
UPDATE usuarios.empleado SET usuario_id = 'USR-00011' WHERE empleado_id = 'EMP-00933';
UPDATE usuarios.empleado SET usuario_id = 'USR-00027' WHERE empleado_id = 'EMP-00210';
