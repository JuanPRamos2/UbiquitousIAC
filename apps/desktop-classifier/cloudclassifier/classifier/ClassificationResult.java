package cloudclassifier.classifier;

import java.util.Collections;
import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Resultado de una clasificación: modelo ganador, puntuaciones y explicación.
 * GUI y CLI muestran esta misma estructura; no duplican la lógica.
 */
public final class ClassificationResult {
    private final String fullUserName;
    private final String originalText;
    private final CloudModel model;
    private final Map<CloudModel, Integer> scores;
    private final String explanation;
    private final String engineName;

    public ClassificationResult(String fullUserName, String originalText, CloudModel model,
                                Map<CloudModel, Integer> scores, String explanation, String engineName) {
        this.fullUserName = fullUserName;
        this.originalText = originalText;
        this.model = model;
        this.scores = Collections.unmodifiableMap(new LinkedHashMap<CloudModel, Integer>(scores));
        this.explanation = explanation;
        this.engineName = engineName;
    }

    public String getFullUserName() {
        return fullUserName;
    }

    public String getOriginalText() {
        return originalText;
    }

    public CloudModel getModel() {
        return model;
    }

    public Map<CloudModel, Integer> getScores() {
        return scores;
    }

    public String getExplanation() {
        return explanation;
    }

    public String getEngineName() {
        return engineName;
    }

    public int getScore(CloudModel model) {
        Integer value = scores.get(model);
        return value == null ? 0 : value.intValue();
    }
}
