(function () {
  var form = document.getElementById("classifier-form");
  if (!form || !window.CloudClassifier) {
    return;
  }

  var firstName = document.getElementById("nombre");
  var lastName = document.getElementById("apellido");
  var description = document.getElementById("descripcion");
  var errorBox = document.getElementById("classifier-error");
  var resultBox = document.getElementById("classifier-result");
  var badge = document.getElementById("result-badge");
  var title = document.getElementById("result-title");
  var explanation = document.getElementById("result-explanation");
  var examplesHost = document.getElementById("example-buttons");

  function selectedEngine() {
    var radio = form.querySelector('input[name="motor"]:checked');
    return radio ? radio.value : "nlp";
  }

  function showError(message) {
    errorBox.textContent = message;
    errorBox.hidden = false;
    resultBox.hidden = true;
  }

  function hideError() {
    errorBox.hidden = true;
    errorBox.textContent = "";
  }

  function setBar(id, score, max) {
    var bar = document.getElementById(id);
    var label = document.getElementById(id + "-label");
    bar.style.width = Math.round((score / max) * 100) + "%";
    label.textContent = score + " pts";
  }

  function renderResult(result) {
    hideError();
    resultBox.hidden = false;
    badge.textContent = result.model.acronym;
    badge.style.background = result.model.color;
    title.innerHTML = "<strong>" + result.fullUserName + "</strong>, el servicio se clasifica como <strong>" +
      result.model.acronym + "</strong> — " + result.model.fullName + ".<br>" +
      result.model.description + "<br><em>Motor: " + result.engineName + "</em>";
    explanation.textContent = result.explanation;
    var max = Math.max(result.scores.IAAS, result.scores.PAAS, result.scores.SAAS, result.scores.FAAS, 1);
    setBar("bar-iaas", result.scores.IAAS, max);
    setBar("bar-paas", result.scores.PAAS, max);
    setBar("bar-saas", result.scores.SAAS, max);
    setBar("bar-faas", result.scores.FAAS, max);
    resultBox.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  form.addEventListener("submit", function (event) {
    event.preventDefault();
    try {
      var result = window.CloudClassifier.classify(
        firstName.value,
        lastName.value,
        description.value,
        selectedEngine()
      );
      renderResult(result);
    } catch (error) {
      showError(error.message);
    }
  });

  document.getElementById("btn-limpiar").addEventListener("click", function () {
    form.reset();
    document.getElementById("motor-nlp").checked = true;
    hideError();
    resultBox.hidden = true;
    firstName.focus();
  });

  if (examplesHost) {
    window.CloudClassifier.examples.forEach(function (example) {
      var button = document.createElement("button");
      button.type = "button";
      button.className = "chip-btn";
      button.textContent = example.label;
      button.addEventListener("click", function () {
        description.value = example.text;
        hideError();
      });
      examplesHost.appendChild(button);
    });
  }
})();
