(function () {
  var btn = document.getElementById("menu-btn");
  var nav = document.getElementById("main-nav");
  if (btn && nav) {
    btn.addEventListener("click", function () {
      var open = nav.classList.toggle("open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    });
  }

  document.querySelectorAll("img.shot").forEach(function (img) {
    img.addEventListener("error", function () {
      if (this.dataset.triedAlt) return;
      this.dataset.triedAlt = "1";
      var src = this.getAttribute("src") || "";
      if (src.indexOf("html/evidencias/") === -1 && src.indexOf("evidencias/") !== -1) {
        this.src = src.replace("evidencias/", "html/evidencias/");
      }
    });
  });
})();
