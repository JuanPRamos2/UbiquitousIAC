package cloudclassifier.classifier;

import cloudclassifier.util.InputValidator;
import cloudclassifier.util.InvalidInputException;

/**
 * Fachada usada por la GUI y la CLI.
 * Aquí vive la validación y la selección del motor; la ventana Swing no clasifica nada.
 */
public final class ClassifierService {
    public enum EngineType {
        REGEX,
        NLP
    }

    private final RegexClassifier regexClassifier = new RegexClassifier();
    private final NlpClassifier nlpClassifier = new NlpClassifier();

    public ClassificationResult classify(String firstName, String lastName, String description,
                                         EngineType engineType) throws InvalidInputException {
        String name = InputValidator.requireName(firstName, "Nombre");
        String surname = InputValidator.requireName(lastName, "Apellido");
        String text = InputValidator.requireDescription(description);
        String fullName = name + " " + surname;

        CloudClassifierEngine engine = engineType == EngineType.REGEX ? regexClassifier : nlpClassifier;
        try {
            return engine.classify(fullName, text);
        } catch (RuntimeException ex) {
            throw new InvalidInputException("No se pudo analizar el texto: " + ex.getMessage());
        }
    }

    public ClassificationResult classifyText(String description, EngineType engineType)
            throws InvalidInputException {
        return classify("Estudiante", "CLI", description, engineType);
    }
}
