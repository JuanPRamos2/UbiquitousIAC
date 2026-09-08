package cloudclassifier.gui;

import cloudclassifier.classifier.ClassificationResult;
import cloudclassifier.classifier.ClassifierService;
import cloudclassifier.classifier.CloudModel;
import cloudclassifier.util.InvalidInputException;

import javax.swing.BorderFactory;
import javax.swing.ButtonGroup;
import javax.swing.JButton;
import javax.swing.JFrame;
import javax.swing.JLabel;
import javax.swing.JOptionPane;
import javax.swing.JPanel;
import javax.swing.JProgressBar;
import javax.swing.JRadioButton;
import javax.swing.JScrollPane;
import javax.swing.JTextArea;
import javax.swing.JTextField;
import javax.swing.SwingConstants;
import java.awt.BorderLayout;
import java.awt.Color;
import java.awt.Dimension;
import java.awt.Font;
import java.awt.GridBagConstraints;
import java.awt.GridBagLayout;
import java.awt.Insets;
import java.awt.event.ActionEvent;
import java.awt.event.ActionListener;
import java.util.EnumMap;
import java.util.Map;

/**
 * Interfaz gráfica. Solo captura datos, llama a ClassifierService y muestra el resultado.
 * La clasificación vive en el paquete classifier, no en esta clase.
 */
public final class ClassifierWindow extends JFrame {
    private static final Color HEADER_BG = new Color(18, 52, 86);
    private static final Color IAAS = new Color(25, 118, 210);
    private static final Color PAAS = new Color(46, 125, 50);
    private static final Color SAAS = new Color(230, 126, 34);
    private static final Color FAAS = new Color(123, 31, 162);
    private static final Color UNKNOWN = new Color(97, 97, 97);

    private final ClassifierService service = new ClassifierService();

    private final JTextField firstNameField = new JTextField(16);
    private final JTextField lastNameField = new JTextField(16);
    private final JTextArea descriptionArea = new JTextArea(6, 40);
    private final JRadioButton regexRadio = new JRadioButton("Regex + palabras clave");
    private final JRadioButton nlpRadio = new JRadioButton("NLP básico");
    private final JLabel resultBadge = new JLabel("Sin clasificar", SwingConstants.CENTER);
    private final JLabel resultTitle = new JLabel("Escribe una descripción y pulsa Clasificar.");
    private final JTextArea explanationArea = new JTextArea(7, 40);
    private final Map<CloudModel, JProgressBar> scoreBars = new EnumMap<CloudModel, JProgressBar>(CloudModel.class);
    private final Map<CloudModel, JLabel> scoreLabels = new EnumMap<CloudModel, JLabel>(CloudModel.class);

    public ClassifierWindow() {
        super("cloud_models_classifier — Clasificador de modelos Cloud");
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(760, 720));
        setLocationRelativeTo(null);
        buildUi();
    }

    private void buildUi() {
        setLayout(new BorderLayout(0, 0));
        add(buildHeader(), BorderLayout.NORTH);
        add(buildForm(), BorderLayout.CENTER);
        add(buildResultPanel(), BorderLayout.SOUTH);
    }

    private JPanel buildHeader() {
        JPanel header = new JPanel(new BorderLayout());
        header.setBackground(HEADER_BG);
        header.setBorder(BorderFactory.createEmptyBorder(16, 20, 16, 20));

        JLabel title = new JLabel("Clasificador de modelos de servicio Cloud");
        title.setForeground(Color.WHITE);
        title.setFont(title.getFont().deriveFont(Font.BOLD, 22f));

        JLabel subtitle = new JLabel("SC3705 · IaaS  ·  PaaS  ·  SaaS  ·  FaaS");
        subtitle.setForeground(new Color(186, 210, 232));
        subtitle.setFont(subtitle.getFont().deriveFont(14f));

        header.add(title, BorderLayout.NORTH);
        header.add(subtitle, BorderLayout.SOUTH);
        return header;
    }

    private JPanel buildForm() {
        JPanel form = new JPanel(new GridBagLayout());
        form.setBorder(BorderFactory.createEmptyBorder(16, 20, 8, 20));
        GridBagConstraints c = new GridBagConstraints();
        c.insets = new Insets(4, 4, 4, 4);
        c.fill = GridBagConstraints.HORIZONTAL;
        c.anchor = GridBagConstraints.WEST;

        c.gridx = 0;
        c.gridy = 0;
        form.add(new JLabel("Nombre"), c);
        c.gridx = 1;
        form.add(firstNameField, c);
        c.gridx = 2;
        form.add(new JLabel("Apellido"), c);
        c.gridx = 3;
        form.add(lastNameField, c);

        descriptionArea.setLineWrap(true);
        descriptionArea.setWrapStyleWord(true);
        JScrollPane scroll = new JScrollPane(descriptionArea);
        scroll.setBorder(BorderFactory.createTitledBorder("Descripción del servicio Cloud"));
        c.gridx = 0;
        c.gridy = 1;
        c.gridwidth = 4;
        c.weightx = 1;
        c.weighty = 1;
        c.fill = GridBagConstraints.BOTH;
        form.add(scroll, c);

        ButtonGroup engines = new ButtonGroup();
        engines.add(regexRadio);
        engines.add(nlpRadio);
        nlpRadio.setSelected(true);
        JPanel enginePanel = new JPanel();
        enginePanel.add(new JLabel("Motor:"));
        enginePanel.add(regexRadio);
        enginePanel.add(nlpRadio);

        JButton classifyButton = new JButton("Clasificar");
        classifyButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                classify();
            }
        });
        JButton clearButton = new JButton("Limpiar");
        clearButton.addActionListener(new ActionListener() {
            @Override
            public void actionPerformed(ActionEvent e) {
                clearForm();
            }
        });

        JPanel actions = new JPanel(new BorderLayout());
        actions.add(enginePanel, BorderLayout.WEST);
        JPanel buttons = new JPanel();
        buttons.add(classifyButton);
        buttons.add(clearButton);
        actions.add(buttons, BorderLayout.EAST);

        c.gridy = 2;
        c.weighty = 0;
        c.fill = GridBagConstraints.HORIZONTAL;
        form.add(actions, c);
        return form;
    }

    private JPanel buildResultPanel() {
        JPanel result = new JPanel(new BorderLayout(8, 8));
        result.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createEmptyBorder(0, 20, 16, 20),
                BorderFactory.createTitledBorder("Resultado de la clasificación")));

        resultBadge.setOpaque(true);
        resultBadge.setBackground(UNKNOWN);
        resultBadge.setForeground(Color.WHITE);
        resultBadge.setFont(resultBadge.getFont().deriveFont(Font.BOLD, 20f));
        resultBadge.setPreferredSize(new Dimension(160, 72));
        resultBadge.setBorder(BorderFactory.createEmptyBorder(8, 12, 8, 12));

        resultTitle.setFont(resultTitle.getFont().deriveFont(Font.PLAIN, 14f));

        JPanel top = new JPanel(new BorderLayout(12, 8));
        top.add(resultBadge, BorderLayout.WEST);
        top.add(resultTitle, BorderLayout.CENTER);
        result.add(top, BorderLayout.NORTH);
        result.add(buildScorePanel(), BorderLayout.CENTER);

        explanationArea.setEditable(false);
        explanationArea.setLineWrap(true);
        explanationArea.setWrapStyleWord(true);
        explanationArea.setBackground(new Color(248, 249, 250));
        JScrollPane explanationScroll = new JScrollPane(explanationArea);
        explanationScroll.setPreferredSize(new Dimension(700, 130));
        explanationScroll.setBorder(BorderFactory.createTitledBorder("Evidencia y explicación"));
        result.add(explanationScroll, BorderLayout.SOUTH);
        return result;
    }

    private JPanel buildScorePanel() {
        JPanel panel = new JPanel(new GridBagLayout());
        GridBagConstraints c = new GridBagConstraints();
        c.insets = new Insets(3, 4, 3, 4);
        c.fill = GridBagConstraints.HORIZONTAL;
        CloudModel[] models = new CloudModel[] {CloudModel.IAAS, CloudModel.PAAS, CloudModel.SAAS, CloudModel.FAAS};
        for (int i = 0; i < models.length; i++) {
            CloudModel model = models[i];
            JLabel name = new JLabel(model.getAcronym());
            name.setPreferredSize(new Dimension(50, 18));
            JProgressBar bar = new JProgressBar(0, 20);
            bar.setStringPainted(false);
            bar.setForeground(colorFor(model));
            JLabel value = new JLabel("0 pts");
            scoreBars.put(model, bar);
            scoreLabels.put(model, value);

            c.gridy = i;
            c.gridx = 0;
            c.weightx = 0;
            panel.add(name, c);
            c.gridx = 1;
            c.weightx = 1;
            panel.add(bar, c);
            c.gridx = 2;
            c.weightx = 0;
            panel.add(value, c);
        }
        return panel;
    }

    private void classify() {
        try {
            ClassifierService.EngineType engine = regexRadio.isSelected()
                    ? ClassifierService.EngineType.REGEX
                    : ClassifierService.EngineType.NLP;
            ClassificationResult result = service.classify(
                    firstNameField.getText(),
                    lastNameField.getText(),
                    descriptionArea.getText(),
                    engine);
            showResult(result);
        } catch (InvalidInputException ex) {
            JOptionPane.showMessageDialog(this, ex.getMessage(), "Datos inválidos", JOptionPane.WARNING_MESSAGE);
        } catch (Exception ex) {
            JOptionPane.showMessageDialog(this,
                    "Ocurrió un error al clasificar: " + ex.getMessage(),
                    "Error", JOptionPane.ERROR_MESSAGE);
        }
    }

    private void showResult(ClassificationResult result) {
        CloudModel model = result.getModel();
        resultBadge.setText(model.getAcronym());
        resultBadge.setBackground(colorFor(model));
        resultTitle.setText("<html><b>" + result.getFullUserName()
                + "</b>, el servicio se clasifica como <b>" + model.getAcronym()
                + "</b> — " + model.getFullName() + ".<br>"
                + model.getDescription() + "<br><i>Motor: " + result.getEngineName() + "</i></html>");

        int max = 1;
        for (Integer value : result.getScores().values()) {
            if (value.intValue() > max) {
                max = value.intValue();
            }
        }
        CloudModel[] models = new CloudModel[] {CloudModel.IAAS, CloudModel.PAAS, CloudModel.SAAS, CloudModel.FAAS};
        for (int i = 0; i < models.length; i++) {
            CloudModel current = models[i];
            int score = result.getScore(current);
            JProgressBar bar = scoreBars.get(current);
            bar.setMaximum(Math.max(max, 1));
            bar.setValue(score);
            scoreLabels.get(current).setText(score + " pts");
        }
        explanationArea.setText(result.getExplanation());
        explanationArea.setCaretPosition(0);
    }

    private void clearForm() {
        firstNameField.setText("");
        lastNameField.setText("");
        descriptionArea.setText("");
        resultBadge.setText("Sin clasificar");
        resultBadge.setBackground(UNKNOWN);
        resultTitle.setText("Escribe una descripción y pulsa Clasificar.");
        explanationArea.setText("");
        CloudModel[] models = new CloudModel[] {CloudModel.IAAS, CloudModel.PAAS, CloudModel.SAAS, CloudModel.FAAS};
        for (int i = 0; i < models.length; i++) {
            scoreBars.get(models[i]).setValue(0);
            scoreLabels.get(models[i]).setText("0 pts");
        }
        firstNameField.requestFocusInWindow();
    }

    private Color colorFor(CloudModel model) {
        if (model == CloudModel.IAAS) {
            return IAAS;
        }
        if (model == CloudModel.PAAS) {
            return PAAS;
        }
        if (model == CloudModel.SAAS) {
            return SAAS;
        }
        if (model == CloudModel.FAAS) {
            return FAAS;
        }
        return UNKNOWN;
    }
}
