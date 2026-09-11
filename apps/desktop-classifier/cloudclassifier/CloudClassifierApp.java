package cloudclassifier;

import cloudclassifier.gui.ClassifierWindow;

import javax.swing.SwingUtilities;
import javax.swing.UIManager;

/**
 * Punto de entrada de la aplicación de escritorio (Partes 1 y 2).
 * Si se pasan argumentos, delega a la CLI para no duplicar puntos de entrada.
 */
public final class CloudClassifierApp {
    public static void main(final String[] args) {
        if (args != null && args.length > 0) {
            CloudClassifier.main(args);
            return;
        }
        SwingUtilities.invokeLater(new Runnable() {
            @Override
            public void run() {
                try {
                    UIManager.setLookAndFeel("javax.swing.plaf.nimbus.NimbusLookAndFeel");
                } catch (Exception ignored) {
                    // Si Nimbus no está disponible se usa el look and feel por defecto.
                }
                ClassifierWindow window = new ClassifierWindow();
                window.setVisible(true);
            }
        });
    }
}
