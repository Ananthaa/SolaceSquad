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

let _mainSidebarBusy = false;

// Sidebar toggle for dashboards
window.openSidebar = function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar) {
        sidebar.classList.remove('-translate-x-full');
        sidebar.classList.add('translate-x-0', 'sidebar-open', 'open');
        sidebar.style.setProperty('display', 'flex', 'important');
        sidebar.style.setProperty('visibility', 'visible', 'important');
        sidebar.style.setProperty('opacity', '1', 'important');
        sidebar.style.setProperty('transform', 'translateX(0px)', 'important');
        sidebar.style.setProperty('-webkit-transform', 'translateX(0px)', 'important');
        sidebar.style.setProperty('left', '0px', 'important');
        sidebar.style.setProperty('z-index', '99999', 'important');
        sidebar.style.setProperty('pointer-events', 'auto', 'important');
    }
    if (overlay) {
        overlay.classList.remove('hidden');
        overlay.classList.add('active', 'sidebar-overlay-open');
        overlay.style.setProperty('display', 'block', 'important');
        overlay.style.setProperty('visibility', 'visible', 'important');
        overlay.style.setProperty('opacity', '1', 'important');
        overlay.style.setProperty('z-index', '99998', 'important');
        overlay.style.setProperty('pointer-events', 'auto', 'important');
    }
};

window.closeSidebar = function () {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar) {
        sidebar.classList.add('-translate-x-full');
        sidebar.classList.remove('translate-x-0', 'sidebar-open', 'open');
        sidebar.style.setProperty('transform', 'translateX(-100%)', 'important');
        sidebar.style.setProperty('-webkit-transform', 'translateX(-100%)', 'important');
        if (window.innerWidth < 1024) {
            sidebar.style.setProperty('display', 'none', 'important');
            sidebar.style.setProperty('left', '-100%', 'important');
            sidebar.style.setProperty('pointer-events', 'none', 'important');
        }
    }
    if (overlay) {
        overlay.classList.add('hidden');
        overlay.classList.remove('active', 'sidebar-overlay-open');
        overlay.style.setProperty('display', 'none', 'important');
        overlay.style.setProperty('pointer-events', 'none', 'important');
    }
};

window.toggleSidebar = function (e) {
    if (e) {
        try { if (typeof e.preventDefault === 'function') e.preventDefault(); } catch (err) {}
        try { if (typeof e.stopPropagation === 'function') e.stopPropagation(); } catch (err) {}
    }
    if (_mainSidebarBusy) return;
    _mainSidebarBusy = true;
    setTimeout(() => { _mainSidebarBusy = false; }, 200);

    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    const isOpen = sidebar.classList.contains('sidebar-open') && 
                   sidebar.style.display !== 'none' &&
                   !sidebar.classList.contains('-translate-x-full');
    if (isOpen) {
        window.closeSidebar();
    } else {
        window.openSidebar();
    }
};

function bindMainSidebarEvents() {
    const toggleBtn = document.getElementById('sidebar-toggle-btn');
    if (toggleBtn && !toggleBtn.dataset.boundMainSidebar) {
        toggleBtn.dataset.boundMainSidebar = 'true';
        const onToggle = function (e) {
            if (e) {
                try { e.preventDefault(); } catch (err) {}
                try { e.stopPropagation(); } catch (err) {}
            }
            window.toggleSidebar(e);
            return false;
        };
        toggleBtn.addEventListener('click', onToggle, { passive: false });
        toggleBtn.addEventListener('touchend', onToggle, { passive: false });
    }

    const closeBtn = document.getElementById('sidebar-close-btn');
    if (closeBtn && !closeBtn.dataset.boundMainSidebar) {
        closeBtn.dataset.boundMainSidebar = 'true';
        const onClose = function (e) {
            if (e) {
                try { e.preventDefault(); } catch (err) {}
                try { e.stopPropagation(); } catch (err) {}
            }
            window.closeSidebar();
            return false;
        };
        closeBtn.addEventListener('click', onClose, { passive: false });
        closeBtn.addEventListener('touchend', onClose, { passive: false });
    }

    const overlay = document.getElementById('sidebar-overlay');
    if (overlay && !overlay.dataset.boundMainSidebar) {
        overlay.dataset.boundMainSidebar = 'true';
        const onOverlayClose = function (e) {
            if (e) {
                try { e.preventDefault(); } catch (err) {}
                try { e.stopPropagation(); } catch (err) {}
            }
            window.closeSidebar();
            return false;
        };
        overlay.addEventListener('click', onOverlayClose, { passive: false });
        overlay.addEventListener('touchend', onOverlayClose, { passive: false });
    }
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindMainSidebarEvents);
} else {
    bindMainSidebarEvents();
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
