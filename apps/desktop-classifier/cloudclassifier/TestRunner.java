package cloudclassifier;

import cloudclassifier.classifier.ClassificationResult;
import cloudclassifier.classifier.ClassifierService;
import cloudclassifier.classifier.CloudModel;
import cloudclassifier.util.InvalidInputException;

/**
 * Ejecuta los casos de prueba del ejercicio y muestra la tabla:
 * Entrada → Esperada → Obtenida → ¿Correcta?
 */
public final class TestRunner {
    private static final String[][] CASES = new String[][] {
            {
                    "Necesito máquinas virtuales, almacenamiento y redes configurables para instalar mi propio sistema operativo.",
                    "IaaS"
            },
            {
                    "Quiero desplegar mi aplicación web sin administrar directamente servidores ni sistemas operativos.",
                    "PaaS"
            },
            {
                    "Los empleados utilizan una aplicación de correo electrónico directamente desde el navegador y pagan una suscripción mensual.",
                    "SaaS"
            },
            {
                    "Necesito ejecutar una función automáticamente cada vez que un usuario suba una imagen al almacenamiento Cloud.",
                    "FaaS"
            },
            {
                    "Voy a contratar instancias en Amazon EC2 con discos persistentes y una red privada virtual para instalar Linux.",
                    "IaaS"
            },
            {
                    "Usaré Google App Engine o Heroku para publicar mi API sin configurar el sistema operativo.",
                    "PaaS"
            }
    };

    public static void main(String[] args) {
        ClassifierService service = new ClassifierService();
        runSuite("REGEX", service, ClassifierService.EngineType.REGEX);
        System.out.println();
        runSuite("NLP", service, ClassifierService.EngineType.NLP);
    }

    private static void runSuite(String label, ClassifierService service, ClassifierService.EngineType engine) {
        System.out.println("=== Casos de prueba (" + label + ") ===");
        int passed = 0;
        for (int i = 0; i < CASES.length; i++) {
            String input = CASES[i][0];
            String expected = CASES[i][1];
            String obtained;
            try {
                ClassificationResult result = service.classifyText(input, engine);
                obtained = result.getModel().getAcronym();
                if (result.getModel() == CloudModel.INDETERMINADO) {
                    obtained = "Indeterminado";
                }
            } catch (InvalidInputException ex) {
                obtained = "ERROR: " + ex.getMessage();
            }
            boolean ok = expected.equals(obtained);
            if (ok) {
                passed++;
            }
            System.out.println("Caso " + (i + 1) + ": " + (ok ? "CORRECTA" : "INCORRECTA"));
            System.out.println("  Entrada: " + input);
            System.out.println("  Esperada: " + expected + " → Obtenida: " + obtained);
        }
        System.out.println("Resumen " + label + ": " + passed + "/" + CASES.length + " correctas");
    }
}
