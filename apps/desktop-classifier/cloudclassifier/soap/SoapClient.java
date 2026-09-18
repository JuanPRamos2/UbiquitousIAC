package cloudclassifier.soap;

import org.w3c.dom.Document;
import org.w3c.dom.Element;
import org.w3c.dom.Node;
import org.w3c.dom.NodeList;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import javax.xml.transform.OutputKeys;
import javax.xml.transform.Transformer;
import javax.xml.transform.TransformerFactory;
import javax.xml.transform.dom.DOMSource;
import javax.xml.transform.stream.StreamResult;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * Cliente SOAP de escritorio. Construye el Envelope con DOM (valores escapados)
 * y no conoce PostgreSQL.
 */
public final class SoapClient {
    private static final String SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/";
    private static final String TNS = "http://udem.edu.mx/iac/library-classifier";
    private static final String WSSE =
            "http://docs.oasis-open.org/wss/2004/01/oasis-200401-wss-wssecurity-secext-1.0.xsd";
    public static final String CLIENT_TYPE = "desktop-java";

    private final String endpoint;

    public SoapClient(String endpoint) {
        this.endpoint = endpoint;
    }

    public List<PendingConcept> obtenerConceptosPendientes(String correo) throws Exception {
        Document request = newEnvelope("ObtenerConceptosPendientes");
        Element op = operation(request);
        append(request, op, "correo", correo);
        append(request, op, "tipoCliente", CLIENT_TYPE);
        Document response = post("ObtenerConceptosPendientes", request);
        Element body = firstChild(response.getDocumentElement(), "Body");
        Element payload = firstChild(body, "ObtenerConceptosPendientesResponse");
        List<PendingConcept> result = new ArrayList<PendingConcept>();
        NodeList nodes = payload.getElementsByTagNameNS(TNS, "concepto");
        if (nodes.getLength() == 0) {
            nodes = payload.getElementsByTagName("concepto");
        }
        for (int i = 0; i < nodes.getLength(); i++) {
            Element item = (Element) nodes.item(i);
            result.add(new PendingConcept(
                    Integer.parseInt(childText(item, "conceptId")),
                    childText(item, "conceptName"),
                    childText(item, "definition"),
                    childText(item, "isbn"),
                    childText(item, "bookTitle"),
                    childText(item, "categoryName")
            ));
        }
        return result;
    }

    public String registrarClasificacion(String nombre, String apellidos, String correo,
                                         PendingConcept concept, String modelo) throws Exception {
        Document request = newEnvelope("RegistrarClasificacion");
        Element op = operation(request);
        append(request, op, "nombre", nombre);
        append(request, op, "apellidos", apellidos);
        append(request, op, "correo", correo);
        append(request, op, "conceptId", String.valueOf(concept.conceptId));
        append(request, op, "isbn", concept.isbn);
        append(request, op, "modelo", modelo);
        append(request, op, "tipoCliente", CLIENT_TYPE);
        Document response = post("RegistrarClasificacion", request);
        Element payload = firstChild(firstChild(response.getDocumentElement(), "Body"),
                "RegistrarClasificacionResponse");
        return childText(payload, "mensaje") + " (" + childText(payload, "modelo")
                + ", id=" + childText(payload, "clasificacionId") + ")";
    }

    public ProgressInfo obtenerProgreso(String correo) throws Exception {
        Document request = newEnvelope("ObtenerProgresoUsuario");
        Element op = operation(request);
        append(request, op, "correo", correo);
        Document response = post("ObtenerProgresoUsuario", request);
        Element payload = firstChild(firstChild(response.getDocumentElement(), "Body"),
                "ObtenerProgresoUsuarioResponse");
        return new ProgressInfo(
                childText(payload, "correo"),
                childText(payload, "nombreCompleto"),
                parseInt(childText(payload, "clasificados")),
                parseInt(childText(payload, "pendientes")),
                parseInt(childText(payload, "totalCatalogo"))
        );
    }

    public String lastXml = "";

    private Document newEnvelope(String operationName) throws Exception {
        Document doc = builder().newDocument();
        Element envelope = doc.createElementNS(SOAP_NS, "soap:Envelope");
        envelope.setAttribute("xmlns:soap", SOAP_NS);
        envelope.setAttribute("xmlns:tns", TNS);
        doc.appendChild(envelope);
        envelope.appendChild(doc.createElementNS(SOAP_NS, "soap:Header"));
        Element body = doc.createElementNS(SOAP_NS, "soap:Body");
        envelope.appendChild(body);
        Element op = doc.createElementNS(TNS, "tns:" + operationName);
        body.appendChild(op);
        return doc;
    }

    private Element operation(Document doc) {
        Element body = firstChild(doc.getDocumentElement(), "Body");
        return (Element) body.getFirstChild();
    }

    private void append(Document doc, Element parent, String name, String value) {
        Element child = doc.createElementNS(TNS, "tns:" + name);
        child.setTextContent(value == null ? "" : value);
        parent.appendChild(child);
    }

    private Document post(String action, Document request) throws Exception {
        byte[] payload = toBytes(request);
        lastXml = new String(payload, StandardCharsets.UTF_8);
        HttpURLConnection connection = (HttpURLConnection) new URL(endpoint).openConnection();
        connection.setRequestMethod("POST");
        connection.setDoOutput(true);
        connection.setConnectTimeout(8000);
        connection.setReadTimeout(15000);
        connection.setRequestProperty("Content-Type", "text/xml; charset=utf-8");
        connection.setRequestProperty("SOAPAction", TNS + "/" + action);
        OutputStream output = connection.getOutputStream();
        try {
            output.write(payload);
        } finally {
            output.close();
        }
        int status = connection.getResponseCode();
        InputStream stream = status >= 400 ? connection.getErrorStream() : connection.getInputStream();
        if (stream == null) {
            throw new SoapFaultException(status, "soap:Server",
                    "El servicio SOAP no devolvió contenido.");
        }
        byte[] responseBytes = readAll(stream);
        lastXml = lastXml + "\n\n----- RESPUESTA -----\n"
                + new String(responseBytes, StandardCharsets.UTF_8);
        Document response = builder().parse(new ByteArrayInputStream(responseBytes));
        Element fault = findFault(response);
        if (fault != null) {
            String message = childText(fault, "faultstring");
            String code = childText(fault, "faultcode");
            int http = status;
            String detailCode = childTextDeep(fault, "codigo");
            if (detailCode.length() > 0) {
                http = parseInt(detailCode);
            }
            throw new SoapFaultException(http, code, friendlyMessage(http, message));
        }
        if (status >= 400) {
            throw new SoapFaultException(status, "soap:Server",
                    "El servicio respondió con un error HTTP " + status + ".");
        }
        return response;
    }

    private String friendlyMessage(int http, String faultstring) {
        if (http == 409) {
            return "Este concepto ya está clasificado. Elige otro de la lista pendiente.";
        }
        if (http == 404) {
            return "Ese concepto no existe en el catálogo de la librería.";
        }
        if (http == 401) {
            return "No autorizado. Revisa las credenciales WS-Security.";
        }
        if (http >= 500) {
            return "El servicio no pudo completar la operación. Inténtalo más tarde.";
        }
        return faultstring == null || faultstring.isEmpty()
                ? "La solicitud SOAP no es válida."
                : faultstring;
    }

    private Element findFault(Document document) {
        NodeList faults = document.getElementsByTagNameNS(SOAP_NS, "Fault");
        if (faults.getLength() > 0) {
            return (Element) faults.item(0);
        }
        faults = document.getElementsByTagName("Fault");
        return faults.getLength() > 0 ? (Element) faults.item(0) : null;
    }

    private Element firstChild(Element parent, String local) {
        NodeList children = parent.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node node = children.item(i);
            if (node instanceof Element && local.equals(node.getLocalName())) {
                return (Element) node;
            }
        }
        throw new IllegalStateException("No se encontró el elemento " + local);
    }

    private String childText(Element parent, String local) {
        NodeList children = parent.getChildNodes();
        for (int i = 0; i < children.getLength(); i++) {
            Node node = children.item(i);
            if (node instanceof Element && local.equals(node.getLocalName())) {
                String text = node.getTextContent();
                return text == null ? "" : text.trim();
            }
        }
        NodeList byTag = parent.getElementsByTagName(local);
        if (byTag.getLength() > 0) {
            String text = byTag.item(0).getTextContent();
            return text == null ? "" : text.trim();
        }
        return "";
    }

    private String childTextDeep(Element parent, String local) {
        NodeList nodes = parent.getElementsByTagName(local);
        if (nodes.getLength() == 0) {
            nodes = parent.getElementsByTagNameNS("*", local);
        }
        if (nodes.getLength() == 0) {
            return "";
        }
        String text = nodes.item(0).getTextContent();
        return text == null ? "" : text.trim();
    }

    private int parseInt(String value) {
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException ex) {
            return 0;
        }
    }

    private byte[] toBytes(Document document) throws Exception {
        Transformer transformer = TransformerFactory.newInstance().newTransformer();
        transformer.setOutputProperty(OutputKeys.ENCODING, "UTF-8");
        transformer.setOutputProperty(OutputKeys.INDENT, "yes");
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        transformer.transform(new DOMSource(document), new StreamResult(buffer));
        return buffer.toByteArray();
    }

    private byte[] readAll(InputStream stream) throws Exception {
        ByteArrayOutputStream buffer = new ByteArrayOutputStream();
        byte[] chunk = new byte[4096];
        int read;
        while ((read = stream.read(chunk)) != -1) {
            buffer.write(chunk, 0, read);
        }
        return buffer.toByteArray();
    }

    private DocumentBuilder builder() throws Exception {
        DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
        factory.setNamespaceAware(true);
        return factory.newDocumentBuilder();
    }
}
