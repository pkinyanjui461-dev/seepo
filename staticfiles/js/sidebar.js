document.addEventListener('DOMContentLoaded', function() {
    var el = document.getElementById("wrapper");
    var toggleButton = document.getElementById("menu-toggle");
    
    if (toggleButton && el) {
        toggleButton.onclick = function() {
            el.classList.toggle("toggled");
            var sidebar = document.getElementById("sidebar");
            sidebar.classList.toggle("collapsed");
        };
    }
});
