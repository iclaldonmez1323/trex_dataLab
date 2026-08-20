(function () {
    if (window.trexExportManager) return;
    window.trexExportManager = true;

    var API_BASE = (location.protocol === 'file:' || location.protocol === 'about:') ? 'http://127.0.0.1:8000' : '';

    function currentPage() {
        return location.pathname.split('/').pop() || 'index.html';
    }

    // ---------- Modal HTML ----------
    function buildModal() {
        if (document.getElementById('trexExportModal')) return;
        var m = document.createElement('div');
        m.id = 'trexExportModal';
        m.innerHTML = `
            <style>
                #trexExportModal { display: none; position: fixed; inset: 0; z-index: 9995; background: rgba(0,0,0,.55);
                    backdrop-filter: blur(4px); align-items: center; justify-content: center; padding: 16px; font-family: 'Inter', system-ui, -apple-system, sans-serif; }
                #trexExportModal.open { display: flex; }
                .trex-export-card { background: #fcf9f8; border: 1px solid #e2e8f0; border-radius: 18px; width: 100%; max-width: 560px;
                    max-height: 90vh; overflow-y: auto; box-shadow: 0 24px 60px rgba(0,0,0,.25); }
                .trex-export-head { padding: 16px 20px; border-bottom: 1px solid #e2e8f0; display: flex; align-items: center; justify-content: space-between; }
                .trex-export-head h3 { font-size: 15px; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 8px; margin: 0; }
                .trex-export-head .material-symbols-outlined { color: #006b33; font-size: 20px; }
                .trex-export-body { padding: 18px 20px; display: flex; flex-direction: column; gap: 14px; }
                .trex-export-opt { border: 1.5px solid #e2e8f0; border-radius: 12px; padding: 14px 16px; cursor: pointer;
                    transition: border-color .15s, background .15s; background: #fff; user-select: none; }
                .trex-export-opt:hover { border-color: #006b33; background: #f0fdf4; }
                .trex-export-opt.active { border-color: #006b33; background: #f0fdf4; }
                .trex-export-opt .t-title { font-size: 13px; font-weight: 700; color: #1e293b; display: flex; align-items: center; gap: 8px; }
                .trex-export-opt .t-sub { font-size: 11px; color: #64748b; margin-top: 3px; }
                .trex-export-opt .material-symbols-outlined { color: #006b33; font-size: 20px; }
                #trexExportSections { display: none; border: 1px solid #e2e8f0; border-radius: 12px; padding: 12px 14px; background: #fff; max-height: 240px; overflow-y: auto; }
                #trexExportSections.show { display: block; }
                .trex-sec-item { display: flex; align-items: center; gap: 10px; padding: 7px 4px; font-size: 12px; color: #334155; border-bottom: 1px dashed #eef2f7; cursor: pointer; }
                .trex-sec-item:last-child { border-bottom: none; }
                .trex-sec-item input { accent-color: #006b33; width: 15px; height: 15px; cursor: pointer; }
                .trex-export-actions { display: flex; justify-content: flex-end; gap: 10px; padding: 0 20px 18px; }
                .trex-btn { border-radius: 10px; padding: 9px 18px; font-size: 12px; font-weight: 600; cursor: pointer; border: none; transition: background .15s, opacity .15s; }
                .trex-btn-ghost { background: #e2e8f0; color: #334155; }
                .trex-btn-ghost:hover { background: #cbd5e1; }
                .trex-btn-primary { background: #006b33; color: #fff; }
                .trex-btn-primary:hover { background: #008742; }
                .trex-btn:disabled { opacity: 0.6; cursor: not-allowed; }
                .trex-export-status { padding: 12px 20px 0; font-size: 12px; font-weight: 500; color: #006b33; display: none; }
                .trex-export-status.err { color: #ba1a1a; }
            </style>
            <div class="trex-export-card">
                <div class="trex-export-head">
                    <h3><span class="material-symbols-outlined">download</span> Dışa Aktar</h3>
                    <button id="trexExportClose" class="text-slate-400 hover:text-[#ba1a1a] text-2xl leading-none cursor-pointer bg-transparent border-0" style="padding:0;line-height:1;">×</button>
                </div>
                <div id="trexExportStatus" class="trex-export-status"></div>
                <div class="trex-export-body">
                    <div class="trex-export-opt active" data-opt="csv">
                        <div class="t-title"><span class="material-symbols-outlined">table_view</span> CSV Olarak İndir</div>
                        <div class="t-sub">Güncel işlenmiş veri setini (CSV) indirir.</div>
                    </div>
                    <div class="trex-export-opt" data-opt="pdf">
                        <div class="t-title"><span class="material-symbols-outlined">picture_as_pdf</span> PDF Olarak İndir</div>
                        <div class="t-sub">Raporu PDF olarak kaydeder. Altında bölüm seçimi yapabilirsiniz.</div>
                    </div>
                    <div id="trexExportSections">
                        <!-- data-export-section'lardan dinamik checkbox listesi -->
                    </div>
                </div>
                <div class="trex-export-actions">
                    <button id="trexExportCancel" class="trex-btn trex-btn-ghost">Vazgeç</button>
                    <button id="trexExportGo" class="trex-btn trex-btn-primary">Dışa Aktar</button>
                </div>
            </div>
        `;
        document.body.appendChild(m);
    }

    function openModal() {
        buildModal();
        var modal = document.getElementById('trexExportModal');
        var optPdf = modal.querySelector('[data-opt="pdf"]');
        if (optPdf) optPdf.classList.remove('active');
        var optCsv = modal.querySelector('[data-opt="csv"]');
        if (optCsv) optCsv.classList.add('active');
        var sectionsBox = document.getElementById('trexExportSections');
        if (sectionsBox) {
            sectionsBox.classList.remove('show');
            sectionsBox.innerHTML = '';
        }
        var status = document.getElementById('trexExportStatus');
        if (status) {
            status.style.display = 'none';
            status.textContent = '';
            status.className = 'trex-export-status';
        }
        modal.classList.add('open');
    }

    function closeModal() {
        var modal = document.getElementById('trexExportModal');
        if (modal) modal.classList.remove('open');
    }

    function gatherSections() {
        var list = [];
        document.querySelectorAll('[data-export-section]').forEach(function (el, index) {
            var title = el.getAttribute('data-export-title') || el.getAttribute('data-export-section') || ('Bölüm ' + (index + 1));
            var id = (el.getAttribute('data-export-section') || 'sec') + '_' + index;
            list.push({ el: el, title: title, key: id, index: index });
        });
        return list;
    }

    function showSections() {
        var box = document.getElementById('trexExportSections');
        if (!box) return;
        box.innerHTML = '';
        var sections = gatherSections();
        if (sections.length === 0) {
            box.innerHTML = '<div style="font-size:12px;color:#64748b;padding:8px 0;">Bu sayfada dışa aktarılacak bölüm bulunamadı.</div>';
            box.classList.add('show');
            return;
        }
        sections.forEach(function (item) {
            var row = document.createElement('label');
            row.className = 'trex-sec-item';
            var cb = document.createElement('input');
            cb.type = 'checkbox';
            cb.checked = true;
            cb.value = item.key;
            cb.dataset.sectionIndex = String(item.index);
            cb.dataset.section = item.el.getAttribute('data-export-section') || '';
            row.appendChild(cb);
            var span = document.createElement('span');
            span.textContent = item.title;
            row.appendChild(span);
            box.appendChild(row);
        });
        box.classList.add('show');
    }

    // A) Bir bölümdeki tüm grafikleri native export ile base64 PNG'ye çevir.
    function rasterizeSectionCharts(secEl) {
        var results = [];

        // 1) ECharts canvas'ları → getDataURL
        if (typeof echarts !== 'undefined') {
            secEl.querySelectorAll('canvas').forEach(function (c) {
                var container = c.closest('[_echarts_instance_]') || c.parentElement;
                if (!container) return;
                var chart = echarts.getInstanceByDom(container);
                if (chart) {
                    try {
                        var url = chart.getDataURL({
                            type: 'png',
                            pixelRatio: 2,
                            backgroundColor: '#ffffff',
                            excludeComponents: ['toolbox']
                        });
                        var img = new Image();
                        img.src = url;
                        img.dataset.trexRole = 'chart';
                        img.style.width = (c.clientWidth || 300) + 'px';
                        img.style.height = (c.clientHeight || 200) + 'px';
                        img.style.objectFit = 'contain';
                        results.push({ imgEl: img, role: 'chart', box: container });
                    } catch (e) { console.error('ECharts getDataURL hatası:', e); }
                }
            });
        }

        // 2) SVG elemanları → SVG data URI → Image → canvas → PNG
        secEl.querySelectorAll('svg').forEach(function (svg) {
            try {
                var s = new XMLSerializer().serializeToString(svg);
                var svgUrl = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(s);
                var img = new Image();
                img.src = svgUrl;
                img.dataset.trexRole = 'chart';
                var rect = svg.getBoundingClientRect();
                var w = Math.round(rect.width || svg.clientWidth || 200);
                var h = Math.round(rect.height || svg.clientHeight || 200);
                img.style.width = w + 'px';
                img.style.height = h + 'px';
                img.style.objectFit = 'contain';
                results.push({ imgEl: img, role: 'svg', box: svg, svgUrl: svgUrl, width: w, height: h });
            } catch (e) { console.error('SVG serialization hatası:', e); }
        });

        // 3) <img> (statik PNG'ler, örn. portfolio) → fetch + blob + base64
        secEl.querySelectorAll('img').forEach(function (el) {
            if (el.dataset.trexRole) return;
            var src = el.getAttribute('src') || el.src || '';
            if (!src) return;
            results.push({
                imgEl: el,
                role: 'img',
                box: el,
                width: el.clientWidth || el.naturalWidth || 300,
                height: el.clientHeight || el.naturalHeight || 200
            });
        });

        return results;
    }

    // B) Bir görselin (img) yüklendiğini bekle; SVG img'ler için ayrıca canvas'a çizip PNG al.
    function finalizeChartImage(item) {
        return new Promise(function (resolve) {
            var img = item.imgEl;
            var done = function () { resolve(img); };
            if (item.role === 'svg') {
                var svgImg = new Image();
                svgImg.onload = function () {
                    try {
                        var cv = document.createElement('canvas');
                        var w = item.width || svgImg.naturalWidth || 800;
                        var h = item.height || svgImg.naturalHeight || 600;
                        cv.width = w * 2;
                        cv.height = h * 2;
                        var ctx = cv.getContext('2d');
                        ctx.fillStyle = '#ffffff';
                        ctx.fillRect(0, 0, cv.width, cv.height);
                        ctx.drawImage(svgImg, 0, 0, cv.width, cv.height);
                        var out = new Image();
                        out.src = cv.toDataURL('image/png');
                        out.style.width = img.style.width;
                        out.style.height = img.style.height;
                        out.style.objectFit = 'contain';
                        out.dataset.trexRole = 'chart';
                        resolve(out);
                    } catch (err) {
                        console.error('SVG canvas convert error:', err);
                        resolve(img);
                    }
                };
                svgImg.onerror = function () { resolve(img); };
                svgImg.src = item.svgUrl;
                return;
            }
            if (item.role === 'img') {
                var src = img.getAttribute('src') || img.src;
                if (src.indexOf('data:') === 0) {
                    done();
                    return;
                }
                fetch(src)
                    .then(function (r) { return r.blob(); })
                    .then(function (blob) {
                        var fr = new FileReader();
                        fr.onloadend = function () {
                            img.src = fr.result;
                            img.style.width = item.width + 'px';
                            img.style.height = item.height + 'px';
                            img.style.objectFit = 'contain';
                            done();
                        };
                        fr.readAsDataURL(blob);
                    })
                    .catch(function (e) { console.error('IMG fetch hatası:', e); done(); });
                return;
            }
            if (img.complete && img.naturalWidth > 0) { done(); return; }
            img.onload = done;
            img.onerror = done;
        });
    }

    // C) Bir bölümü klonda topla; grafikleri (base64) img'lerle değiştirip
    //    bölüm bazında html2canvas ile tek PNG'ye rasterize et.
    function rasterizeSectionBlock(secEl, chartImages) {
        return new Promise(function (resolve) {
            var clone = secEl.cloneNode(true);
            clone.querySelectorAll('script,style,button,input,select').forEach(function (n) { n.remove(); });

            // Grafik kutularını base64 img'lerle değiştir
            chartImages.forEach(function (item) {
                var target = null;
                if (item.box && item.box.id) {
                    target = clone.querySelector('#' + item.box.id);
                }
                if (!target && item.box) {
                    var tag = item.box.tagName.toLowerCase();
                    var origEls = Array.prototype.slice.call(secEl.querySelectorAll(tag));
                    var cloneEls = Array.prototype.slice.call(clone.querySelectorAll(tag));
                    var idx = origEls.indexOf(item.box);
                    if (idx !== -1 && cloneEls[idx]) {
                        target = cloneEls[idx];
                    }
                }
                if (target && target.parentNode) {
                    var replacement = item.imgEl.cloneNode(true);
                    target.parentNode.replaceChild(replacement, target);
                }
            });

            // Geçici, görünür (offscreen değil) render konteyneri
            var wrapper = document.createElement('div');
            wrapper.style.position = 'fixed';
            wrapper.style.left = '0';
            wrapper.style.top = '0';
            wrapper.style.zIndex = '-1';
            wrapper.style.opacity = '0';
            wrapper.style.pointerEvents = 'none';
            wrapper.style.width = '794px';
            wrapper.style.background = '#ffffff';
            wrapper.appendChild(clone);
            document.body.appendChild(wrapper);

            try {
                if (typeof html2canvas === 'undefined') {
                    throw new Error('html2canvas bulunamadı');
                }
                html2canvas(wrapper, {
                    scale: 2,
                    useCORS: true,
                    backgroundColor: '#ffffff',
                    logging: false
                }).then(function (canvas) {
                    var dataUrl = canvas.toDataURL('image/jpeg', 0.92);
                    resolve({ dataUrl: dataUrl, width: canvas.width, height: canvas.height });
                    setTimeout(function () { if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper); }, 50);
                }).catch(function (e) {
                    console.error('Bölüm render hatası:', e);
                    resolve(null);
                    setTimeout(function () { if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper); }, 50);
                });
            } catch (e) {
                console.error('html2canvas çağrı hatası:', e);
                resolve(null);
                if (wrapper.parentNode) wrapper.parentNode.removeChild(wrapper);
            }
        });
    }

    // ---------- PDF üretimi (jsPDF + Native Grafik Export) ----------
    async function exportPdf(sections) {
        var status = document.getElementById('trexExportStatus');
        var goBtn = document.getElementById('trexExportGo');
        if (status) { status.className = 'trex-export-status'; status.style.display = 'block'; status.textContent = 'Grafikler işleniyor...'; }
        if (goBtn) goBtn.disabled = true;

        try {
            // jsPDF kurulumu
            var JsPDF = (window.jspdf && window.jspdf.jsPDF) ? window.jspdf.jsPDF : (typeof jsPDF !== 'undefined' ? jsPDF : null);
            if (!JsPDF) throw new Error('jsPDF yüklenemedi. Lütfen internet bağlantınızı kontrol edin.');
            var doc = new JsPDF({ orientation: 'portrait', unit: 'mm', format: 'a4' });

            var MARGIN = 10;
            var PAGE_W = 210;
            var PAGE_H = 297;
            var MAX_W = PAGE_W - MARGIN * 2;   // 190 mm
            var MAX_H = PAGE_H - MARGIN * 2;   // 277 mm
            var y = MARGIN;

            // Başlık bloğu (bölüm bazlı değil, rapor başlığı)
            doc.setFillColor(0, 40, 18);
            doc.rect(MARGIN, y, MAX_W, 18, 'F');
            doc.setTextColor(255, 255, 255);
            doc.setFont('helvetica', 'bold');
            doc.setFontSize(14);
            doc.text('trex DataLab Raporu', MARGIN + 6, y + 7);
            doc.setFontSize(9);
            doc.setTextColor(200, 220, 210);
            doc.text((document.title || 'Rapor') + ' - ' + currentPage() + ' - ' + new Date().toLocaleString('tr-TR'), MARGIN + 6, y + 14);
            y += 18 + 6;

            for (var i = 0; i < sections.length; i++) {
                var sec = sections[i];

                // Bölüm başlığı
                if (y + 10 > PAGE_H - MARGIN) { doc.addPage(); y = MARGIN; }
                doc.setTextColor(0, 107, 51);
                doc.setFont('helvetica', 'bold');
                doc.setFontSize(11);
                doc.text(sec.title.toUpperCase(), MARGIN, y);
                y += 6;

                // 1) Grafikleri native export ile topla (ECharts / SVG / img)
                var items = rasterizeSectionCharts(sec.el);
                var finalized = [];
                for (var k = 0; k < items.length; k++) {
                    var fimg = await finalizeChartImage(items[k]);
                    if (fimg) finalized.push(fimg);
                }

                // 2) Bölümü tek PNG olarak rasterize et (grafikler base64 img ile değiştirilmiş)
                var blockImg = await rasterizeSectionBlock(sec.el, items);

                if (blockImg) {
                    // oranları koruyarak sayfa genişliğine sığdır
                    var ratio = blockImg.height / blockImg.width;
                    var w = MAX_W;
                    var h = w * ratio;
                    if (h > MAX_H) { h = MAX_H; w = h / ratio; }
                    if (y + h > PAGE_H - MARGIN) { doc.addPage(); y = MARGIN; }
                    doc.addImage(blockImg.dataUrl, 'JPEG', MARGIN, y, w, h, undefined, 'FAST');
                    y += h + 8;
                } else if (finalized.length > 0) {
                    // Sadece grafikler (bölüm render'ı başarısız olduysa)
                    for (var g = 0; g < finalized.length; g++) {
                        var gi = finalized[g];
                        var imgRatio = (gi.naturalHeight || 200) / (gi.naturalWidth || 300);
                        var iw = MAX_W;
                        var ih = iw * imgRatio;
                        if (ih > MAX_H) { ih = MAX_H; iw = ih / imgRatio; }
                        if (y + ih > PAGE_H - MARGIN) { doc.addPage(); y = MARGIN; }
                        doc.addImage(gi.src, 'PNG', MARGIN, y, iw, ih, undefined, 'FAST');
                        y += ih + 6;
                    }
                } else {
                    // Ne bölüm ne grafik üretilemedi → boş bölüm notu
                    doc.setTextColor(150, 150, 150);
                    doc.setFont('helvetica', 'normal');
                    doc.setFontSize(9);
                    doc.text('(Bölüm içeriği oluşturulamadı)', MARGIN, y);
                    y += 8;
                }
            }

            var pageBase = currentPage().replace('.html', '');
            doc.save('trex_datalab_' + pageBase + '_raporu.pdf');

            if (status) { status.className = 'trex-export-status'; status.textContent = 'PDF oluşturuldu ve indirildi.'; }
            setTimeout(function () { closeModal(); }, 1200);
        } catch (e) {
            console.error('PDF hatası:', e);
            if (status) { status.className = 'trex-export-status err'; status.textContent = 'PDF oluşturulamadı: ' + e.message; }
        } finally {
            if (goBtn) goBtn.disabled = false;
            setTimeout(function () { if (status) status.style.display = 'none'; }, 4000);
        }
    }

    // ---------- CSV indirme ----------
    async function exportCsv() {
        var status = document.getElementById('trexExportStatus');
        var goBtn = document.getElementById('trexExportGo');
        if (status) {
            status.className = 'trex-export-status';
            status.style.display = 'block';
            status.textContent = 'CSV hazırlanıyor...';
        }
        if (goBtn) goBtn.disabled = true;

        try {
            var res = await fetch(API_BASE + '/api/export/csv');
            if (!res.ok) {
                var errDetail = 'CSV alınamadı.';
                try {
                    var err = await res.json();
                    if (err && err.detail) errDetail = err.detail;
                } catch (e) {}
                throw new Error(errDetail);
            }

            var filename = 'veri_aktarilan.csv';
            var disposition = res.headers.get('Content-Disposition');
            if (disposition && disposition.indexOf('filename=') !== -1) {
                var matches = /filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/.exec(disposition);
                if (matches != null && matches[1]) {
                    filename = matches[1].replace(/['"]/g, '');
                }
            }

            var blob = await res.blob();
            var a = document.createElement('a');
            a.href = URL.createObjectURL(blob);
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            setTimeout(function () {
                URL.revokeObjectURL(a.href);
                if (a.parentNode) a.remove();
            }, 500);

            if (status) {
                status.className = 'trex-export-status';
                status.textContent = 'CSV başarıyla indirildi.';
            }
            setTimeout(function () { closeModal(); }, 1200);
        } catch (e) {
            console.error('CSV hatası:', e);
            if (status) {
                status.className = 'trex-export-status err';
                status.textContent = 'CSV hatası: ' + e.message;
            }
        } finally {
            if (goBtn) goBtn.disabled = false;
            setTimeout(function () { if (status) status.style.display = 'none'; }, 4000);
        }
    }

    // ---------- Event'ler ----------
    document.addEventListener('click', function (e) {
        var go = e.target.closest('#trexExportGo');
        var opt = e.target.closest('.trex-export-opt');
        var close = e.target.closest('#trexExportClose, #trexExportCancel');
        var modal = document.getElementById('trexExportModal');

        if (close && modal) { closeModal(); return; }

        if (opt && modal) {
            modal.querySelectorAll('.trex-export-opt').forEach(function (o) { o.classList.remove('active'); });
            opt.classList.add('active');
            var isPdf = opt.getAttribute('data-opt') === 'pdf';
            var box = document.getElementById('trexExportSections');
            if (isPdf) {
                showSections();
            } else if (box) {
                box.classList.remove('show');
            }
            return;
        }

        if (go && modal) {
            var activeOpt = modal.querySelector('.trex-export-opt.active');
            var isCsv = activeOpt && activeOpt.getAttribute('data-opt') === 'csv';
            if (isCsv) {
                exportCsv();
            } else {
                var allSections = gatherSections();
                var checked = [];
                modal.querySelectorAll('#trexExportSections input[type="checkbox"]:checked').forEach(function (cb) {
                    var idx = parseInt(cb.dataset.sectionIndex, 10);
                    if (!isNaN(idx) && allSections[idx]) {
                        checked.push(allSections[idx]);
                    }
                });
                if (checked.length === 0) {
                    var status = document.getElementById('trexExportStatus');
                    if (status) {
                        status.className = 'trex-export-status err';
                        status.textContent = 'Lütfen en az bir bölüm seçin.';
                        status.style.display = 'block';
                    }
                    return;
                }
                exportPdf(checked);
            }
        }
    });

    // Backdrop tıklandığında kapatma
    document.addEventListener('click', function (e) {
        var modal = document.getElementById('trexExportModal');
        if (modal && modal.classList.contains('open') && e.target === modal) closeModal();
    });

    // ESC tuşuyla kapatma
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape') {
            var modal = document.getElementById('trexExportModal');
            if (modal && modal.classList.contains('open')) closeModal();
        }
    });

    // ---------- Global fonksiyonlar ----------
    window.openExportModal = function () { openModal(); };
    window.closeExportModal = function () { closeModal(); };
})();
