package cloudclassifier.gui;

import cloudclassifier.classifier.ClassificationResult;
import cloudclassifier.classifier.ClassifierService;
import cloudclassifier.classifier.CloudModel;
import cloudclassifier.soap.PendingConcept;
import cloudclassifier.soap.ProgressInfo;
import cloudclassifier.soap.SoapClient;
import cloudclassifier.soap.SoapFaultException;
import cloudclassifier.util.InputValidator;
import cloudclassifier.util.InvalidInputException;

import javax.swing.BorderFactory;
import javax.swing.ButtonGroup;
import javax.swing.DefaultComboBoxModel;
import javax.swing.JButton;
import javax.swing.JComboBox;
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
import javax.swing.SwingWorker;
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
import java.util.List;
import java.util.Map;

/**
 * Interfaz gráfica. Modo local (ejercicio 1) y modo cliente SOAP (ejercicio 3).
 * La GUI no se conecta a PostgreSQL.
 */
public final class ClassifierWindow extends JFrame {
    private static final Color HEADER_BG = new Color(18, 52, 86);
    private static final Color IAAS = new Color(25, 118, 210);
    private static final Color PAAS = new Color(46, 125, 50);
    private static final Color SAAS = new Color(230, 126, 34);
    private static final Color FAAS = new Color(123, 31, 162);
    private static final Color UNKNOWN = new Color(97, 97, 97);

    private final ClassifierService service = new ClassifierService();

    private final JTextField firstNameField = new JTextField(14);
    private final JTextField lastNameField = new JTextField(14);
    private final JTextField emailField = new JTextField(18);
    private final JTextField endpointField = new JTextField("http://localhost:5000/soap", 28);
    private final JTextArea descriptionArea = new JTextArea(5, 40);
    private final JRadioButton regexRadio = new JRadioButton("Regex + palabras clave");
    private final JRadioButton nlpRadio = new JRadioButton("NLP básico");
    private final JRadioButton localRadio = new JRadioButton("Local");
    private final JRadioButton soapRadio = new JRadioButton("Cliente SOAP");
    private final JComboBox pendingCombo = new JComboBox();
    private final JLabel resultBadge = new JLabel("Sin clasificar", SwingConstants.CENTER);
    private final JLabel resultTitle = new JLabel("Escribe una descripción o carga conceptos pendientes.");
    private final JTextArea explanationArea = new JTextArea(5, 40);
    private final JTextArea soapLogArea = new JTextArea(6, 40);
    private final Map<CloudModel, JProgressBar> scoreBars = new EnumMap<CloudModel, JProgressBar>(CloudModel.class);
    private final Map<CloudModel, JLabel> scoreLabels = new EnumMap<CloudModel, JLabel>(CloudModel.class);

    public ClassifierWindow() {
        super("cloud_models_classifier — Local y cliente SOAP");
        setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        setMinimumSize(new Dimension(860, 860));
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

        JLabel title = new JLabel("Clasificador Cloud · modo local y SOAP");
        title.setForeground(Color.WHITE);
        title.setFont(title.getFont().deriveFont(Font.BOLD, 22f));

        JLabel subtitle = new JLabel("SC3705 · IaaS  ·  PaaS  ·  SaaS  ·  FaaS  ·  WSDL");
        subtitle.setForeground(new Color(186, 210, 232));
        subtitle.setFont(subtitle.getFont().deriveFont(14f));

        header.add(title, BorderLayout.NORTH);
        header.add(subtitle, BorderLayout.SOUTH);
        return header;
    }

    private JPanel buildForm() {
        JPanel form = new JPanel(new GridBagLayout());
        form.setBorder(BorderFactory.createEmptyBorder(12, 20, 8, 20));
        GridBagConstraints c = new GridBagConstraints();
        c.insets = new Insets(3, 4, 3, 4);
        c.fill = GridBagConstraints.HORIZONTAL;
        c.anchor = GridBagConstraints.WEST;

        c.gridx = 0;
        c.gridy = 0;
        form.add(new JLabel("Nombre"), c);
        c.gridx = 1;
        form.add(firstNameField, c);
        c.gridx = 2;
        form.add(new JLabel("Apellidos"), c);
        c.gridx = 3;
        form.add(lastNameField, c);

        c.gridx = 0;
        c.gridy = 1;
        form.add(new JLabel("Correo"), c);
        c.gridx = 1;
        c.gridwidth = 3;
        form.add(emailField, c);
        c.gridwidth = 1;

        ButtonGroup modes = new ButtonGroup();
        modes.add(localRadio);
        modes.add(soapRadio);
        soapRadio.setSelected(true);
        JPanel modePanel = new JPanel();
        modePanel.add(new JLabel("Modo:"));
        modePanel.add(localRadio);
        modePanel.add(soapRadio);
        c.gridx = 0;
        c.gridy = 2;
        c.gridwidth = 4;
        form.add(modePanel, c);

        c.gridy = 3;
        form.add(labeled("Endpoint SOAP", endpointField), c);

        pendingCombo.setModel(new DefaultComboBoxModel());
        c.gridy = 4;
        form.add(labeled("Conceptos pendientes", pendingCombo), c);

        descriptionArea.setLineWrap(true);
        descriptionArea.setWrapStyleWord(true);
        JScrollPane scroll = new JScrollPane(descriptionArea);
        scroll.setBorder(BorderFactory.createTitledBorder("Descripción / definición del concepto"));
        c.gridy = 5;
        c.weightx = 1;
        c.weighty = 1;
        c.fill = GridBagConstraints.BOTH;
        form.add(scroll, c);

        ButtonGroup engines = new ButtonGroup();
        engines.add(regexRadio);
        engines.add(nlpRadio);
        nlpRadio.setSelected(true);
        JPanel enginePanel = new JPanel();
        enginePanel.add(new JLabel("Motor local:"));
        enginePanel.add(regexRadio);
        enginePanel.add(nlpRadio);

        JButton loadButton = new JButton("Cargar pendientes");
        loadButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent e) {
                loadPending();
            }
        });
        JButton classifyButton = new JButton("Clasificar");
        classifyButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent e) {
                classify();
            }
        });
        JButton registerButton = new JButton("Registrar en SOAP");
        registerButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent e) {
                registerSoap();
            }
        });
        JButton progressButton = new JButton("Ver progreso");
        progressButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent e) {
                loadProgress();
            }
        });
        JButton clearButton = new JButton("Limpiar");
        clearButton.addActionListener(new ActionListener() {
            public void actionPerformed(ActionEvent e) {
                clearForm();
            }
        });

        JPanel actions = new JPanel();
        actions.add(enginePanel);
        actions.add(loadButton);
        actions.add(classifyButton);
        actions.add(registerButton);
        actions.add(progressButton);
        actions.add(clearButton);

        c.gridy = 6;
        c.weighty = 0;
        c.fill = GridBagConstraints.HORIZONTAL;
        form.add(actions, c);
        return form;
    }

    private JPanel labeled(String title, java.awt.Component field) {
        JPanel panel = new JPanel(new BorderLayout(8, 0));
        panel.add(new JLabel(title), BorderLayout.WEST);
        panel.add(field, BorderLayout.CENTER);
        return panel;
    }

    private JPanel buildResultPanel() {
        JPanel result = new JPanel(new BorderLayout(8, 8));
        result.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createEmptyBorder(0, 20, 16, 20),
                BorderFactory.createTitledBorder("Resultado")));

        resultBadge.setOpaque(true);
        resultBadge.setBackground(UNKNOWN);
        resultBadge.setForeground(Color.WHITE);
        resultBadge.setFont(resultBadge.getFont().deriveFont(Font.BOLD, 20f));
        resultBadge.setPreferredSize(new Dimension(160, 64));
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
        explanationScroll.setPreferredSize(new Dimension(700, 90));
        explanationScroll.setBorder(BorderFactory.createTitledBorder("Evidencia local"));

        soapLogArea.setEditable(false);
        soapLogArea.setLineWrap(true);
        soapLogArea.setWrapStyleWord(true);
        soapLogArea.setBackground(new Color(248, 249, 250));
        JScrollPane soapScroll = new JScrollPane(soapLogArea);
        soapScroll.setPreferredSize(new Dimension(700, 110));
        soapScroll.setBorder(BorderFactory.createTitledBorder("Respuesta SOAP (sin detalles de PostgreSQL)"));

        JPanel bottom = new JPanel(new BorderLayout(6, 6));
        bottom.add(explanationScroll, BorderLayout.NORTH);
        bottom.add(soapScroll, BorderLayout.CENTER);
        result.add(bottom, BorderLayout.SOUTH);
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
            PendingConcept selected = selectedConcept();
            if (soapRadio.isSelected() && selected != null && descriptionArea.getText().trim().isEmpty()) {
                descriptionArea.setText(selected.definition);
            }
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

    private void loadPending() {
        runSoap("Cargando conceptos pendientes…", new SoapWork() {
            public String run(SoapClient client) throws Exception {
                String correo = InputValidator.requireEmail(emailField.getText());
                List concepts = client.obtenerConceptosPendientes(correo);
                DefaultComboBoxModel model = new DefaultComboBoxModel();
                for (int i = 0; i < concepts.size(); i++) {
                    model.addElement(concepts.get(i));
                }
                pendingCombo.setModel(model);
                if (!concepts.isEmpty()) {
                    PendingConcept first = (PendingConcept) concepts.get(0);
                    descriptionArea.setText(first.definition);
                }
                return "Pendientes: " + concepts.size() + " concepto(s).";
            }
        });
    }

    private void registerSoap() {
        runSoap("Registrando clasificación…", new SoapWork() {
            public String run(SoapClient client) throws Exception {
                String nombre = InputValidator.requireName(firstNameField.getText(), "Nombre");
                String apellidos = InputValidator.requireName(lastNameField.getText(), "Apellidos");
                String correo = InputValidator.requireEmail(emailField.getText());
                PendingConcept concept = selectedConcept();
                if (concept == null) {
                    throw new InvalidInputException("Carga y selecciona un concepto pendiente.");
                }
                if (descriptionArea.getText().trim().isEmpty()) {
                    descriptionArea.setText(concept.definition);
                }
                ClassifierService.EngineType engine = regexRadio.isSelected()
                        ? ClassifierService.EngineType.REGEX
                        : ClassifierService.EngineType.NLP;
                ClassificationResult result = service.classify(nombre, apellidos, descriptionArea.getText(), engine);
                showResult(result);
                if (result.getModel() == CloudModel.INDETERMINADO) {
                    throw new InvalidInputException(
                            "El motor local no identificó un modelo. Ajusta la descripción y vuelve a clasificar.");
                }
                return client.registrarClasificacion(
                        nombre, apellidos, correo, concept, result.getModel().getAcronym());
            }
        });
    }

    private void loadProgress() {
        runSoap("Consultando progreso…", new SoapWork() {
            public String run(SoapClient client) throws Exception {
                String correo = InputValidator.requireEmail(emailField.getText());
                ProgressInfo info = client.obtenerProgreso(correo);
                return info.nombreCompleto + " · clasificados " + info.clasificados
                        + " · pendientes " + info.pendientes
                        + " · catálogo " + info.totalCatalogo;
            }
        });
    }

    private interface SoapWork {
        String run(SoapClient client) throws Exception;
    }

    private void runSoap(final String waitMessage, final SoapWork work) {
        soapLogArea.setText(waitMessage);
        final String endpoint = endpointField.getText().trim();
        SwingWorker worker = new SwingWorker() {
            protected Object doInBackground() throws Exception {
                SoapClient client = new SoapClient(endpoint);
                String message = work.run(client);
                return new Object[] {message, client.lastXml};
            }

            protected void done() {
                try {
                    Object[] pair = (Object[]) get();
                    soapLogArea.setText((String) pair[0] + "\n\n" + pair[1]);
                    soapLogArea.setCaretPosition(0);
                    resultTitle.setText("<html>" + pair[0] + "</html>");
                } catch (Exception ex) {
                    Throwable cause = ex.getCause() == null ? ex : ex.getCause();
                    showSoapError(cause);
                }
            }
        };
        worker.execute();
    }

    private void showSoapError(Throwable cause) {
        if (cause instanceof SoapFaultException) {
            SoapFaultException fault = (SoapFaultException) cause;
            String title = fault.isDuplicate() ? "Concepto ya clasificado"
                    : (fault.isClientFault() ? "No se pudo completar la solicitud" : "El servicio no está disponible");
            JOptionPane.showMessageDialog(this, fault.getUserMessage(), title,
                    fault.isClientFault() ? JOptionPane.WARNING_MESSAGE : JOptionPane.ERROR_MESSAGE);
            soapLogArea.setText(fault.getUserMessage());
            return;
        }
        if (cause instanceof InvalidInputException) {
            JOptionPane.showMessageDialog(this, cause.getMessage(), "Datos inválidos", JOptionPane.WARNING_MESSAGE);
            soapLogArea.setText(cause.getMessage());
            return;
        }
        JOptionPane.showMessageDialog(this,
                "No hay conexión con el módulo SOAP. Verifica el endpoint y que el servicio esté en ejecución.",
                "Servicio no disponible", JOptionPane.ERROR_MESSAGE);
        soapLogArea.setText(cause.getMessage());
    }

    private PendingConcept selectedConcept() {
        Object value = pendingCombo.getSelectedItem();
        if (value instanceof PendingConcept) {
            return (PendingConcept) value;
        }
        return null;
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
        emailField.setText("");
        descriptionArea.setText("");
        pendingCombo.setModel(new DefaultComboBoxModel());
        resultBadge.setText("Sin clasificar");
        resultBadge.setBackground(UNKNOWN);
        resultTitle.setText("Escribe una descripción o carga conceptos pendientes.");
        explanationArea.setText("");
        soapLogArea.setText("");
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
