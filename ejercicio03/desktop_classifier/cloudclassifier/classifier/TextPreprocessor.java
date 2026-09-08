package cloudclassifier.classifier;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.Collections;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

/**
 * Pipeline NLP básico pedido en la Parte 5:
 * minúsculas → limpieza → normalización (sin acentos) → tokenización →
 * stopwords → stemming sencillo en español.
 *
 * No usa un LLM: solo prepara el texto para asignar puntuaciones por categoría.
 */
public final class TextPreprocessor {
    private static final Set<String> STOPWORDS = new HashSet<String>(Arrays.asList(
            "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a",
            "y", "o", "u", "en", "por", "para", "con", "sin", "ni", "que", "se", "su", "sus",
            "mi", "mis", "tu", "tus", "lo", "le", "les", "es", "son", "ser", "como", "mas",
            "más", "cuando", "donde", "qué", "cual", "cuál", "este", "esta", "estos", "estas",
            "eso", "esa", "me", "te", "nos", "ya", "muy", "pero", "si", "sí", "no", "también",
            "the", "a", "an", "of", "to", "and", "or", "for", "with", "from", "on", "in", "at",
            "my", "your", "our", "is", "are", "be", "when", "that", "this", "it",
            "necesito", "quiero", "puedo", "puede", "pueden", "utilizar", "utilizan", "usar",
            "tengo", "tiene", "hacen", "hacer", "desde", "cada", "vez", "propio", "propia"
    ));

    private TextPreprocessor() {
    }

    public static ProcessedText process(String rawText) {
        String lower = rawText.toLowerCase(Locale.ROOT);
        String normalized = stripAccents(lower);
        String cleaned = normalized.replaceAll("[^a-z0-9\\s]", " ");
        cleaned = cleaned.replaceAll("\\s+", " ").trim();

        List<String> tokens = new ArrayList<String>();
        if (!cleaned.isEmpty()) {
            Collections.addAll(tokens, cleaned.split(" "));
        }

        List<String> withoutStopwords = new ArrayList<String>();
        for (String token : tokens) {
            if (token.length() <= 1 || STOPWORDS.contains(token)) {
                continue;
            }
            withoutStopwords.add(token);
        }

        List<String> stems = new ArrayList<String>();
        for (String token : withoutStopwords) {
            stems.add(stemSpanish(token));
        }

        return new ProcessedText(rawText, lower, normalized, cleaned, tokens, withoutStopwords, stems);
    }

    /**
     * Normalización: "máquinas" y "maquinas" quedan iguales al quitar acentos.
     */
    public static String stripAccents(String text) {
        String decomposed = Normalizer.normalize(text, Normalizer.Form.NFD);
        return decomposed.replaceAll("\\p{M}+", "");
    }

    /**
     * Stemming conservador. No es Snowball completo: solo recorta sufijos frecuentes
     * para que "virtuales", "función" y "funciones" coincidan con las mismas reglas.
     */
    static String stemSpanish(String token) {
        String word = token;
        if (word.length() <= 3) {
            return word;
        }
        word = replaceSuffix(word, "aciones", "ar");
        word = replaceSuffix(word, "iciones", "ir");
        word = replaceSuffix(word, "amente", "");
        word = replaceSuffix(word, "mente", "");
        word = replaceSuffix(word, "aciones", "");
        word = replaceSuffix(word, "cion", "");
        word = replaceSuffix(word, "sion", "");
        word = replaceSuffix(word, "ando", "");
        word = replaceSuffix(word, "iendo", "");
        word = replaceSuffix(word, "ando", "");
        if (word.endsWith("es") && word.length() > 4) {
            word = word.substring(0, word.length() - 2);
        } else if (word.endsWith("s") && word.length() > 3 && !word.endsWith("us") && !word.endsWith("is")) {
            word = word.substring(0, word.length() - 1);
        }
        if (word.length() > 4 && (word.endsWith("ar") || word.endsWith("er") || word.endsWith("ir"))) {
            word = word.substring(0, word.length() - 2);
        }
        return word;
    }

    private static String replaceSuffix(String word, String suffix, String replacement) {
        if (word.endsWith(suffix) && word.length() - suffix.length() >= 3) {
            return word.substring(0, word.length() - suffix.length()) + replacement;
        }
        return word;
    }

    /**
     * Contenedor inmutable con cada etapa del pipeline, útil para explicar el NLP en clase.
     */
    public static final class ProcessedText {
        private final String original;
        private final String lowercased;
        private final String normalized;
        private final String cleaned;
        private final List<String> tokens;
        private final List<String> withoutStopwords;
        private final List<String> stems;

        ProcessedText(String original, String lowercased, String normalized, String cleaned,
                      List<String> tokens, List<String> withoutStopwords, List<String> stems) {
            this.original = original;
            this.lowercased = lowercased;
            this.normalized = normalized;
            this.cleaned = cleaned;
            this.tokens = Collections.unmodifiableList(tokens);
            this.withoutStopwords = Collections.unmodifiableList(withoutStopwords);
            this.stems = Collections.unmodifiableList(stems);
        }

        public String getOriginal() {
            return original;
        }

        public String getLowercased() {
            return lowercased;
        }

        public String getNormalized() {
            return normalized;
        }

        public String getCleaned() {
            return cleaned;
        }

        public List<String> getTokens() {
            return tokens;
        }

        public List<String> getWithoutStopwords() {
            return withoutStopwords;
        }

        public List<String> getStems() {
            return stems;
        }

        public boolean containsStem(String stem) {
            return stems.contains(stem);
        }

        public String joinedStems() {
            StringBuilder builder = new StringBuilder();
            for (int i = 0; i < stems.size(); i++) {
                if (i > 0) {
                    builder.append(' ');
                }
                builder.append(stems.get(i));
            }
            return builder.toString();
        }
    }
}
