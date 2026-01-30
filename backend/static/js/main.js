// Mobile menu toggle
function toggleMobileMenu() {
    const menu = document.getElementById('mobile-menu');
    menu.classList.toggle('open');
}

// Sidebar toggle for dashboards
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    sidebar.classList.toggle('open');

    if (overlay) {
        overlay.classList.toggle('hidden');
    }
}

// Close sidebar when clicking overlay
function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    sidebar.classList.remove('open');

    if (overlay) {
        overlay.classList.add('hidden');
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function () {
    // Close mobile menu when clicking outside
    document.addEventListener('click', function (event) {
        const menu = document.getElementById('mobile-menu');
        const menuButton = document.getElementById('mobile-menu-button');

        if (menu && menuButton && !menu.contains(event.target) && !menuButton.contains(event.target)) {
            menu.classList.remove('open');
        }
    });
});
