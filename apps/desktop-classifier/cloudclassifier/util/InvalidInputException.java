package cloudclassifier.util;

/**
 * Error de validación de entradas (nombre, apellido o descripción vacíos/inválidos).
 */
public class InvalidInputException extends Exception {
    public InvalidInputException(String message) {
        super(message);
    }
}
