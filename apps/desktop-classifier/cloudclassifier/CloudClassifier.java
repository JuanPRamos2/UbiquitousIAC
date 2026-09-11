package cloudclassifier;

import cloudclassifier.classifier.ClassificationResult;
import cloudclassifier.classifier.ClassifierService;
import cloudclassifier.classifier.CloudModel;
import cloudclassifier.util.InvalidInputException;

/**
 * Interfaz de línea de comandos (Parte 6).
 * Reutiliza ClassifierService, la misma lógica que la GUI.
 *
 * Ejemplos:
 *   java cloudclassifier.CloudClassifier "máquinas virtuales almacenamiento redes"
 *   java cloudclassifier.CloudClassifier --regex "desplegar mi aplicación web"
 *   java cloudclassifier.CloudClassifier --nlp --nombre Ana --apellido Pérez --texto "..."
 */
public final class CloudClassifier {
    public static void main(String[] args) {
        try {
            CliRequest request = CliRequest.parse(args);
            ClassifierService service = new ClassifierService();
            ClassificationResult result = service.classify(
                    request.firstName, request.lastName, request.text, request.engine);
            System.out.println("Modelo identificado: " + result.getModel().getAcronym());
            if (request.verbose) {
                printVerbose(result);
            }
        } catch (IllegalArgumentException ex) {
            System.err.println(ex.getMessage());
            printUsage();
            System.exit(1);
        } catch (InvalidInputException ex) {
            System.err.println("Error de validación: " + ex.getMessage());
            System.exit(1);
        } catch (Exception ex) {
            System.err.println("Error inesperado: " + ex.getMessage());
            System.exit(1);
        }
    }

    private static void printVerbose(ClassificationResult result) {
        System.out.println("Usuario: " + result.getFullUserName());
        System.out.println("Motor: " + result.getEngineName());
        System.out.println("Descripción: " + result.getOriginalText());
        for (CloudModel model : result.getScores().keySet()) {
            System.out.println("  " + model.getAcronym() + ": " + result.getScore(model) + " pts");
        }
        System.out.println(result.getExplanation());
    }

    private static void printUsage() {
        System.err.println("Uso:");
        System.err.println("  java cloudclassifier.CloudClassifier \"descripción del servicio\"");
        System.err.println("  java cloudclassifier.CloudClassifier [--regex|--nlp] [--verbose] \"texto\"");
        System.err.println("  java cloudclassifier.CloudClassifier --nombre Ana --apellido Perez --texto \"...\"");
    }

    private static final class CliRequest {
        private String firstName = "Estudiante";
        private String lastName = "CLI";
        private String text;
        private ClassifierService.EngineType engine = ClassifierService.EngineType.NLP;
        private boolean verbose;

        static CliRequest parse(String[] args) {
            if (args == null || args.length == 0) {
                throw new IllegalArgumentException("Falta la descripción a clasificar.");
            }
            CliRequest request = new CliRequest();
            for (int i = 0; i < args.length; i++) {
                String arg = args[i];
                if ("--regex".equals(arg)) {
                    request.engine = ClassifierService.EngineType.REGEX;
                } else if ("--nlp".equals(arg)) {
                    request.engine = ClassifierService.EngineType.NLP;
                } else if ("--verbose".equals(arg) || "-v".equals(arg)) {
                    request.verbose = true;
                } else if ("--nombre".equals(arg)) {
                    request.firstName = requireValue(args, ++i, "--nombre");
                } else if ("--apellido".equals(arg)) {
                    request.lastName = requireValue(args, ++i, "--apellido");
                } else if ("--texto".equals(arg) || "--text".equals(arg)) {
                    request.text = requireValue(args, ++i, "--texto");
                } else if (arg.startsWith("-")) {
                    throw new IllegalArgumentException("Opción no reconocida: " + arg);
                } else if (request.text == null) {
                    request.text = arg;
                } else {
                    request.text = request.text + " " + arg;
                }
            }
            if (request.text == null || request.text.trim().isEmpty()) {
                throw new IllegalArgumentException("Falta la descripción a clasificar.");
            }
            return request;
        }

        private static String requireValue(String[] args, int index, String flag) {
            if (index >= args.length) {
                throw new IllegalArgumentException("La opción " + flag + " necesita un valor.");
            }
            return args[index];
        }
    }
}
