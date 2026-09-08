package cloudclassifier.util;

import java.util.regex.Pattern;

/**
 * Validación de entradas. Se mantiene fuera de la GUI para reutilizarla en la CLI.
 */
public final class InputValidator {
    private static final Pattern NAME_PATTERN =
            Pattern.compile("^[\\p{L}]+([ '\\-][\\p{L}]+)*$", Pattern.UNICODE_CHARACTER_CLASS);
    private static final Pattern EMAIL_PATTERN =
            Pattern.compile("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$");

    private static final int MIN_DESCRIPTION_LENGTH = 8;
    private static final int MAX_DESCRIPTION_LENGTH = 2000;
    private static final int MAX_NAME_LENGTH = 40;

    private InputValidator() {
    }

    public static String requireName(String value, String fieldLabel) throws InvalidInputException {
        String trimmed = safeTrim(value);
        if (trimmed.isEmpty()) {
            throw new InvalidInputException("El campo \"" + fieldLabel + "\" no puede estar vacío.");
        }
        if (trimmed.length() < 2) {
            throw new InvalidInputException("El campo \"" + fieldLabel + "\" es demasiado corto.");
        }
        if (trimmed.length() > MAX_NAME_LENGTH) {
            throw new InvalidInputException("El campo \"" + fieldLabel + "\" es demasiado largo.");
        }
        if (!NAME_PATTERN.matcher(trimmed).matches()) {
            throw new InvalidInputException(
                    "El campo \"" + fieldLabel + "\" solo admite letras, espacios, apóstrofos o guiones.");
        }
        return trimmed;
    }

    public static String requireDescription(String value) throws InvalidInputException {
        String trimmed = safeTrim(value);
        if (trimmed.isEmpty()) {
            throw new InvalidInputException("La descripción del servicio Cloud no puede estar vacía.");
        }
        if (trimmed.length() < MIN_DESCRIPTION_LENGTH) {
            throw new InvalidInputException(
                    "Escribe una descripción más completa (mínimo " + MIN_DESCRIPTION_LENGTH + " caracteres).");
        }
        if (trimmed.length() > MAX_DESCRIPTION_LENGTH) {
            throw new InvalidInputException("La descripción supera el máximo permitido.");
        }
        return trimmed;
    }

    public static String requireEmail(String value) throws InvalidInputException {
        String trimmed = safeTrim(value);
        if (trimmed.isEmpty()) {
            throw new InvalidInputException("El correo no puede estar vacío.");
        }
        if (!EMAIL_PATTERN.matcher(trimmed).matches()) {
            throw new InvalidInputException("El correo no tiene un formato válido.");
        }
        return trimmed.toLowerCase();
    }

    private static String safeTrim(String value) {
        return value == null ? "" : value.trim();
    }
}
