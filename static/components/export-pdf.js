document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('exportPdfBtn');
    if (!btn) return;

    btn.addEventListener('click', function (e) {
        e.preventDefault();
        e.stopPropagation();
        openExportModal();
    });

    function getMain() { return document.querySelector('main'); }

    function collectSections() {
        const main = getMain();
        if (!main) return [];
        const sections = main.querySelectorAll('[data-export-section]');
        const items = [];
        sections.forEach(function (sec, i) {
            items.push({ el: sec, title: sec.getAttribute('data-export-title') || ('Bölüm ' + (i + 1)) });
        });
        return items;
    }

    function openExportModal() {
        let items = collectSections();
        const useWhole = items.length === 0;
        if (useWhole) {
            const main = getMain();
            if (!main) { alert('Dışa aktarılacak içerik bulunamadı.'); return; }
            items = [{ el: main, title: 'Tüm İçerik' }];
        }

        const overlay = document.createElement('div');
        overlay.id = 'exportModal';
        overlay.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:99999;display:flex;align-items:center;justify-content:center;';
        overlay.innerHTML =
            '<div style="background:#fff;border-radius:16px;width:90%;max-width:460px;max-height:80vh;overflow:hidden;box-shadow:0 20px 50px rgba(0,0,0,0.3);display:flex;flex-direction:column;">' +
              '<div style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid #E2E8F0;">' +
                '<h3 style="margin:0;font-size:16px;font-weight:700;color:#002812;font-family:Inter,system-ui,sans-serif;">PDF Dışa Aktar</h3>' +
                '<button id="exportModalClose" style="background:none;border:none;font-size:22px;cursor:pointer;color:#4A5568;line-height:1;">×</button>' +
              '</div>' +
              '<div style="padding:12px 20px;border-bottom:1px solid #E2E8F0;display:flex;justify-content:space-between;align-items:center;">' +
                '<span style="font-size:14px;color:#4A5568;font-family:Inter,system-ui,sans-serif;">Eklenecek bölümleri seç:</span>' +
                '<button id="exportSelectAll" style="background:none;border:1px solid #006b33;color:#006b33;border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer;font-family:Inter,system-ui,sans-serif;">Tümünü Seç</button>' +
              '</div>' +
              '<div id="exportSectionList" style="padding:10px 20px;overflow-y:auto;flex:1;">' +
                items.map(function (it, i) {
                    return '<label style="display:flex;align-items:center;gap:10px;padding:9px 0;cursor:pointer;border-bottom:1px solid #F1F5F9;font-family:Inter,system-ui,sans-serif;font-size:14px;color:#1a202c;">' +
                           '<input type="checkbox" data-export-idx="' + i + '" checked style="width:16px;height:16px;accent-color:#006b33;"/>' +
                           '<span>' + it.title + '</span></label>';
                }).join('') +
              '</div>' +
              '<div style="padding:16px 20px;border-top:1px solid #E2E8F0;display:flex;justify-content:flex-end;gap:10px;">' +
                '<button id="exportModalCancel" style="background:#fff;border:1px solid #CBD5E0;color:#4A5568;border-radius:8px;padding:9px 18px;font-size:14px;cursor:pointer;font-family:Inter,system-ui,sans-serif;">Vazgeç</button>' +
                '<button id="exportModalConfirm" style="background:#006b33;border:none;color:#fff;border-radius:8px;padding:9px 18px;font-size:14px;cursor:pointer;font-family:Inter,system-ui,sans-serif;">PDF Oluştur</button>' +
              '</div>' +
            '</div>';

        document.body.appendChild(overlay);
        overlay.addEventListener('click', function (ev) { if (ev.target === overlay) closeModal(); });
        overlay.querySelector('#exportModalClose').addEventListener('click', closeModal);
        overlay.querySelector('#exportModalCancel').addEventListener('click', closeModal);
        overlay.querySelector('#exportSelectAll').addEventListener('click', function () {
            const cbs = overlay.querySelectorAll('[data-export-idx]');
            const allChecked = Array.from(cbs).every(c => c.checked);
            cbs.forEach(c => c.checked = !allChecked);
        });
        overlay.querySelector('#exportModalConfirm').addEventListener('click', function () {
            const idxs = Array.from(overlay.querySelectorAll('[data-export-idx]'))
                .filter(c => c.checked)
                .map(c => parseInt(c.getAttribute('data-export-idx')));
            if (!idxs.length) { alert('En az bir bölüm seçmelisiniz.'); return; }
            closeModal();
            const selected = items.filter(function (_, i) { return idxs.indexOf(i) !== -1; });
            buildAndExport(selected, useWhole);
        });

        function closeModal() {
            if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
        }
    }

    function buildAndExport(selected, useWhole) {
        if (typeof html2pdf === 'undefined') {
            alert('html2pdf kütüphanesi yüklenemedi. İnternet bağlantınızı kontrol edin.');
            return;
        }
        const wrapper = document.createElement('div');
        wrapper.style.cssText = 'position:absolute;left:-9999px;top:0;width:1240px;';
        selected.forEach(function (item) {
            const clone = item.el.cloneNode(true);
            clone.style.width = '100%';
            wrapper.appendChild(clone);
        });
        document.body.appendChild(wrapper);

        const filename = btn.getAttribute('data-filename') || 'trex_datalab_rapor';

        html2pdf()
            .set({
                margin: 10,
                filename: filename + '.pdf',
                image: { type: 'jpeg', quality: 0.98 },
                html2canvas: { scale: 2, useCORS: true, windowWidth: document.documentElement.scrollWidth },
                jsPDF: { unit: 'mm', format: 'a4', orientation: 'portrait' },
                pagebreak: { mode: ['avoid-all', 'css', 'legacy'] }
            })
            .from(wrapper)
            .save()
            .then(function () { document.body.removeChild(wrapper); })
            .catch(function (err) {
                console.error('PDF oluşturulurken hata:', err);
                document.body.removeChild(wrapper);
                alert('PDF oluşturulamadı. Lütfen tekrar deneyin.');
            });
    }
});
