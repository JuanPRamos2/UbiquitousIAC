package cloudclassifier.classifier;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Segunda versión (Parte 5): NLP básico + puntuaciones.
 * Sigue usando métodos independientes por categoría, pero trabaja sobre tokens
 * y stems en lugar de buscar solo con Regex sobre el texto crudo.
 */
public final class NlpClassifier implements CloudClassifierEngine {
    private static final List<String> IAAS_STEMS = Arrays.asList(
            "maquina", "virtual", "vm", "ec2", "vpc", "infraestructur", "instancia",
            "almacen", "disco", "red", "hardware", "cpu", "ram", "linux", "compute",
            "virtualiz"
    );
    private static final List<String> PAAS_STEMS = Arrays.asList(
            "despleg", "plataforma", "heroku", "runtime", "beanstalk", "paas",
            "framework", "pipeline", "buildpack"
    );
    private static final List<String> SAAS_STEMS = Arrays.asList(
            "correo", "gmail", "dropbox", "salesforce", "outlook", "suscrip",
            "navegador", "office", "docs", "saas", "software"
    );
    private static final List<String> FAAS_STEMS = Arrays.asList(
            "funcion", "lambda", "serverless", "evento", "trigger", "faas",
            "automatic", "webhook"
    );

    @Override
    public String getName() {
        return "NLP básico + puntuaciones";
    }

    @Override
    public ClassificationResult classify(String fullUserName, String text) {
        TextPreprocessor.ProcessedText processed = TextPreprocessor.process(text);

        CategoryScore iaas = scoreIaas(processed);
        CategoryScore paas = scorePaas(processed);
        CategoryScore saas = scoreSaas(processed);
        CategoryScore faas = scoreFaas(processed);

        Map<CloudModel, Integer> scores = new LinkedHashMap<CloudModel, Integer>();
        scores.put(CloudModel.IAAS, Integer.valueOf(iaas.score));
        scores.put(CloudModel.PAAS, Integer.valueOf(paas.score));
        scores.put(CloudModel.SAAS, Integer.valueOf(saas.score));
        scores.put(CloudModel.FAAS, Integer.valueOf(faas.score));

        CloudModel winner = pickWinner(scores);
        String explanation = buildExplanation(processed, winner, iaas, paas, saas, faas);
        return new ClassificationResult(fullUserName, text, winner, scores, explanation, getName());
    }

    CategoryScore scoreIaas(TextPreprocessor.ProcessedText processed) {
        CategoryScore score = scoreStems(processed, IAAS_STEMS);
        score = addPhrase(score, processed, "maquina virtual", 4);
        score = addPhrase(score, processed, "sistema operativo", 3);
        score = addPhrase(score, processed, "compute engine", 4);
        if (avoidsManaging(processed)) {
            score = score.without("servidor", "operativo");
        } else {
            score = addIfPresent(score, processed, "servidor", 2);
        }
        return score;
    }

    CategoryScore scorePaas(TextPreprocessor.ProcessedText processed) {
        CategoryScore score = scoreStems(processed, PAAS_STEMS);
        score = addPhrase(score, processed, "app engine", 4);
        score = addPhrase(score, processed, "aplicacion web", 2);
        score = addPhrase(score, processed, "azure app", 3);
        if (avoidsManaging(processed)) {
            score = score.plus("no administrar servidores/SO", 4);
        }
        return score;
    }

    CategoryScore scoreSaas(TextPreprocessor.ProcessedText processed) {
        CategoryScore score = scoreStems(processed, SAAS_STEMS);
        score = addPhrase(score, processed, "correo electronico", 4);
        score = addPhrase(score, processed, "google docs", 4);
        score = addPhrase(score, processed, "office 365", 4);
        return score;
    }

    CategoryScore scoreFaas(TextPreprocessor.ProcessedText processed) {
        CategoryScore score = scoreStems(processed, FAAS_STEMS);
        score = addPhrase(score, processed, "ejecut funcion", 4);
        score = addPhrase(score, processed, "cloud function", 4);
        score = addPhrase(score, processed, "azure function", 4);
        if (processed.getCleaned().contains("suba") || processed.containsStem("sub")) {
            score = score.plus("evento al subir archivo", 3);
        }
        return score;
    }

    private boolean avoidsManaging(TextPreprocessor.ProcessedText processed) {
        String cleaned = processed.getCleaned();
        return cleaned.contains("sin administrar") || cleaned.contains("no administrar");
    }

    private CategoryScore scoreStems(TextPreprocessor.ProcessedText processed, List<String> categoryStems) {
        List<String> hits = new ArrayList<String>();
        int score = 0;
        for (String stem : processed.getStems()) {
            for (String expected : categoryStems) {
                if (stem.equals(expected) || stem.startsWith(expected) || expected.startsWith(stem) && stem.length() >= 4) {
                    if (!hits.contains(stem)) {
                        hits.add(stem);
                        score += 2;
                    }
                }
            }
        }
        return new CategoryScore(score, hits);
    }

    private CategoryScore addPhrase(CategoryScore current, TextPreprocessor.ProcessedText processed,
                                    String phrase, int weight) {
        String haystack = processed.getCleaned() + " " + processed.joinedStems();
        String needle = TextPreprocessor.stripAccents(phrase);
        if (haystack.contains(needle)) {
            return current.plus(phrase, weight);
        }
        return current;
    }

    private CategoryScore addIfPresent(CategoryScore current, TextPreprocessor.ProcessedText processed,
                                       String stem, int weight) {
        if (processed.containsStem(stem) || processed.joinedStems().contains(stem)) {
            return current.plus(stem, weight);
        }
        return current;
    }

    private CloudModel pickWinner(Map<CloudModel, Integer> scores) {
        int max = 0;
        for (Integer value : scores.values()) {
            if (value.intValue() > max) {
                max = value.intValue();
            }
        }
        if (max == 0) {
            return CloudModel.INDETERMINADO;
        }
        CloudModel winner = CloudModel.INDETERMINADO;
        int ties = 0;
        for (Map.Entry<CloudModel, Integer> entry : scores.entrySet()) {
            if (entry.getValue().intValue() == max) {
                ties++;
                winner = entry.getKey();
            }
        }
        return ties > 1 ? CloudModel.INDETERMINADO : winner;
    }

    private String buildExplanation(TextPreprocessor.ProcessedText processed, CloudModel winner,
                                    CategoryScore iaas, CategoryScore paas,
                                    CategoryScore saas, CategoryScore faas) {
        StringBuilder builder = new StringBuilder();
        builder.append("Pipeline NLP: minúsculas → limpieza → tokens → stopwords → stems.\n");
        builder.append("Tokens: ").append(processed.getTokens()).append('\n');
        builder.append("Stems: ").append(processed.getStems()).append('\n');
        if (winner == CloudModel.INDETERMINADO) {
            builder.append("No hay un modelo predominante.\n");
        } else {
            builder.append("Predomina ").append(winner.getAcronym()).append(" por puntuación.\n");
        }
        builder.append("IaaS: ").append(iaas).append('\n');
        builder.append("PaaS: ").append(paas).append('\n');
        builder.append("SaaS: ").append(saas).append('\n');
        builder.append("FaaS: ").append(faas);
        return builder.toString();
    }

    static final class CategoryScore {
        final int score;
        final List<String> evidence;

        CategoryScore(int score, List<String> evidence) {
            this.score = score;
            this.evidence = evidence;
        }

        CategoryScore plus(String label, int extra) {
            List<String> copy = new ArrayList<String>(evidence);
            copy.add(label);
            return new CategoryScore(score + extra, copy);
        }

        CategoryScore without(String... fragments) {
            List<String> filtered = new ArrayList<String>();
            int removed = 0;
            for (String item : evidence) {
                boolean drop = false;
                for (int i = 0; i < fragments.length; i++) {
                    if (item.contains(fragments[i])) {
                        drop = true;
                        break;
                    }
                }
                if (drop) {
                    removed++;
                } else {
                    filtered.add(item);
                }
            }
            return new CategoryScore(Math.max(0, score - removed * 2), filtered);
        }

        @Override
        public String toString() {
            if (evidence.isEmpty()) {
                return score + " pts";
            }
            return score + " pts — " + evidence;
        }
    }
}
