package cloudclassifier.classifier;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Primera versión del clasificador (Partes 1-4): palabras clave y expresiones regulares.
 * Cada categoría tiene su propio método para facilitar la explicación en clase.
 */
public final class RegexClassifier implements CloudClassifierEngine {
    private static final int FLAGS = Pattern.CASE_INSENSITIVE | Pattern.UNICODE_CASE;

    private static final Pattern[] IAAS_PATTERNS = new Pattern[] {
            Pattern.compile("maquinas?\\s+virtuales?", FLAGS),
            Pattern.compile("\\b(vm|ec2|vpc)\\b", FLAGS),
            Pattern.compile("compute\\s+engine", FLAGS),
            Pattern.compile("azure\\s+vm", FLAGS),
            Pattern.compile("sistema\\s+operativo", FLAGS),
            Pattern.compile("\\b(infraestructura|instancias?|virtualizacion|hardware)\\b", FLAGS),
            Pattern.compile("\\b(almacenamiento|discos?|cpu|ram)\\b", FLAGS),
            Pattern.compile("\\bredes?\\b", FLAGS),
            Pattern.compile("\\bservidores?\\b", FLAGS)
    };

    private static final Pattern[] PAAS_PATTERNS = new Pattern[] {
            Pattern.compile("despleg(ar|ar|ando|ue)?", FLAGS),
            Pattern.compile("sin\\s+administrar", FLAGS),
            Pattern.compile("no\\s+administrar", FLAGS),
            Pattern.compile("aplicacion\\s+web", FLAGS),
            Pattern.compile("app\\s+engine", FLAGS),
            Pattern.compile("azure\\s+app", FLAGS),
            Pattern.compile("\\b(heroku|plataforma|runtime|beanstalk)\\b", FLAGS),
            Pattern.compile("entorno\\s+de\\s+(desarrollo|ejecucion)", FLAGS)
    };

    private static final Pattern[] SAAS_PATTERNS = new Pattern[] {
            Pattern.compile("correo\\s+electronico", FLAGS),
            Pattern.compile("\\b(gmail|dropbox|salesforce|outlook)\\b", FLAGS),
            Pattern.compile("google\\s+docs", FLAGS),
            Pattern.compile("office\\s*365", FLAGS),
            Pattern.compile("\\b(suscripcion|navegador)\\b", FLAGS),
            Pattern.compile("desde\\s+el\\s+navegador", FLAGS),
            Pattern.compile("software\\s+(listo|como\\s+servicio)", FLAGS),
            Pattern.compile("empleados\\s+utilizan", FLAGS)
    };

    private static final Pattern[] FAAS_PATTERNS = new Pattern[] {
            Pattern.compile("ejecutar\\s+una\\s+funcion", FLAGS),
            Pattern.compile("\\bfunciones?\\b", FLAGS),
            Pattern.compile("\\b(lambda|serverless)\\b", FLAGS),
            Pattern.compile("cloud\\s+functions?", FLAGS),
            Pattern.compile("azure\\s+functions?", FLAGS),
            Pattern.compile("cada\\s+vez\\s+que", FLAGS),
            Pattern.compile("en\\s+respuesta\\s+a", FLAGS),
            Pattern.compile("\\b(automaticamente|evento|trigger)\\b", FLAGS),
            Pattern.compile("suba\\s+una\\s+imagen", FLAGS)
    };

    @Override
    public String getName() {
        return "Regex + palabras clave";
    }

    @Override
    public ClassificationResult classify(String fullUserName, String text) {
        String normalized = TextPreprocessor.stripAccents(text);
        ScoreDetail iaas = scoreIaas(normalized);
        ScoreDetail paas = scorePaas(normalized);
        ScoreDetail saas = scoreSaas(normalized);
        ScoreDetail faas = scoreFaas(normalized);

        Map<CloudModel, Integer> scores = new LinkedHashMap<CloudModel, Integer>();
        scores.put(CloudModel.IAAS, Integer.valueOf(iaas.score));
        scores.put(CloudModel.PAAS, Integer.valueOf(paas.score));
        scores.put(CloudModel.SAAS, Integer.valueOf(saas.score));
        scores.put(CloudModel.FAAS, Integer.valueOf(faas.score));

        Winner winner = pickWinner(scores);
        String explanation = buildExplanation(winner, iaas, paas, saas, faas);
        return new ClassificationResult(fullUserName, text, winner.model, scores, explanation, getName());
    }

    /** Identifica evidencia de IaaS. No puntúa "servidores" si el usuario dice que NO quiere administrarlos. */
    ScoreDetail scoreIaas(String text) {
        ScoreDetail detail = matchPatterns(text, IAAS_PATTERNS, 2);
        if (avoidsManagingInfrastructure(text)) {
            detail = detail.withoutMatchesContaining("servidor", "sistema operativo", "redes");
        }
        return detail;
    }

    ScoreDetail scorePaas(String text) {
        ScoreDetail detail = matchPatterns(text, PAAS_PATTERNS, 3);
        if (avoidsManagingInfrastructure(text)) {
            detail = detail.plus("sin administrar infraestructura", 3);
        }
        return detail;
    }

    ScoreDetail scoreSaas(String text) {
        return matchPatterns(text, SAAS_PATTERNS, 3);
    }

    ScoreDetail scoreFaas(String text) {
        return matchPatterns(text, FAAS_PATTERNS, 3);
    }

    /**
     * Frases como "sin administrar servidores" describen PaaS, no IaaS.
     * Si no se filtra, "servidores" inflaría incorrectamente el puntaje de IaaS.
     */
    private boolean avoidsManagingInfrastructure(String text) {
        return Pattern.compile("sin\\s+administrar|no\\s+administrar", FLAGS).matcher(text).find();
    }

    private ScoreDetail matchPatterns(String text, Pattern[] patterns, int weight) {
        List<String> matches = new ArrayList<String>();
        int score = 0;
        for (int i = 0; i < patterns.length; i++) {
            Matcher matcher = patterns[i].matcher(text);
            if (matcher.find()) {
                String found = matcher.group();
                matches.add(found);
                score += weight;
            }
        }
        return new ScoreDetail(score, matches);
    }

    private Winner pickWinner(Map<CloudModel, Integer> scores) {
        int max = 0;
        for (Integer value : scores.values()) {
            if (value.intValue() > max) {
                max = value.intValue();
            }
        }
        if (max == 0) {
            return new Winner(CloudModel.INDETERMINADO, max, 0);
        }
        int ties = 0;
        CloudModel winner = CloudModel.INDETERMINADO;
        for (Map.Entry<CloudModel, Integer> entry : scores.entrySet()) {
            if (entry.getValue().intValue() == max) {
                ties++;
                winner = entry.getKey();
            }
        }
        if (ties > 1) {
            return new Winner(CloudModel.INDETERMINADO, max, ties);
        }
        return new Winner(winner, max, 1);
    }

    private String buildExplanation(Winner winner, ScoreDetail iaas, ScoreDetail paas,
                                    ScoreDetail saas, ScoreDetail faas) {
        StringBuilder builder = new StringBuilder();
        if (winner.model == CloudModel.INDETERMINADO && winner.max == 0) {
            builder.append("No se encontraron palabras clave ni patrones suficientes.");
            return builder.toString();
        }
        if (winner.model == CloudModel.INDETERMINADO) {
            builder.append("Hay empate entre dos o más modelos. Revisa las coincidencias.");
        } else {
            builder.append("Predomina ").append(winner.model.getAcronym())
                    .append(" porque acumuló más coincidencias.");
        }
        builder.append("\nIaaS: ").append(formatDetail(iaas));
        builder.append("\nPaaS: ").append(formatDetail(paas));
        builder.append("\nSaaS: ").append(formatDetail(saas));
        builder.append("\nFaaS: ").append(formatDetail(faas));
        return builder.toString();
    }

    private String formatDetail(ScoreDetail detail) {
        if (detail.matches.isEmpty()) {
            return detail.score + " pts (sin coincidencias)";
        }
        return detail.score + " pts — " + join(detail.matches);
    }

    private String join(List<String> values) {
        StringBuilder builder = new StringBuilder();
        for (int i = 0; i < values.size(); i++) {
            if (i > 0) {
                builder.append(", ");
            }
            builder.append(values.get(i));
        }
        return builder.toString();
    }

    static final class ScoreDetail {
        final int score;
        final List<String> matches;

        ScoreDetail(int score, List<String> matches) {
            this.score = score;
            this.matches = matches;
        }

        ScoreDetail plus(String label, int extra) {
            List<String> copy = new ArrayList<String>(matches);
            copy.add(label);
            return new ScoreDetail(score + extra, copy);
        }

        ScoreDetail withoutMatchesContaining(String... fragments) {
            List<String> filtered = new ArrayList<String>();
            int removed = 0;
            for (String match : matches) {
                String lower = match.toLowerCase();
                boolean drop = false;
                for (String fragment : fragments) {
                    if (lower.contains(fragment)) {
                        drop = true;
                        break;
                    }
                }
                if (drop) {
                    removed++;
                } else {
                    filtered.add(match);
                }
            }
            int newScore = Math.max(0, score - (removed * 2));
            return new ScoreDetail(newScore, filtered);
        }
    }

    private static final class Winner {
        final CloudModel model;
        final int max;
        final int ties;

        Winner(CloudModel model, int max, int ties) {
            this.model = model;
            this.max = max;
            this.ties = ties;
        }
    }
}
