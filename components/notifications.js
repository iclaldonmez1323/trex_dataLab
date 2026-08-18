/**
 * trex DataLab - Bildirim Merkezi (Notification Center)
 * Tek ortak bildirim bileşeni.
 * LocalStorage senkronizasyonu, sekmeli filtreleme, göreli zaman, okundu takibi ve geçmiş görünümü.
 */

(function () {
    'use strict';

    const STORAGE_KEY = 'trex_datalab_notifications';
    const SCHEMA_VERSION = 1;

    // Başlangıç / Örnek Bildirim Verileri
    function getSeedNotifications() {
        const now = Date.now();
        const min = 60 * 1000;
        const hour = 60 * min;
        const day = 24 * hour;

        return [
            {
                id: 'notif-1',
                type: 'success',
                category: 'islem',
                title: 'PDF Raporu Hazır',
                message: 'veri_analiz_ozeti.pdf başarıyla dışa aktarıldı.',
                timestamp: new Date(now - 5 * min).toISOString(),
                read: false,
                action: { type: 'pdf_download', filename: 'veri_analiz_ozeti.pdf' }
            },
            {
                id: 'notif-2',
                type: 'info',
                category: 'islem',
                title: 'Veri & Analiz Uyarısı',
                message: 'Veri Kalitesi Skoru Hesaplandı: Yüklenen veri seti %78 kalite skoruna sahip. 3 kritik eksik değer uyarısı mevcut.',
                timestamp: new Date(now - 20 * min).toISOString(),
                read: false,
                action: null
            },
            {
                id: 'notif-3',
                type: 'error',
                category: 'uyari',
                title: 'Dışa Aktarma Hatası',
                message: 'PDF oluşturulurken bir sorun oluştu, lütfen tekrar deneyin.',
                timestamp: new Date(now - 1 * hour).toISOString(),
                read: false,
                action: null
            },
            {
                id: 'notif-4',
                type: 'warning',
                category: 'uyari',
                title: 'Veri Uyumsuzluğu',
                message: "'Torque' sütununda 32 olası uç değer tespit edildi.",
                timestamp: new Date(now - 3 * hour).toISOString(),
                read: false,
                action: null
            },
            {
                id: 'notif-5',
                type: 'info',
                category: 'islem',
                title: 'Sistem Bilgilendirmesi',
                message: 'Sistem Güncellemesi: Yeni dışa aktarma formatları eklendi.',
                timestamp: new Date(now - 1 * day).toISOString(),
                read: false,
                action: null
            },
            {
                id: 'notif-6',
                type: 'success',
                category: 'islem',
                title: 'Analiz Tamamlandı',
                message: 'Veri kalitesi analizi başarıyla tamamlandı.',
                timestamp: new Date(now - 2 * day).toISOString(),
                read: false,
                action: null
            }
        ];
    }

    // State
    let notifications = [];
    let currentTab = 'all'; // 'all' | 'islem' | 'uyari'
    let currentView = 'list'; // 'list' | 'history'
    let isPanelOpen = false;

    // DOM Elements
    let notifBtn = null;
    let badgeEl = null;
    let dropdownEl = null;

    /**
     * LocalStorage'dan verileri yükle
     */
    function loadNotifications() {
        try {
            const raw = localStorage.getItem(STORAGE_KEY);
            if (raw) {
                const parsed = JSON.parse(raw);
                if (parsed && parsed.version === SCHEMA_VERSION && Array.isArray(parsed.items)) {
                    notifications = parsed.items;
                    return;
                }
            }
        } catch (e) {
            console.warn('[NotificationCenter] LocalStorage okuma hatası:', e);
        }

        // İlk kurulum veya versiyon değişimi
        notifications = getSeedNotifications();
        saveNotifications();
    }

    /**
     * LocalStorage'a kaydet
     */
    function saveNotifications() {
        try {
            const payload = {
                version: SCHEMA_VERSION,
                items: notifications
            };
            localStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
        } catch (e) {
            console.error('[NotificationCenter] LocalStorage yazma hatası:', e);
        }
        updateBadge();
    }

    /**
     * Göreli Zaman Formatlayıcı (Türkçe)
     */
    function formatRelativeTime(isoString) {
        if (!isoString) return '';
        const now = Date.now();
        const date = new Date(isoString);
        const diffMs = Math.max(0, now - date.getTime());
        const diffSec = Math.floor(diffMs / 1000);
        const diffMin = Math.floor(diffSec / 60);
        const diffHour = Math.floor(diffMin / 60);
        const diffDay = Math.floor(diffHour / 24);

        if (diffSec < 60) return 'Az önce';
        if (diffMin < 60) return `${diffMin} dakika önce`;
        if (diffHour < 24) return `${diffHour} saat önce`;
        if (diffHour < 48 || diffDay === 1) return 'Dün';
        if (diffDay < 7) return `${diffDay} gün önce`;

        const months = ['Oca', 'Şub', 'Mar', 'Nis', 'May', 'Haz', 'Tem', 'Ağu', 'Eyl', 'Eki', 'Kas', 'Ara'];
        return `${date.getDate()} ${months[date.getMonth()]}`;
    }

    /**
     * Okunmamış bildirim sayısı
     */
    function getUnreadCount() {
        return notifications.filter(n => !n.read).length;
    }

    /**
     * Rozeti güncelle
     */
    function updateBadge() {
        if (!badgeEl) return;
        const unread = getUnreadCount();
        if (unread <= 0) {
            badgeEl.classList.add('hidden');
            badgeEl.textContent = '0';
        } else {
            badgeEl.classList.remove('hidden');
            badgeEl.textContent = unread > 9 ? '9+' : unread.toString();
        }
    }

    /**
     * Tek bildirimi okundu yap
     */
    function markAsRead(id) {
        let changed = false;
        notifications = notifications.map(n => {
            if (n.id === id && !n.read) {
                changed = true;
                return { ...n, read: true };
            }
            return n;
        });

        if (changed) {
            saveNotifications();
            renderDropdownContent();
        }
    }

    /**
     * Tümünü okundu yap
     */
    function markAllAsRead() {
        const hasUnread = notifications.some(n => !n.read);
        if (!hasUnread) return;

        notifications = notifications.map(n => ({ ...n, read: true }));
        saveNotifications();
        renderDropdownContent();
        showToast('Tüm bildirimler okundu olarak işaretlendi.');
    }

    /**
     * Toast Bildirimi Göster
     */
    function showToast(message) {
        let toast = document.getElementById('trexNotifToast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'trexNotifToast';
            toast.className = 'fixed bottom-5 right-5 z-[9999] flex items-center gap-2.5 px-4 py-3 bg-[#1c1b1b] text-white text-xs font-body-md rounded-xl shadow-2xl transition-all duration-300 transform translate-y-10 opacity-0 pointer-events-none';
            document.body.appendChild(toast);
        }

        toast.innerHTML = `
            <span class="material-symbols-outlined text-emerald-400 text-base">check_circle</span>
            <span class="font-medium">${message}</span>
        `;

        requestAnimationFrame(() => {
            toast.classList.remove('translate-y-10', 'opacity-0', 'pointer-events-none');
            toast.classList.add('translate-y-0', 'opacity-100');
        });

        clearTimeout(toast._timeout);
        toast._timeout = setTimeout(() => {
            toast.classList.remove('translate-y-0', 'opacity-100');
            toast.classList.add('translate-y-10', 'opacity-0', 'pointer-events-none');
        }, 3000);
    }

    /**
     * Bildirim Tipi İkon & Renk Bilgileri
     */
    function getTypeConfig(type) {
        switch (type) {
            case 'success':
                return {
                    icon: 'check_circle',
                    bg: 'bg-emerald-50 text-[#19924B] border border-emerald-200/60'
                };
            case 'warning':
                return {
                    icon: 'warning',
                    bg: 'bg-amber-50 text-[#F5B054] border border-amber-200/60'
                };
            case 'error':
                return {
                    icon: 'cancel',
                    bg: 'bg-red-50 text-[#ba1a1a] border border-red-200/60'
                };
            case 'info':
            default:
                return {
                    icon: 'notifications',
                    bg: 'bg-blue-50 text-[#0284c7] border border-blue-200/60'
                };
        }
    }

    /**
     * Panelin Konumunu Hesapla
     */
    function updateDropdownPosition() {
        if (!dropdownEl || !notifBtn) return;
        const rect = notifBtn.getBoundingClientRect();
        
        // Ekranın sağına taşmayacak şekilde sağa hizalama
        const rightOffset = Math.max(12, window.innerWidth - rect.right);
        const topOffset = rect.bottom + 8;

        dropdownEl.style.top = `${topOffset}px`;
        dropdownEl.style.right = `${rightOffset}px`;
    }

    /**
     * Paneli Aç / Kapat
     */
    function toggleDropdown(open) {
        if (!dropdownEl) return;
        isPanelOpen = typeof open === 'boolean' ? open : !isPanelOpen;

        if (isPanelOpen) {
            updateDropdownPosition();
            dropdownEl.classList.remove('hidden');
            // Animasyon için frame bekle
            requestAnimationFrame(() => {
                dropdownEl.classList.remove('opacity-0', 'scale-95', 'translate-y-[-8px]');
                dropdownEl.classList.add('opacity-100', 'scale-100', 'translate-y-0');
            });
            renderDropdownContent();
        } else {
            dropdownEl.classList.remove('opacity-100', 'scale-100', 'translate-y-0');
            dropdownEl.classList.add('opacity-0', 'scale-95', 'translate-y-[-8px]');
            setTimeout(() => {
                if (!isPanelOpen) {
                    dropdownEl.classList.add('hidden');
                }
            }, 180);
        }
    }

    /**
     * Dropdown HTML İçeriğini Render Et
     */
    function renderDropdownContent() {
        if (!dropdownEl) return;

        const unreadCount = getUnreadCount();

        if (currentView === 'history') {
            renderHistoryView(unreadCount);
        } else {
            renderListView(unreadCount);
        }
    }

    /**
     * 1. Ana Liste Görünümü
     */
    function renderListView(unreadCount) {
        const filtered = notifications.filter(n => {
            if (currentTab === 'islem') return n.category === 'islem';
            if (currentTab === 'uyari') return n.category === 'uyari';
            return true;
        });

        const islemCount = notifications.filter(n => n.category === 'islem' && !n.read).length;
        const uyariCount = notifications.filter(n => n.category === 'uyari' && !n.read).length;

        dropdownEl.innerHTML = `
            <div class="flex flex-col h-full max-h-[480px]">
                <!-- Header -->
                <div class="px-4 py-3.5 border-b border-slate-100 flex items-center justify-between bg-white rounded-t-2xl">
                    <div class="flex items-center gap-2">
                        <span class="font-headline-md font-bold text-slate-800 text-sm">Bildirimler</span>
                        ${unreadCount > 0 
                            ? `<span class="px-2 py-0.5 bg-[#ba1a1a]/10 text-[#ba1a1a] text-[11px] font-semibold rounded-full">${unreadCount} Okunmamış</span>`
                            : `<span class="px-2 py-0.5 bg-slate-100 text-slate-500 text-[11px] font-medium rounded-full">Tümü Okundu</span>`
                        }
                    </div>
                    <button id="markAllReadBtn" class="flex items-center gap-1 text-xs font-medium text-primary hover:text-emerald-800 transition-colors p-1 rounded hover:bg-emerald-50/60 cursor-pointer" title="Tümünü Okundu İşaretle">
                        <span class="material-symbols-outlined text-[16px]">done_all</span>
                        <span>Tümünü Okundu İşaretle</span>
                    </button>
                </div>

                <!-- Filtre Sekmeleri -->
                <div class="p-2 bg-slate-50/80 border-b border-slate-100 flex gap-1.5 text-xs">
                    <button data-tab="all" class="tab-btn flex-1 py-1.5 px-2 rounded-lg font-medium transition-all text-center flex items-center justify-center gap-1 cursor-pointer ${
                        currentTab === 'all'
                            ? 'bg-primary text-white shadow-sm'
                            : 'text-slate-600 hover:bg-white/80 hover:text-slate-900'
                    }">
                        <span>Tümü</span>
                        <span class="text-[10px] opacity-80">(${notifications.length})</span>
                    </button>
                    <button data-tab="islem" class="tab-btn flex-1 py-1.5 px-2 rounded-lg font-medium transition-all text-center flex items-center justify-center gap-1 cursor-pointer ${
                        currentTab === 'islem'
                            ? 'bg-primary text-white shadow-sm'
                            : 'text-slate-600 hover:bg-white/80 hover:text-slate-900'
                    }">
                        <span>İşlem / Raporlama</span>
                        ${islemCount > 0 ? `<span class="w-2 h-2 rounded-full bg-amber-400"></span>` : ''}
                    </button>
                    <button data-tab="uyari" class="tab-btn flex-1 py-1.5 px-2 rounded-lg font-medium transition-all text-center flex items-center justify-center gap-1 cursor-pointer ${
                        currentTab === 'uyari'
                            ? 'bg-primary text-white shadow-sm'
                            : 'text-slate-600 hover:bg-white/80 hover:text-slate-900'
                    }">
                        <span>Sistem Uyarıları</span>
                        ${uyariCount > 0 ? `<span class="w-2 h-2 rounded-full bg-[#ba1a1a]"></span>` : ''}
                    </button>
                </div>

                <!-- Bildirim Listesi -->
                <div class="flex-1 overflow-y-auto divide-y divide-slate-100 max-h-[320px] custom-scrollbar bg-white">
                    ${renderNotificationItems(filtered)}
                </div>

                <!-- Footer -->
                <div class="p-2.5 border-t border-slate-100 bg-slate-50/60 rounded-b-2xl flex items-center justify-center">
                    <button id="viewHistoryBtn" class="w-full py-1.5 px-3 rounded-lg text-xs font-semibold text-primary hover:bg-primary/10 transition-colors flex items-center justify-center gap-1.5 cursor-pointer">
                        <span class="material-symbols-outlined text-[16px]">history</span>
                        <span>Tüm Bildirim Geçmişini Gör</span>
                    </button>
                </div>
            </div>
        `;

        bindListEvents();
    }

    /**
     * 2. Geçmiş Görünümü
     */
    function renderHistoryView(unreadCount) {
        dropdownEl.innerHTML = `
            <div class="flex flex-col h-full max-h-[480px]">
                <!-- Header with Back Button -->
                <div class="px-4 py-3.5 border-b border-slate-100 flex items-center justify-between bg-white rounded-t-2xl">
                    <div class="flex items-center gap-2">
                        <button id="backToListBtn" class="p-1 rounded-lg text-slate-500 hover:text-primary hover:bg-slate-100 transition-colors flex items-center justify-center cursor-pointer" title="Geri Dön">
                            <span class="material-symbols-outlined text-[20px]">arrow_back</span>
                        </button>
                        <span class="font-headline-md font-bold text-slate-800 text-sm">Bildirim Geçmişi</span>
                        <span class="px-2 py-0.5 bg-slate-100 text-slate-600 text-[11px] font-medium rounded-full">${notifications.length} Kayıt</span>
                    </div>
                    ${unreadCount > 0 ? `
                        <button id="markAllReadBtn" class="flex items-center gap-1 text-xs font-medium text-primary hover:text-emerald-800 transition-colors p-1 rounded hover:bg-emerald-50/60 cursor-pointer" title="Tümünü Okundu İşaretle">
                            <span class="material-symbols-outlined text-[16px]">done_all</span>
                            <span>Tümünü Okundu</span>
                        </button>
                    ` : ''}
                </div>

                <!-- Tüm Bildirimler (Filtresiz) -->
                <div class="flex-1 overflow-y-auto divide-y divide-slate-100 max-h-[380px] custom-scrollbar bg-white">
                    ${renderNotificationItems(notifications)}
                </div>

                <!-- Footer -->
                <div class="p-2.5 border-t border-slate-100 bg-slate-50/60 rounded-b-2xl flex items-center justify-between px-4 text-[11px] text-slate-400">
                    <span>Toplam ${notifications.length} bildirim kaydı</span>
                    <button id="backToListFooterBtn" class="text-primary hover:underline font-medium cursor-pointer">Ana Görünüme Dön</button>
                </div>
            </div>
        `;

        bindHistoryEvents();
    }

    /**
     * Bildirim Elemanlarını HTML'e dönüştür
     */
    function renderNotificationItems(items) {
        if (!items || items.length === 0) {
            if (notifications.length === 0) {
                return `
                    <div class="py-12 px-6 flex flex-col items-center justify-center text-center text-slate-400">
                        <div class="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-3">
                            <span class="material-symbols-outlined text-slate-400 text-2xl">notifications_off</span>
                        </div>
                        <p class="text-xs font-semibold text-slate-700">Henüz yeni bir bildiriminiz yok.</p>
                        <p class="text-[11px] text-slate-400 mt-1">Bildirimleriniz burada görünecek.</p>
                    </div>
                `;
            }
            return `
                <div class="py-10 px-6 flex flex-col items-center justify-center text-center text-slate-400">
                    <span class="material-symbols-outlined text-slate-300 text-3xl mb-2">filter_alt_off</span>
                    <p class="text-xs font-medium text-slate-600">Bu kategoride bildirim bulunamadı.</p>
                </div>
            `;
        }

        return items.map(item => {
            const config = getTypeConfig(item.type);
            const timeText = formatRelativeTime(item.timestamp);
            const isUnread = !item.read;

            return `
                <div data-id="${item.id}" class="notif-item group relative px-4 py-3 transition-colors cursor-pointer flex gap-3 items-start ${
                    isUnread ? 'bg-[#F8FAFC] hover:bg-slate-100/90' : 'bg-white hover:bg-slate-50/90'
                }">
                    <!-- İkon -->
                    <div class="shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${config.bg} shadow-2xs mt-0.5">
                        <span class="material-symbols-outlined text-[18px]">${config.icon}</span>
                    </div>

                    <!-- İçerik -->
                    <div class="flex-1 min-w-0 pr-3">
                        <div class="flex items-center justify-between gap-2">
                            <h4 class="text-xs font-bold text-slate-900 truncate leading-snug">${escapeHtml(item.title)}</h4>
                            <span class="text-[10px] text-slate-400 font-mono shrink-0">${timeText}</span>
                        </div>
                        <p class="text-xs text-slate-600 mt-1 leading-relaxed break-words">${escapeHtml(item.message)}</p>
                        
                        ${item.action && item.action.type === 'pdf_download' ? `
                            <div class="mt-2">
                                <span class="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-50 hover:bg-emerald-100 text-primary border border-emerald-200/80 rounded text-[11px] font-semibold transition-colors">
                                    <span class="material-symbols-outlined text-[13px]">picture_as_pdf</span>
                                    <span>${escapeHtml(item.action.filename || 'PDF Raporu')}</span>
                                </span>
                            </div>
                        ` : ''}
                    </div>

                    <!-- Okunmamış Göstergesi (Yeşil Nokta) -->
                    ${isUnread ? `
                        <div class="shrink-0 self-center">
                            <span class="inline-block w-2.5 h-2.5 rounded-full bg-[#19924B] shadow-xs" title="Okunmadı"></span>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');
    }

    /**
     * Liste Görünümü Event Bağlantıları
     */
    function bindListEvents() {
        // Tümünü Okundu Butonu
        const markAllBtn = dropdownEl.querySelector('#markAllReadBtn');
        if (markAllBtn) {
            markAllBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                markAllAsRead();
            });
        }

        // Sekmeler
        const tabBtns = dropdownEl.querySelectorAll('.tab-btn');
        tabBtns.forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const tab = btn.dataset.tab;
                if (tab && tab !== currentTab) {
                    currentTab = tab;
                    renderDropdownContent();
                }
            });
        });

        // Geçmiş Görünümü Butonu
        const viewHistoryBtn = dropdownEl.querySelector('#viewHistoryBtn');
        if (viewHistoryBtn) {
            viewHistoryBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                currentView = 'history';
                renderDropdownContent();
            });
        }

        // Bildirim Kartlarına Tıklama
        bindItemClicks();
    }

    /**
     * Geçmiş Görünümü Event Bağlantıları
     */
    function bindHistoryEvents() {
        const backBtn = dropdownEl.querySelector('#backToListBtn');
        const backFooterBtn = dropdownEl.querySelector('#backToListFooterBtn');
        const markAllBtn = dropdownEl.querySelector('#markAllReadBtn');

        const goBack = (e) => {
            e.stopPropagation();
            currentView = 'list';
            renderDropdownContent();
        };

        if (backBtn) backBtn.addEventListener('click', goBack);
        if (backFooterBtn) backFooterBtn.addEventListener('click', goBack);

        if (markAllBtn) {
            markAllBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                markAllAsRead();
            });
        }

        bindItemClicks();
    }

    /**
     * Bildirim Öğelerine Tıklama İşleyicisi
     */
    function bindItemClicks() {
        const items = dropdownEl.querySelectorAll('.notif-item');
        items.forEach(el => {
            el.addEventListener('click', (e) => {
                e.stopPropagation();
                const notifId = el.dataset.id;
                const notif = notifications.find(n => n.id === notifId);
                if (!notif) return;

                // Okundu olarak işaretle
                markAsRead(notifId);

                // Aksiyon varsa tetikle
                if (notif.action && notif.action.type === 'pdf_download') {
                    showToast(`📄 ${notif.action.filename} raporu açılıyor...`);
                }
            });
        });
    }

    /**
     * HTML Kaçış Yardımcısı
     */
    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Bildirim Merkezini Başlat
     */
    function init() {
        // Çan Butonunu Bul
        notifBtn = document.getElementById('notificationsBtn');
        if (!notifBtn) {
            // ID yoksa title="Bildirimler" veya notifications iconu içeren butonu bul ve ID ekle
            const candidate = document.querySelector('button[title="Bildirimler"]') ||
                document.querySelector('button span.material-symbols-outlined:contains("notifications")')?.closest('button');
            if (candidate) {
                notifBtn = candidate;
                notifBtn.id = 'notificationsBtn';
            }
        }

        if (!notifBtn) {
            console.warn('[NotificationCenter] notificationsBtn elementi bulunamadı.');
            return;
        }

        // Buton pozisyonlamasını ve stilini hazırla
        notifBtn.classList.add('relative');

        // Rozet (Badge) Elemanını Oluştur
        badgeEl = document.getElementById('notificationsBadge');
        if (!badgeEl) {
            badgeEl = document.createElement('span');
            badgeEl.id = 'notificationsBadge';
            badgeEl.className = 'absolute -top-1 -right-1 min-w-[17px] h-[17px] px-1 bg-[#ba1a1a] text-white text-[10px] font-bold rounded-full flex items-center justify-center border-2 border-white shadow-xs leading-none pointer-events-none transition-all duration-200';
            notifBtn.appendChild(badgeEl);
        }

        // Dropdown Panel Elemanını Oluştur
        dropdownEl = document.getElementById('notificationsDropdown');
        if (!dropdownEl) {
            dropdownEl = document.createElement('div');
            dropdownEl.id = 'notificationsDropdown';
            dropdownEl.className = 'fixed w-[380px] max-w-[calc(100vw-1.5rem)] bg-white border border-slate-200/90 rounded-2xl shadow-2xl z-[60] overflow-hidden transition-all duration-200 transform origin-top-right hidden opacity-0 scale-95 translate-y-[-8px]';
            document.body.appendChild(dropdownEl);
        }

        // Verileri Yükle ve Rozeti Ayarla
        loadNotifications();
        updateBadge();

        // Buton Tıklama
        notifBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown();
        });

        // Dışarı Tıklama ile Kapatma
        document.addEventListener('click', (e) => {
            if (isPanelOpen && dropdownEl && !dropdownEl.contains(e.target) && !notifBtn.contains(e.target)) {
                toggleDropdown(false);
            }
        });

        // Esc Tuşu ile Kapatma
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && isPanelOpen) {
                toggleDropdown(false);
            }
        });

        // Pencere Boyutu Değişirse Konumu Güncelle
        window.addEventListener('resize', () => {
            if (isPanelOpen) updateDropdownPosition();
        });
        window.addEventListener('scroll', () => {
            if (isPanelOpen) updateDropdownPosition();
        }, { passive: true });

        // Storage Olayı (Farklı sekmelerde senkronize olması için)
        window.addEventListener('storage', (e) => {
            if (e.key === STORAGE_KEY) {
                loadNotifications();
                updateBadge();
                if (isPanelOpen) renderDropdownContent();
            }
        });
    }

    // DOM Hazır Olunca Başlat
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
