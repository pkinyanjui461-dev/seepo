document.addEventListener('DOMContentLoaded', function() {
    var el = document.getElementById("wrapper");
    var toggleButton = document.getElementById("menu-toggle");
    var sidebar = document.getElementById("sidebar");
    var mobileQuery = window.matchMedia('(max-width: 991.98px)');
    
    if (toggleButton && el && sidebar) {
        toggleButton.onclick = function() {
            if (mobileQuery.matches) {
                el.classList.toggle("toggled");
                return;
            }

            el.classList.toggle("toggled");
            sidebar.classList.toggle("collapsed");
        };

        document.addEventListener('click', function(event) {
            if (!mobileQuery.matches || !el.classList.contains('toggled')) {
                return;
            }

            var clickedToggle = toggleButton.contains(event.target);
            var clickedSidebar = sidebar.contains(event.target);
            if (!clickedToggle && !clickedSidebar) {
                el.classList.remove('toggled');
            }
        });
    }
});
