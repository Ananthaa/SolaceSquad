// Mobile menu toggle — fixed overlay, toggled via inline style for maximum reliability
window.toggleMobileMenu = function () {
    const menu = document.getElementById('mobile-menu');
    const iconOpen = document.getElementById('icon-hamburger');
    const iconClose = document.getElementById('icon-close');
    if (!menu) return;
    const isOpen = menu.style.display === 'block';
    menu.style.display = isOpen ? 'none' : 'block';
    if (iconOpen) iconOpen.classList.toggle('hidden', !isOpen);
    if (iconClose) iconClose.classList.toggle('hidden', isOpen);
}

window.closeMobileMenu = function () {
    const menu = document.getElementById('mobile-menu');
    const iconOpen = document.getElementById('icon-hamburger');
    const iconClose = document.getElementById('icon-close');
    if (!menu) return;
    menu.style.display = 'none';
    if (iconOpen) iconOpen.classList.remove('hidden');
    if (iconClose) iconClose.classList.add('hidden');
}

// Sidebar toggle for dashboards
window.toggleSidebar = function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (sidebar) {
        // Toggle transform classes
        sidebar.classList.toggle('-translate-x-full');
    }

    if (overlay) {
        overlay.classList.toggle('hidden');
    }
}

// Close sidebar when clicking overlay
window.closeSidebar = function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');

    if (sidebar) {
        // Hide sidebar
        sidebar.classList.add('-translate-x-full');
    }

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
            closeMobileMenu();
        }
    });

    // Auto-close mobile menu when a nav link is tapped
    const mobileMenu = document.getElementById('mobile-menu');
    if (mobileMenu) {
        mobileMenu.querySelectorAll('a').forEach(function (link) {
            link.addEventListener('click', function () { closeMobileMenu(); });
        });
    }

    // Auto-close sidebar on mobile when clicking nav links
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        const navLinks = sidebar.querySelectorAll('a');
        navLinks.forEach(link => {
            link.addEventListener('click', function () {
                // Only close on mobile (screens smaller than lg breakpoint)
                if (window.innerWidth < 1024) {
                    closeSidebar();
                }
            });
        });
    }

    // Close sidebar when window is resized to desktop
    window.addEventListener('resize', function () {
        if (window.innerWidth >= 1024) {
            // On desktop, ensure sidebar is visible and overlay is hidden
            const sidebar = document.getElementById('sidebar');
            const overlay = document.getElementById('sidebar-overlay');

            if (sidebar) {
                sidebar.classList.remove('-translate-x-full');
            }
            if (overlay) {
                overlay.classList.add('hidden');
            }
        }
    });
});

// Global Table Actions Dropdown Controller
window.toggleTableDropdown = function (button, event) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    
    // Find the next element which contains the action templates/source
    const actionsContainer = button.nextElementSibling;
    if (!actionsContainer) return;
    
    let dropdown = document.getElementById('global-actions-dropdown');
    if (!dropdown) {
        // Create global dropdown container
        dropdown = document.createElement('div');
        dropdown.id = 'global-actions-dropdown';
        dropdown.className = 'fixed hidden bg-white border border-gray-200 rounded-xl shadow-xl z-[1000] py-1.5 min-w-[160px] animate-fade-in duration-100';
        document.body.appendChild(dropdown);
        
        // Close dropdown when clicking anywhere else
        document.addEventListener('click', function (e) {
            if (!dropdown.contains(e.target) && !e.target.closest('.dropdown-trigger')) {
                dropdown.classList.add('hidden');
            }
        });
        
        // Close dropdown on window resize or scroll
        window.addEventListener('resize', () => dropdown.classList.add('hidden'));
        window.addEventListener('scroll', () => dropdown.classList.add('hidden'), true);
    }
    
    // Toggle state if clicking the same trigger button
    if (!dropdown.classList.contains('hidden') && dropdown.dataset.triggerId === button.id) {
        dropdown.classList.add('hidden');
        return;
    }
    
    // Populate the dropdown with cloned action items
    dropdown.innerHTML = '';
    const clonedContainer = actionsContainer.cloneNode(true);
    clonedContainer.classList.remove('hidden');
    
    // Format all buttons / links as list items
    const items = clonedContainer.querySelectorAll('button, a');
    items.forEach(item => {
        // Build clean classes following existing theme layout
        item.className = 'flex w-full items-center px-4 py-2.5 text-sm text-gray-700 hover:bg-gray-50 transition-colors text-left gap-2 font-medium';
        // Add a click listener to auto-close the dropdown
        item.addEventListener('click', () => dropdown.classList.add('hidden'));
    });
    
    dropdown.appendChild(clonedContainer);
    dropdown.dataset.triggerId = button.id;
    
    // Position dropdown relative to the trigger button
    const rect = button.getBoundingClientRect();
    dropdown.classList.remove('hidden');
    
    const dropdownWidth = dropdown.offsetWidth;
    const dropdownHeight = dropdown.offsetHeight;
    
    let top = rect.bottom + 6;
    let left = rect.right - dropdownWidth;
    
    // Boundary check for viewport edges
    if (left < 10) left = 10;
    if (left + dropdownWidth > window.innerWidth - 10) {
        left = window.innerWidth - dropdownWidth - 10;
    }
    if (top + dropdownHeight > window.innerHeight - 10) {
        // Open upwards if no space below
        top = rect.top - dropdownHeight - 6;
    }
    
    dropdown.style.top = `${top}px`;
    dropdown.style.left = `${left}px`;
    
    // Re-initialize lucide icons inside dropdown
    if (window.lucide) {
        lucide.createIcons({ container: dropdown });
    }
};
