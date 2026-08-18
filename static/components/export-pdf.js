document.addEventListener('DOMContentLoaded', function () {
    const btns = document.querySelectorAll('#exportPdfBtn, #exportPdfBtnAlt');
    if (!btns.length) return;

    btns.forEach(function (btn) {
        btn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            openExportModal(btn);
        });
    });

    function getMain() { return document.querySelector('main'); }

    function collectSections() {
        const main = getMain();
        if (!main) return [];
        const sections = main.querySelectorAll('[data-export-section]');
        const items = [];
        sections.forEach(function (sec, i) {
            items.push({
                el: sec,
                title: sec.getAttribute('data-export-title') || ('Bölüm ' + (i + 1))
            });
        });
        return items;
    }

    function openExportModal(activeBtn) {
        let items = collectSections();
        const useWhole = items.length === 0;
        if (useWhole) {
            const main = getMain();
            if (!main) { alert('Dışa aktarılacak içerik bulunamadı.'); return; }
            items = [{ el: main, title: 'Tüm Sayfa İçeriği' }];
        }

        // Remove existing modal if any
        const existing = document.getElementById('exportModal');
        if (existing) existing.remove();

        const overlay = document.createElement('div');
        overlay.id = 'exportModal';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.6);backdrop-filter:blur(4px);z-index:99999;display:flex;align-items:center;justify-content:center;padding:16px;';
        overlay.innerHTML =
            '<div style="background:#ffffff;border-radius:16px;width:100%;max-width:500px;max-height:85vh;overflow:hidden;box-shadow:0 25px 60px rgba(0,0,0,0.35);display:flex;flex-direction:column;font-family:Inter,system-ui,sans-serif;color:#1e293b;">' +
              '<div style="display:flex;justify-content:space-between;align-items:center;padding:18px 22px;border-bottom:1px solid #e2e8f0;background:#f8fafc;">' +
                '<div>' +
                  '<h3 style="margin:0;font-size:17px;font-weight:700;color:#002812;">PDF Dışa Aktar</h3>' +
                  '<p style="margin:2px 0 0 0;font-size:12px;color:#64748b;">Raporunuza dahil etmek istediğiniz bölümleri seçin</p>' +
                '</div>' +
                '<button id="exportModalClose" style="background:none;border:none;font-size:24px;cursor:pointer;color:#64748b;line-height:1;padding:4px 8px;border-radius:6px;">&times;</button>' +
              '</div>' +
              '<div style="padding:12px 22px;border-bottom:1px solid #f1f5f9;display:flex;justify-content:space-between;align-items:center;background:#ffffff;">' +
                '<span style="font-size:13px;font-weight:600;color:#475569;">Bölüm Listesi (' + items.length + ')</span>' +
                '<button id="exportSelectAll" style="background:#f1f5f9;border:1px solid #cbd5e1;color:#006b33;border-radius:6px;padding:5px 12px;font-size:12px;font-weight:600;cursor:pointer;">Tümünü Seç / Kaldır</button>' +
              '</div>' +
              '<div id="exportSectionList" style="padding:12px 22px;overflow-y:auto;flex:1;max-height:360px;">' +
                items.map(function (it, i) {
                    return '<label style="display:flex;align-items:center;gap:12px;padding:10px 12px;margin-bottom:6px;cursor:pointer;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;font-size:13px;font-weight:500;color:#1e293b;transition:background 0.15s;">' +
                           '<input type="checkbox" data-export-idx="' + i + '" checked style="width:17px;height:17px;accent-color:#006b33;cursor:pointer;"/>' +
                           '<span style="flex:1;">' + it.title + '</span></label>';
                }).join('') +
              '</div>' +
              '<div style="padding:16px 22px;border-top:1px solid #e2e8f0;background:#f8fafc;display:flex;justify-content:flex-end;gap:10px;">' +
                '<button id="exportModalCancel" style="background:#ffffff;border:1px solid #cbd5e1;color:#475569;border-radius:8px;padding:9px 18px;font-size:13px;font-weight:600;cursor:pointer;">Vazgeç</button>' +
                '<button id="exportModalConfirm" style="background:#006b33;border:none;color:#ffffff;border-radius:8px;padding:9px 22px;font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:6px;">' +
                  '<span>PDF Oluştur</span>' +
                '</button>' +
              '</div>' +
            '</div>';

        document.body.appendChild(overlay);
        overlay.addEventListener('click', function (ev) { if (ev.target === overlay) closeModal(); });
        overlay.querySelector('#exportModalClose').addEventListener('click', closeModal);
        overlay.querySelector('#exportModalCancel').addEventListener('click', closeModal);
        
        let allCheckedState = true;
        overlay.querySelector('#exportSelectAll').addEventListener('click', function () {
            const cbs = overlay.querySelectorAll('[data-export-idx]');
            allCheckedState = !allCheckedState;
            cbs.forEach(c => c.checked = allCheckedState);
        });

        overlay.querySelector('#exportModalConfirm').addEventListener('click', function () {
            const idxs = Array.from(overlay.querySelectorAll('[data-export-idx]'))
                .filter(c => c.checked)
                .map(c => parseInt(c.getAttribute('data-export-idx')));
            if (!idxs.length) { alert('Lütfen en az bir bölüm seçin.'); return; }
            
            const confirmBtn = overlay.querySelector('#exportModalConfirm');
            confirmBtn.disabled = true;
            confirmBtn.style.opacity = '0.7';
            confirmBtn.innerHTML = '<span>PDF Hazırlanıyor...</span>';

            setTimeout(function () {
                const selected = items.filter(function (_, i) { return idxs.indexOf(i) !== -1; });
                closeModal();
                buildAndExport(selected, useWhole, activeBtn);
            }, 50);
        });

        function closeModal() {
            if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        }
    }

    function cloneSectionWithCanvases(originalEl) {
        const clone = originalEl.cloneNode(true);

        // 1. Convert all canvases in the original into real images in the clone
        const origCanvases = originalEl.querySelectorAll('canvas');
        const cloneCanvases = clone.querySelectorAll('canvas');
        for (let i = 0; i < origCanvases.length; i++) {
            const origCv = origCanvases[i];
            const cloneCv = cloneCanvases[i];
            if (origCv && cloneCv) {
                try {
                    const img = document.createElement('img');
                    img.src = origCv.toDataURL('image/png');
                    img.style.width = '100%';
                    img.style.height = 'auto';
                    img.style.display = 'block';
                    img.style.maxHeight = '420px';
                    img.style.objectFit = 'contain';
                    if (cloneCv.parentNode) {
                        cloneCv.parentNode.replaceChild(img, cloneCv);
                    }
                } catch (e) {
                    console.warn('Canvas to image conversion warning:', e);
                }
            }
        }

        // 2. Remove interactive buttons and inputs from the clone
        clone.querySelectorAll('button, select, input, #dropZone, #searchInput').forEach(function (el) {
            // Keep preview search or badge text if needed, but remove action buttons
            if (el.tagName === 'BUTTON' || el.tagName === 'SELECT') {
                el.remove();
            }
        });

        // 3. Ensure cards inside clone have clean styling
        clone.style.backgroundColor = '#ffffff';
        clone.style.color = '#1e293b';
        clone.style.boxShadow = 'none';

        return clone;
    }

    function buildAndExport(selected, useWhole, activeBtn) {
        if (typeof html2pdf === 'undefined') {
            alert('PDF kütüphanesi yüklenemedi. Lütfen internet bağlantınızı kontrol edip sayfayı yenileyin.');
            return;
        }

        // Create container positioned in DOM but below normal view
        const holder = document.createElement('div');
        holder.id = 'exportHolder';
        holder.style.cssText = 'position:absolute;left:0;top:0;width:1040px;background:#ffffff;color:#1e293b;z-index:0;opacity:0.01;pointer-events:none;padding:32px;box-sizing:border-box;font-family:Inter,system-ui,sans-serif;';

        // Header
        const reportHeader = document.createElement('div');
        reportHeader.style.cssText = 'margin-bottom:28px;padding-bottom:16px;border-bottom:2px solid #006b33;display:flex;justify-content:space-between;align-items:center;';
        reportHeader.innerHTML =
            '<div>' +
              '<h1 style="font-size:22px;font-weight:800;color:#002812;margin:0 0 4px 0;letter-spacing:-0.02em;">trex DataLab Analiz Raporu</h1>' +
              '<p style="font-size:12px;color:#64748b;margin:0;">Rapor Tarihi: ' + new Date().toLocaleString('tr-TR') + '</p>' +
            '</div>' +
            '<div style="font-size:12px;font-weight:700;color:#006b33;background:#f0fdf4;padding:6px 14px;border-radius:8px;border:1px solid #bbf7d0;letter-spacing:0.05em;text-transform:uppercase;">' +
              'trex DataLab' +
            '</div>';
        holder.appendChild(reportHeader);

        // Sections
        selected.forEach(function (item) {
            const clone = cloneSectionWithCanvases(item.el);
            clone.style.marginBottom = '24px';
            clone.style.breakInside = 'avoid';
            clone.style.pageBreakInside = 'avoid';
            holder.appendChild(clone);
        });

        document.body.appendChild(holder);

        const filename = (activeBtn && activeBtn.getAttribute('data-filename')) || 'trex_datalab_rapor';

        const opt = {
            margin: [8, 8, 8, 8],
            filename: filename + '.pdf',
            image: { type: 'jpeg', quality: 0.98 },
            html2canvas: {
                scale: 2,
                useCORS: true,
                logging: false,
                backgroundColor: '#ffffff',
                scrollY: 0,
                scrollX: 0,
                windowWidth: 1040,
                onclone: function (clonedDoc) {
                    const el = clonedDoc.getElementById('exportHolder');
                    if (el) {
                        el.style.position = 'static';
                        el.style.opacity = '1';
                        el.style.zIndex = '0';
                        el.style.left = '0';
                        el.style.top = '0';
                        el.style.margin = '0';
                        el.style.width = '794px';
                        el.style.padding = '32px';
                        el.style.boxSizing = 'border-box';
                    }
                    // Klonda arayüz öğelerini temizle (güvence)
                    clonedDoc.querySelectorAll('nav, aside, header, #exportModal, #chartZoomModal, #notificationsPanel, #profileMenu, .fixed').forEach(function (el) {
                        if (el && el.parentNode) el.parentNode.removeChild(el);
                    });
                }
            },
            jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
            pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
        };

        html2pdf()
            .set(opt)
            .from(holder)
            .save()
            .then(function () {
                if (holder.parentNode) holder.parentNode.removeChild(holder);
            })
            .catch(function (err) {
                console.error('PDF oluşturulurken hata:', err);
                if (holder.parentNode) holder.parentNode.removeChild(holder);
                alert('PDF oluşturulamadı. Lütfen tekrar deneyin.');
            });
    }
});
