#!/usr/bin/env python3
"""Cliente generado conceptualmente desde el WSDL (zeep).

No usa xml.etree: zeep lee el contrato y construye las llamadas.
Sirve como evidencia de interoperabilidad frente al cliente Java manual.
"""
from __future__ import annotations

import argparse
import sys

from zeep import Client
from zeep.exceptions import Fault
from zeep.transports import Transport
from requests import Session


def build_client(wsdl: str) -> Client:
    session = Session()
    session.headers["User-Agent"] = "iac-zeep-client/1.0"
    return Client(wsdl, transport=Transport(session=session, timeout=20))


def main() -> int:
    parser = argparse.ArgumentParser(description="Cliente SOAP zeep (interoperabilidad)")
    parser.add_argument("--wsdl", default="http://localhost:5000/soap?wsdl")
    parser.add_argument("--correo", default="juan.pablo@udem.edu")
    parser.add_argument("--nombre", default="Juan Pablo")
    parser.add_argument("--apellidos", default="Ramos Salazar")
    parser.add_argument("--concept-id", type=int, default=None)
    parser.add_argument("--isbn", default=None)
    parser.add_argument("--modelo", default="PaaS")
    parser.add_argument(
        "--operacion",
        choices=["pendientes", "registrar", "progreso"],
        default="pendientes",
    )
    args = parser.parse_args()

    client = build_client(args.wsdl)
    print("Operaciones del WSDL:", list(client.wsdl.services.values())[0].ports)
    print("Servicio:", client.service)

    try:
        if args.operacion == "pendientes":
            result = client.service.ObtenerConceptosPendientes(
                correo=args.correo, tipoCliente="zeep-python"
            )
            print(result)
        elif args.operacion == "progreso":
            print(client.service.ObtenerProgresoUsuario(correo=args.correo))
        else:
            if args.concept_id is None or not args.isbn:
                print("registrar requiere --concept-id e --isbn", file=sys.stderr)
                return 2
            print(
                client.service.RegistrarClasificacion(
                    nombre=args.nombre,
                    apellidos=args.apellidos,
                    correo=args.correo,
                    conceptId=args.concept_id,
                    isbn=args.isbn,
                    modelo=args.modelo,
                    tipoCliente="zeep-python",
                )
            )
    except Fault as fault:
        print("SOAP Fault:", fault.message, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
