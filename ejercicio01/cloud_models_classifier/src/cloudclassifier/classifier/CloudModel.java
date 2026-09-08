package cloudclassifier.classifier;

/**
 * Modelos de servicio Cloud que el clasificador puede identificar.
 * El valor INDETERMINADO se usa cuando no hay evidencia suficiente o hay empate.
 */
public enum CloudModel {
    IAAS("IaaS", "Infrastructure as a Service",
            "El proveedor ofrece recursos de infraestructura: máquinas virtuales, redes y almacenamiento."),
    PAAS("PaaS", "Platform as a Service",
            "El proveedor ofrece una plataforma para desplegar aplicaciones sin administrar servidores."),
    SAAS("SaaS", "Software as a Service",
            "El usuario consume software listo a través de internet, normalmente con una suscripción."),
    FAAS("FaaS", "Function as a Service",
            "Se ejecutan funciones pequeñas en respuesta a eventos, sin mantener servidores encendidos."),
    INDETERMINADO("Indeterminado", "No clasificado",
            "El texto no contiene evidencia suficiente o varios modelos empataron.");

    private final String acronym;
    private final String fullName;
    private final String description;

    CloudModel(String acronym, String fullName, String description) {
        this.acronym = acronym;
        this.fullName = fullName;
        this.description = description;
    }

    public String getAcronym() {
        return acronym;
    }

    public String getFullName() {
        return fullName;
    }

    public String getDescription() {
        return description;
    }
}
