/**
 * trex DataLab - Kullanıcı Profili & Hesap Menüsü (Profile Menu)
 * Tüm 5 sayfada header profil ikonuna tıklandığında açılan tam işlevsel açılır menü.
 */

(function () {
    'use strict';

    let dropdownEl = null;
    let isOpen = false;
    let usageExpanded = false;

    // Toast helper
    function showToast(msg) {
        let toast = document.getElementById('trexProfileToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'trexProfileToast';
            toast.className = 'fixed bottom-5 right-5 z-[99999] flex items-center gap-2.5 px-4 py-3 bg-[#1c1b1b] text-white text-xs font-body-md rounded-xl shadow-2xl transition-all duration-300 transform translate-y-10 opacity-0 pointer-events-none';
            document.body.appendChild(toast);
        }
        toast.innerHTML = `
            <span class="material-symbols-outlined text-emerald-400 text-base">info</span>
            <span class="font-medium">${msg}</span>
        `;
        requestAnimationFrame(() => {
            toast.classList.remove('translate-y-10', 'opacity-0', 'pointer-events-none');
            toast.classList.add('translate-y-0', 'opacity-100');
        });
        clearTimeout(toast._timeout);
        toast._timeout = setTimeout(() => {
            toast.classList.remove('translate-y-0', 'opacity-100');
            toast.classList.add('translate-y-10', 'opacity-0', 'pointer-events-none');
        }, 2500);
    }

    // Get current user profile data
    function getUserData() {
        const store = window.SettingsStore;
        const s = (store && typeof store.get === 'function') ? store.get() : {};
        const profile = s.user_profile || s.profile || {};

        const name = (profile.name || '').trim();
        const surname = (profile.surname || '').trim();
        let fullName = (name + ' ' + surname).trim();
        if (!fullName) {
            fullName = window.t ? window.t('profile.defaultName', 'Demo Kullanıcı') : 'Demo Kullanıcı';
        }

        const email = profile.email || (window.t ? window.t('profile.defaultEmail', 'demo@trexdatalab.com') : 'demo@trexdatalab.com');
        const role = profile.role || (window.t ? window.t('profile.role.analyst', 'Veri Analisti') : 'Veri Analisti');
        const avatar = profile.avatar || null;

        let initials = 'DK';
        if (name && surname) {
            initials = (name[0] + surname[0]).toUpperCase();
        } else if (name) {
            initials = name.substring(0, 2).toUpperCase();
        }

        const theme = s.theme || 'system';
        const isDark = (theme === 'dark') || (theme === 'system' && window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches);
        const language = s.language || 'tr';

        return {
            fullName,
            email,
            role,
            avatar,
            initials,
            isDark,
            language
        };
    }

    // Update Header Button Avatar
    function updateHeaderBtnAvatar(btn) {
        if (!btn) return;
        const user = getUserData();
        
        if (user.avatar) {
            btn.innerHTML = `
                <div class="w-8 h-8 rounded-full overflow-hidden border border-primary/40 shadow-xs flex items-center justify-center bg-primary/10">
                    <img src="${user.avatar}" alt="Avatar" class="w-full h-full object-cover">
                </div>
            `;
        } else {
            btn.innerHTML = `
                <div class="w-8 h-8 rounded-full bg-primary/10 text-primary border border-primary/30 flex items-center justify-center font-bold text-xs shadow-xs hover:bg-primary/20 transition-colors">
                    ${user.initials}
                </div>
            `;
        }
    }

    // Create or re-render Dropdown Menu HTML
    function renderDropdownHTML() {
        if (!dropdownEl) return;
        const user = getUserData();
        const t = window.t || ((k, f) => f || k);

        dropdownEl.innerHTML = `
            <!-- User Info Header -->
            <div class="p-4 bg-surface-container-low border-b border-border-subtle flex items-center gap-3.5">
                <div class="w-12 h-12 rounded-full overflow-hidden border-2 border-primary/30 shadow-xs flex items-center justify-center bg-primary/10 text-primary font-bold text-sm shrink-0">
                    ${user.avatar ? `<img src="${user.avatar}" alt="Avatar" class="w-full h-full object-cover">` : user.initials}
                </div>
                <div class="flex-1 min-w-0">
                    <div class="font-headline-md font-bold text-sm text-on-surface truncate">${user.fullName}</div>
                    <div class="text-[11px] text-on-surface-variant truncate">${user.email}</div>
                    <div class="mt-1 flex items-center gap-1.5">
                        <span class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-primary/10 text-primary border border-primary/20">
                            <span class="w-1.5 h-1.5 rounded-full bg-primary animate-pulse"></span>
                            <span>${user.role}</span>
                        </span>
                    </div>
                </div>
            </div>

            <!-- Navigation Links -->
            <div class="p-2 border-b border-border-subtle flex flex-col gap-0.5 text-xs">
                <!-- Profilimi Düzenle -->
                <a href="settings.html#profile" class="flex items-center gap-2.5 px-3 py-2 text-on-surface hover:bg-surface-container-high rounded-xl transition-colors">
                    <span class="material-symbols-outlined text-primary text-lg">person_edit</span>
                    <span class="font-medium">${t('profile.edit', 'Profilimi Düzenle')}</span>
                </a>

                <!-- Hesap Ayarları & Güvenlik -->
                <a href="settings.html#security" class="flex items-center gap-2.5 px-3 py-2 text-on-surface hover:bg-surface-container-high rounded-xl transition-colors">
                    <span class="material-symbols-outlined text-on-surface-variant text-lg">lock_reset</span>
                    <span class="font-medium">${t('profile.accountSecurity', 'Hesap Ayarları & Güvenlik')}</span>
                </a>

                <!-- Kullanım & Limit Bilgisi Accordion -->
                <div>
                    <button type="button" id="toggleUsageBtn" class="w-full flex items-center justify-between px-3 py-2 text-on-surface hover:bg-surface-container-high rounded-xl transition-colors cursor-pointer text-left">
                        <div class="flex items-center gap-2.5">
                            <span class="material-symbols-outlined text-on-surface-variant text-lg">pie_chart</span>
                            <span class="font-medium">${t('profile.usage', 'Kullanım & Limit Bilgisi')}</span>
                        </div>
                        <span class="material-symbols-outlined text-sm text-on-surface-variant transition-transform ${usageExpanded ? 'rotate-180' : ''}">expand_more</span>
                    </button>
                    <div id="usageCollapse" class="${usageExpanded ? 'block' : 'hidden'} px-3 py-2.5 mx-1 mb-1 bg-surface-container-low rounded-xl border border-border-subtle/70 space-y-2.5">
                        <!-- Daily Quota -->
                        <div>
                            <div class="flex justify-between text-[11px] font-medium text-on-surface mb-1">
                                <span class="text-on-surface-variant">${t('profile.usage.dailyQuota', 'Günlük Analiz Kotası')}</span>
                                <span class="font-mono text-primary font-bold">8 / 10</span>
                            </div>
                            <div class="w-full h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
                                <div class="h-full bg-primary rounded-full" style="width: 80%;"></div>
                            </div>
                        </div>
                        <!-- Upload Limit -->
                        <div>
                            <div class="flex justify-between text-[11px] font-medium text-on-surface mb-1">
                                <span class="text-on-surface-variant">${t('profile.usage.uploadLimit', 'Yüklenen Veri Limiti')}</span>
                                <span class="font-mono text-warning-orange font-bold">42 MB / 50 MB</span>
                            </div>
                            <div class="w-full h-1.5 bg-surface-container-highest rounded-full overflow-hidden">
                                <div class="h-full bg-warning-orange rounded-full" style="width: 84%;"></div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Quick Preferences (Theme & Language) -->
            <div class="p-3 border-b border-border-subtle bg-surface-container-lowest flex flex-col gap-2.5 text-xs">
                <!-- Theme Mode Toggle -->
                <div class="flex items-center justify-between px-1">
                    <div class="flex items-center gap-2 text-on-surface font-medium">
                        <span class="material-symbols-outlined text-lg ${user.isDark ? 'text-amber-400' : 'text-amber-500'}">
                            ${user.isDark ? 'dark_mode' : 'light_mode'}
                        </span>
                        <span>${user.isDark ? t('profile.themeDark', 'Koyu Mod') : t('profile.themeLight', 'Açık Mod')}</span>
                    </div>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" id="profileThemeToggle" class="sr-only peer" ${user.isDark ? 'checked' : ''}>
                        <div class="w-9 h-5 bg-surface-container-highest peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-border-subtle after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-primary"></div>
                    </label>
                </div>

                <!-- Language Selection -->
                <div class="flex items-center justify-between px-1">
                    <div class="flex items-center gap-2 text-on-surface font-medium">
                        <span class="material-symbols-outlined text-lg text-on-surface-variant">translate</span>
                        <span>${t('profile.language', 'Dil Seçimi')}</span>
                    </div>
                    <div class="flex items-center bg-surface-container-low p-0.5 rounded-lg border border-border-subtle">
                        <button type="button" data-profile-lang="tr" class="px-2 py-0.5 text-[11px] font-semibold rounded-md transition-all cursor-pointer ${user.language === 'tr' ? 'bg-primary text-white shadow-xs' : 'text-on-surface-variant hover:text-on-surface'}">
                            TR 🇹🇷
                        </button>
                        <button type="button" data-profile-lang="en" class="px-2 py-0.5 text-[11px] font-semibold rounded-md transition-all cursor-pointer ${user.language === 'en' ? 'bg-primary text-white shadow-xs' : 'text-on-surface-variant hover:text-on-surface'}">
                            EN 🇬🇧
                        </button>
                    </div>
                </div>
            </div>

            <!-- Support & Feedback -->
            <div class="p-2 border-b border-border-subtle flex flex-col gap-0.5 text-xs">
                <!-- Help & Documentation -->
                <button type="button" id="profileHelpBtn" class="w-full flex items-center gap-2.5 px-3 py-2 text-on-surface hover:bg-surface-container-high rounded-xl transition-colors cursor-pointer text-left">
                    <span class="material-symbols-outlined text-on-surface-variant text-lg">help_outline</span>
                    <span class="font-medium">${t('profile.help', 'Yardım & Dokümantasyon')}</span>
                </button>

                <!-- Send Feedback -->
                <button type="button" id="profileFeedbackBtn" class="w-full flex items-center gap-2.5 px-3 py-2 text-on-surface hover:bg-surface-container-high rounded-xl transition-colors cursor-pointer text-left">
                    <span class="material-symbols-outlined text-on-surface-variant text-lg">chat_bubble_outline</span>
                    <span class="font-medium">${t('profile.feedback', 'Geri Bildirim Gönder')}</span>
                </button>
            </div>

            <!-- Version Info & Sign Out -->
            <div class="p-2 bg-surface-container-lowest">
                <button type="button" id="profileLogoutBtn" class="w-full flex items-center justify-between px-3 py-2 text-error hover:bg-error/10 rounded-xl transition-colors cursor-pointer text-left text-xs font-semibold">
                    <div class="flex items-center gap-2">
                        <span class="material-symbols-outlined text-lg">logout</span>
                        <span>${t('profile.logout', 'Çıkış Yap')}</span>
                    </div>
                    <span class="text-[10px] text-on-surface-variant/60 font-normal font-mono">${t('profile.version', 'Sürüm v1.0.0')}</span>
                </button>
            </div>
        `;

        bindDropdownEvents();
    }

    // Bind events inside the dropdown
    function bindDropdownEvents() {
        if (!dropdownEl) return;
        const store = window.SettingsStore;
        const t = window.t || ((k, f) => f || k);

        // 1. Toggle Usage Details
        const toggleUsageBtn = dropdownEl.querySelector('#toggleUsageBtn');
        if (toggleUsageBtn) {
            toggleUsageBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                usageExpanded = !usageExpanded;
                renderDropdownHTML();
            });
        }

        // 2. Theme Toggle Switch
        const themeToggle = dropdownEl.querySelector('#profileThemeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('change', (e) => {
                const isDark = e.target.checked;
                if (store && typeof store.set === 'function') {
                    store.set({ theme: isDark ? 'dark' : 'light' });
                }
                renderDropdownHTML();
                showToast(t('settings.savedToast', 'Ayarlar kaydedildi ✓'));
            });
        }

        // 3. Language Buttons
        dropdownEl.querySelectorAll('[data-profile-lang]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const targetLang = btn.getAttribute('data-profile-lang');
                if (window.setLanguage && typeof window.setLanguage === 'function') {
                    window.setLanguage(targetLang);
                } else if (store && typeof store.set === 'function') {
                    store.set({ language: targetLang });
                }
                renderDropdownHTML();
                showToast(t('settings.savedToast', 'Ayarlar kaydedildi ✓'));
            });
        });

        // 4. Help Button
        const helpBtn = dropdownEl.querySelector('#profileHelpBtn');
        if (helpBtn) {
            helpBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                closeMenu();
                alert(t('profile.helpModalDesc', 'Veri kalitesi skoru; kayıp veri, yinelenen kayıt, aykırı değer ve tip uyumsuzluklarının ağırlıklı hesaplanmasıyla oluşturulur.'));
            });
        }

        // 5. Feedback Button
        const feedbackBtn = dropdownEl.querySelector('#profileFeedbackBtn');
        if (feedbackBtn) {
            feedbackBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                closeMenu();
                showToast(t('profile.feedbackToast', 'Geri bildiriminiz başarıyla iletildi!'));
            });
        }

        // 6. Logout Button
        const logoutBtn = dropdownEl.querySelector('#profileLogoutBtn');
        if (logoutBtn) {
            logoutBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                if (confirm(t('profile.confirmLogout', 'Oturumu kapatmak istediğinize emin misiniz?'))) {
                    closeMenu();
                    showToast(t('profile.demoLogout', 'Demo modu: Bu uygulamada gerçek oturum sistemi bulunmuyor.'));
                    setTimeout(() => {
                        window.location.href = 'index.html';
                    }, 500);
                }
            });
        }

        // Links close the menu
        dropdownEl.querySelectorAll('a').forEach(a => {
            a.addEventListener('click', () => {
                closeMenu();
            });
        });
    }

    // Positioning
    function updatePosition(btn) {
        if (!dropdownEl || !btn) return;
        const rect = btn.getBoundingClientRect();
        const top = rect.bottom + 8;
        const right = window.innerWidth - rect.right;

        dropdownEl.style.top = `${top}px`;
        dropdownEl.style.right = `${Math.max(12, right)}px`;
    }

    // Open Menu
    function openMenu(btn) {
        if (!dropdownEl) return;
        isOpen = true;
        renderDropdownHTML();
        updatePosition(btn);
        
        dropdownEl.classList.remove('opacity-0', 'scale-95', 'pointer-events-none');
        dropdownEl.classList.add('opacity-100', 'scale-100', 'pointer-events-auto');
        if (btn) btn.classList.add('text-primary');
    }

    // Close Menu
    function closeMenu() {
        if (!dropdownEl) return;
        isOpen = false;
        dropdownEl.classList.add('opacity-0', 'scale-95', 'pointer-events-none');
        dropdownEl.classList.remove('opacity-100', 'scale-100', 'pointer-events-auto');
        
        const btn = document.getElementById('profileBtn');
        if (btn) btn.classList.remove('text-primary');
    }

    // Toggle Menu
    function toggleMenu(btn) {
        if (isOpen) {
            closeMenu();
        } else {
            // Close notification dropdown if open
            const notifDropdown = document.getElementById('trexNotificationsDropdown');
            if (notifDropdown && notifDropdown.classList.contains('opacity-100')) {
                notifDropdown.classList.add('opacity-0', 'scale-95', 'pointer-events-none');
                notifDropdown.classList.remove('opacity-100', 'scale-100', 'pointer-events-auto');
            }
            openMenu(btn);
        }
    }

    // Initialize Profile Menu
    function initProfileMenu() {
        // Find profile button
        let profileBtn = document.getElementById('profileBtn');
        if (!profileBtn) {
            profileBtn = document.querySelector('button[title*="Profil"], button[data-i18n-title="nav.profile"], button[title*="Profile"]');
            if (profileBtn) profileBtn.id = 'profileBtn';
        }

        if (!profileBtn) return;

        // Ensure consistent styling & button avatar
        profileBtn.classList.add('cursor-pointer', 'select-none', 'transition-all');
        updateHeaderBtnAvatar(profileBtn);

        // Create Dropdown Container if not exists
        if (!dropdownEl) {
            dropdownEl = document.createElement('div');
            dropdownEl.id = 'trexProfileDropdown';
            dropdownEl.className = 'fixed z-50 w-72 sm:w-80 bg-white border border-border-subtle rounded-2xl shadow-xl overflow-hidden transition-all duration-200 transform opacity-0 scale-95 pointer-events-none origin-top-right';
            document.body.appendChild(dropdownEl);
        }

        // Toggle click
        profileBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleMenu(profileBtn);
        });

        // Close on click outside
        document.addEventListener('click', (e) => {
            if (isOpen && dropdownEl && !dropdownEl.contains(e.target) && !profileBtn.contains(e.target)) {
                closeMenu();
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && isOpen) {
                closeMenu();
            }
        });

        // Reposition on window resize / scroll
        window.addEventListener('resize', () => {
            if (isOpen) updatePosition(profileBtn);
        });
        window.addEventListener('scroll', () => {
            if (isOpen) updatePosition(profileBtn);
        }, true);

        // Listen for language or settings changes to re-sync
        document.addEventListener('languageChanged', () => {
            updateHeaderBtnAvatar(profileBtn);
            if (isOpen) renderDropdownHTML();
        });
        if (window.SettingsStore && typeof window.SettingsStore.subscribe === 'function') {
            window.SettingsStore.subscribe(() => {
                updateHeaderBtnAvatar(profileBtn);
                if (isOpen) renderDropdownHTML();
            });
        }
    }

    // Start on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initProfileMenu);
    } else {
        initProfileMenu();
    }

    // Expose on window
    window.TrexProfileMenu = {
        open: openMenu,
        close: closeMenu,
        toggle: toggleMenu,
        refresh: () => {
            const btn = document.getElementById('profileBtn');
            if (btn) updateHeaderBtnAvatar(btn);
            if (isOpen) renderDropdownHTML();
        }
    };
})();
