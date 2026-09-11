package cloudclassifier.soap;

public final class ProgressInfo {
    public final String correo;
    public final String nombreCompleto;
    public final int clasificados;
    public final int pendientes;
    public final int totalCatalogo;

    public ProgressInfo(String correo, String nombreCompleto, int clasificados,
                        int pendientes, int totalCatalogo) {
        this.correo = correo;
        this.nombreCompleto = nombreCompleto;
        this.clasificados = clasificados;
        this.pendientes = pendientes;
        this.totalCatalogo = totalCatalogo;
    }
}
