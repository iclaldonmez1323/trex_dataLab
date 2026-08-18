/**
 * trex DataLab - Ayarlar ve Tema Yöneticisi (Settings & Theme Manager)
 * LocalStorage yönetimi, Koyu/Açık/Sistem Tema, Renk Paleti ve Önizleme Ayarları.
 */

(function () {
    'use strict';

    const STORAGE_KEY = 'trex_datalab_settings';
    const SCHEMA_VERSION = 1;

    const DEFAULT_SETTINGS = {
        version: SCHEMA_VERSION,
        theme: 'system', // 'light' | 'dark' | 'system'
        language: 'tr', // 'tr' | 'en'
        table_preview_rows: 10, // 10 | 25 | 50 | 100
        color_palette: 'default', // 'default' | 'ocean' | 'forest'
        csv_delimiter: ',', // ',' | ';' | '\t'
        quality_missing_threshold: 20, // % 0-100
        history_retention_days: 30, // gun
        export_sections: ['summary', 'missing', 'duplicates', 'dtypes', 'outliers', 'score'],
        export_title: 'trex DataLab Raporu',
        export_logo: null, // base64 string
        export_format: 'pdf', // 'pdf' | 'xlsx' | 'csv'
        notify_analysis_complete: true,
        notify_export_ready: true,
        notify_system_errors: true,
        notification_sound: false,
        geminiApiKey: '',
        user_profile: {
            name: 'İclal',
            surname: 'Dönmez',
            email: 'iclal@trex.io',
            avatar: null
        }
    };

    const PALETTES = {
        default: {
            light: {
                primary: '#006b33',
                primaryContainer: '#008742',
                primaryFixed: '#8bf9a6',
                onPrimaryFixed: '#00210b',
                onPrimary: '#ffffff'
            },
            dark: {
                primary: '#34D17B',
                primaryContainer: '#005226',
                primaryFixed: '#22613d',
                onPrimaryFixed: '#8bf9a6',
                onPrimary: '#003919'
            }
        },
        ocean: {
            light: {
                primary: '#0284c7',
                primaryContainer: '#0369a1',
                primaryFixed: '#bae6fd',
                onPrimaryFixed: '#082f49',
                onPrimary: '#ffffff'
            },
            dark: {
                primary: '#38bdf8',
                primaryContainer: '#075985',
                primaryFixed: '#0c4a6e',
                onPrimaryFixed: '#e0f2fe',
                onPrimary: '#082f49'
            }
        },
        forest: {
            light: {
                primary: '#1b4332',
                primaryContainer: '#2d6a4f',
                primaryFixed: '#95d5b2',
                onPrimaryFixed: '#081c15',
                onPrimary: '#ffffff'
            },
            dark: {
                primary: '#52b788',
                primaryContainer: '#1b4332',
                primaryFixed: '#2d6a4f',
                onPrimaryFixed: '#d8f3dc',
                onPrimary: '#081c15'
            }
        }
    };

    let listeners = [];
    let mediaQueryListener = null;

    /**
     * LocalStorage'dan ayarları yükle
     */
    function loadSettings() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed && typeof parsed === 'object') {
                    return {
                        ...DEFAULT_SETTINGS,
                        ...parsed,
                        user_profile: {
                            ...DEFAULT_SETTINGS.user_profile,
                            ...(parsed.user_profile || {})
                        },
                        version: SCHEMA_VERSION
                    };
                }
            }
        } catch (e) {
            console.warn('[SettingsStore] Ayarlar okunamadı:', e);
        }
        return { ...DEFAULT_SETTINGS };
    }

    /**
     * Ayarları kaydet
     */
    function saveSettings(settings) {
        try {
            const payload = {
                ...settings,
                version: SCHEMA_VERSION
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        } catch (e) {
            console.error('[SettingsStore] Ayarlar kaydedilemedi:', e);
        }
    }

    /**
     * Aktif temayı tespit et (light veya dark)
     */
    function resolveTheme(themeOption) {
        if (themeOption === 'dark') return 'dark';
        if (themeOption === 'light') return 'light';
        // 'system'
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }

    /**
     * CSS Değişkenlerini DOM'a enjekte et
     */
    function injectThemeStyles(isDark, paletteName) {
        const palette = PALETTES[paletteName] || PALETTES.default;
        const pColors = isDark ? palette.dark : palette.light;

        let styleEl = document.getElementById('trex-theme-vars');
        if (!styleEl) {
            styleEl = document.createElement('style');
            styleEl.id = 'trex-theme-vars';
            document.head.appendChild(styleEl);
        }

        if (isDark) {
            styleEl.textContent = `
                :root, html, html.dark, [data-theme="dark"] {
                    --c-surface: #121e17;
                    --c-surface-faint: #0a140e;
                    --c-surface-container-low: #16261d;
                    --c-surface-container: #1c3025;
                    --c-surface-container-high: #233a2d;
                    --c-surface-container-highest: #2d4637;
                    --c-surface-container-lowest: #0e1812;
                    --c-background: #0a140e;
                    --c-on-surface: #E8F0EA;
                    --c-on-surface-variant: #A3B8AA;
                    --c-on-background: #E8F0EA;
                    --c-border-subtle: #22382a;
                    --c-outline-variant: #2c4635;
                    --c-outline: #476652;
                    --c-primary: ${pColors.primary};
                    --c-primary-container: ${pColors.primaryContainer};
                    --c-primary-fixed: ${pColors.primaryFixed};
                    --c-on-primary-fixed: ${pColors.onPrimaryFixed};
                    --c-on-primary: ${pColors.onPrimary};
                    --c-error: #FF6B6B;
                    --c-error-container: #4f1010;
                    --c-on-error-container: #ffd4d4;
                    --c-warning-orange: #F5B054;
                    --c-success-green: #4ADE80;
                    --c-slate-gray: #94A3B8;
                    color-scheme: dark;
                }
                html.dark body {
                    background-color: var(--c-surface-faint) !important;
                    color: var(--c-on-surface) !important;
                }
                html.dark .bg-white {
                    background-color: var(--c-surface-container-lowest) !important;
                }
                html.dark .bg-surface {
                    background-color: var(--c-surface) !important;
                }
                html.dark .bg-surface-faint {
                    background-color: var(--c-surface-faint) !important;
                }
                html.dark .bg-surface-container-lowest {
                    background-color: var(--c-surface-container-lowest) !important;
                }
                html.dark .bg-surface-container-low {
                    background-color: var(--c-surface-container-low) !important;
                }
                html.dark .bg-surface-container {
                    background-color: var(--c-surface-container) !important;
                }
                html.dark .bg-surface-container-high {
                    background-color: var(--c-surface-container-high) !important;
                }
                html.dark .bg-surface-container-highest {
                    background-color: var(--c-surface-container-highest) !important;
                }
                html.dark .border-border-subtle, html.dark .border-slate-200, html.dark .border-slate-100 {
                    border-color: var(--c-border-subtle) !important;
                }
                html.dark .text-slate-900, html.dark .text-slate-800, html.dark .text-slate-700 {
                    color: var(--c-on-surface) !important;
                }
                html.dark .text-slate-600, html.dark .text-slate-500, html.dark .text-slate-400 {
                    color: var(--c-on-surface-variant) !important;
                }
                html.dark .bg-slate-50, html.dark .bg-slate-100 {
                    background-color: var(--c-surface-container-low) !important;
                }
                html.dark input:not([type="checkbox"]):not([type="radio"]),
                html.dark select,
                html.dark textarea {
                    background-color: var(--c-surface-container-low) !important;
                    color: var(--c-on-surface) !important;
                    border-color: var(--c-border-subtle) !important;
                }
            `;
        } else {
            styleEl.textContent = `
                :root, html, [data-theme="light"] {
                    --c-surface: #ffffff;
                    --c-surface-faint: #F8FAFC;
                    --c-surface-container-low: #f6f3f2;
                    --c-surface-container: #f0edec;
                    --c-surface-container-high: #ebe7e7;
                    --c-surface-container-highest: #e5e2e1;
                    --c-surface-container-lowest: #ffffff;
                    --c-background: #fcf9f8;
                    --c-on-surface: #1c1b1b;
                    --c-on-surface-variant: #3e4a3f;
                    --c-on-background: #1c1b1b;
                    --c-border-subtle: #E2E8F0;
                    --c-outline-variant: #bdcabc;
                    --c-outline: #6e7a6e;
                    --c-primary: ${pColors.primary};
                    --c-primary-container: ${pColors.primaryContainer};
                    --c-primary-fixed: ${pColors.primaryFixed};
                    --c-on-primary-fixed: ${pColors.onPrimaryFixed};
                    --c-on-primary: ${pColors.onPrimary};
                    --c-error: #ba1a1a;
                    --c-error-container: #ffdad6;
                    --c-on-error-container: #93000a;
                    --c-warning-orange: #F5B054;
                    --c-success-green: #19924B;
                    --c-slate-gray: #4A5568;
                    color-scheme: light;
                }
            `;
        }
    }

    /**
     * Temayı Uygula
     */
    function applyTheme(themeOption, paletteOption) {
        const settings = loadSettings();
        const theme = themeOption || settings.theme || 'system';
        const palette = paletteOption || settings.color_palette || 'default';

        const effectiveTheme = resolveTheme(theme);
        const isDark = effectiveTheme === 'dark';

        const root = document.documentElement;
        root.setAttribute('data-theme', isDark ? 'dark' : 'light');
        root.classList.toggle('dark', isDark);

        injectThemeStyles(isDark, palette);

        // Sistem teması izleyicisi
        if (theme === 'system' && window.matchMedia) {
            if (!mediaQueryListener) {
                const mq = window.matchMedia('(prefers-color-scheme: dark)');
                mediaQueryListener = (e) => {
                    const cur = loadSettings();
                    if (cur.theme === 'system') {
                        applyTheme('system', cur.color_palette);
                    }
                };
                mq.addEventListener('change', mediaQueryListener);
            }
        }
    }

    /**
     * Settings Store API
     */
    const SettingsStore = {
        get() {
            return loadSettings();
        },

        set(partialOrFull) {
            const current = loadSettings();
            const updated = {
                ...current,
                ...partialOrFull,
                user_profile: {
                    ...current.user_profile,
                    ...((partialOrFull && partialOrFull.user_profile) || {})
                }
            };
            saveSettings(updated);

            // Tema ve Renk Paleti güncelle
            applyTheme(updated.theme, updated.color_palette);

            // Dil güncellemesi gerekiyorsa i18n'e bildir
            if (partialOrFull.language && window.setLanguage && typeof window.setLanguage === 'function') {
                window.setLanguage(partialOrFull.language, false);
            }

            // Olayı fırlat
            const event = new CustomEvent('trex:settings-changed', { detail: updated });
            window.dispatchEvent(event);
            listeners.forEach(fn => {
                try { fn(updated); } catch (e) { console.error(e); }
            });

            return updated;
        },

        reset() {
            saveSettings(DEFAULT_SETTINGS);
            applyTheme(DEFAULT_SETTINGS.theme, DEFAULT_SETTINGS.color_palette);
            if (window.setLanguage) {
                window.setLanguage(DEFAULT_SETTINGS.language, false);
            }
            const event = new CustomEvent('trex:settings-changed', { detail: DEFAULT_SETTINGS });
            window.dispatchEvent(event);
            listeners.forEach(fn => {
                try { fn(DEFAULT_SETTINGS); } catch (e) { console.error(e); }
            });
            return DEFAULT_SETTINGS;
        },

        clearCache() {
            const keysToRemove = [];
            for (let i = 0; i < localStorage.length; i++) {
                const k = localStorage.key(i);
                if (k && (k.startsWith('trex_datalab_') || k.startsWith('trex_'))) {
                    keysToRemove.push(k);
                }
            }
            keysToRemove.forEach(k => localStorage.removeItem(k));
            // Varsayılan ayarları tekrar kaydet
            saveSettings(DEFAULT_SETTINGS);
            applyTheme(DEFAULT_SETTINGS.theme, DEFAULT_SETTINGS.color_palette);
            return true;
        },

        getEffectiveTheme() {
            const s = loadSettings();
            return resolveTheme(s.theme);
        },

        subscribe(callback) {
            if (typeof callback === 'function') {
                listeners.push(callback);
            }
            return () => {
                listeners = listeners.filter(fn => fn !== callback);
            };
        }
    };

    // Global nesneler
    window.SettingsStore = SettingsStore;
    window.TrexSettings = SettingsStore;

    // Hemen temayı başlat (FOUC - Flash of Unstyled Content önleme)
    const initSettings = loadSettings();
    applyTheme(initSettings.theme, initSettings.color_palette);

    // Storage olayını dinle (diğer sekmelerle anında senkronizasyon)
    window.addEventListener('storage', (e) => {
        if (e.key === STORAGE_KEY) {
            const fresh = loadSettings();
            applyTheme(fresh.theme, fresh.color_palette);
            if (window.setLanguage && typeof window.setLanguage === 'function') {
                window.setLanguage(fresh.language, false);
            }
            listeners.forEach(fn => fn(fresh));
        }
    });

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => {
            applyTheme();
        });
    }
})();
