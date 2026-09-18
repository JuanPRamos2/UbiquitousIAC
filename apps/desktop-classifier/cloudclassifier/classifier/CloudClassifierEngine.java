package cloudclassifier.classifier;

/**
 * Contrato común de los motores de clasificación.
 * Tanto RegexClassifier como NlpClassifier implementan este interfaz,
 * de modo que GUI y CLI pueden cambiar de motor sin cambiar su código.
 */
public interface CloudClassifierEngine {
    String getName();

    ClassificationResult classify(String fullUserName, String text);
}
