"""Capa compartida de Redis y JWT.

Cada microservicio es un proceso aparte. Esta biblioteca solo unifica la URL de
Redis, la verificación del JWT y el CORS. No consulta datos de otro servicio.
"""
