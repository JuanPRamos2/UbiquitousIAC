# Cliente de interoperabilidad (Python / zeep)

El servidor SOAP está escrito a mano con Flask + `xml.etree`.
Este cliente **no** construye el Envelope: zeep lo genera a partir del WSDL.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# El servicio Flask debe estar en ejecución
python cliente_zeep.py --wsdl http://localhost:5000/soap?wsdl --operacion pendientes
python cliente_zeep.py --operacion registrar --concept-id 1 --isbn 9780132350884 --modelo IaaS
python cliente_zeep.py --operacion progreso
```

Comparación breve:

| Aspecto | Cliente Java (manual) | Cliente zeep |
| --- | --- | --- |
| Construcción XML | DOM en `SoapClient.java` | Automática desde el WSDL |
| Conocimiento interno | Solo el contrato | Solo el contrato |
| Lenguaje | Java | Python |
