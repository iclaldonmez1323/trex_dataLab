(function () {
    if (document.getElementById('appSidebar')) return;

    function currentPage() {
        var p = (location.pathname.split('/').pop() || 'index.html').toLowerCase();
        if (!p || p === '/' || p === 'index') return 'index.html';
        if (!p.endsWith('.html')) return p + '.html';
        return p;
    }
    var page = currentPage();
    var isIndex = page === 'index.html';

    var NAV_ITEMS = [
        { href: 'index.html',        key: 'nav.dashboard',        icon: 'dashboard',       label: 'Dashboard' },
        { href: 'data-quality.html', key: 'nav.dataQuality',      icon: 'analytics',       label: 'Data Quality' },
        { href: 'preprocessing.html',key: 'nav.preprocessing',    icon: 'construction',    label: 'Preprocessing' },
        { href: 'visualization.html',key: 'nav.visualization',    icon: 'insights',        label: 'Visualization' },
        { href: 'machine-learning.html', key: 'nav.machineLearning', icon: 'model_training', label: 'Machine Learning' },
        { href: 'portfolio.html',    key: 'nav.portfolio',        icon: 'folder_shared',   label: 'Portfolio' }
    ];
    var FOOTER_ITEMS = [
        { href: 'settings.html', key: 'nav.settings', icon: 'settings', label: 'Settings' },
        { href: 'support.html',  key: 'nav.support',  icon: 'help',     label: 'Support' }
    ];

    function navLinkClass(active) {
        return 'flex items-center gap-3 px-4 py-2 rounded-lg transition-colors' +
            (active ? ' bg-primary text-on-primary opacity-90'
                    : ' text-white/70 hover:text-white hover:bg-white/10 transition-all');
    }

    var uploadHtml = isIndex
        ? '<button id="sidebarUploadBtn" type="button" class="w-full mb-8 bg-primary-fixed text-on-primary-fixed font-body-md text-body-md py-3 px-4 rounded-lg flex items-center justify-center gap-2 hover:bg-primary-fixed-dim transition-colors shadow-[0_4px_6px_-1px_rgba(0,0,0,0.05)] cursor-pointer">' +
          '  <span class="material-symbols-outlined">upload</span>' +
          '  <span data-i18n="nav.newUpload">Yeni Veri Yükle</span>' +
          '</button>'
        : '<a href="index.html" class="w-full mb-8 bg-primary-fixed text-on-primary-fixed font-body-md text-body-md py-3 px-4 rounded-lg flex items-center justify-center gap-2 hover:bg-primary-fixed-dim transition-colors shadow-[0_4px_6px_-1px_rgba(0,0,0,0.05)] cursor-pointer">' +
          '  <span class="material-symbols-outlined">upload</span>' +
          '  <span data-i18n="nav.newUpload">Yeni Veri Yükle</span>' +
          '</a>';

    var html =
        '<nav id="appSidebar" class="fixed left-0 top-0 h-full w-sidebar-width bg-[#002812] border-r border-outline-variant flex flex-col py-6 px-4 z-20">' +
        '  <div class="mb-10 px-2">' +
        '    <h1 class="font-headline-md text-headline-md text-white m-0 leading-tight">trex DataLab</h1>' +
        '    <p class="font-label-mono text-label-mono text-white/70 uppercase" data-i18n="brand.tagline">PRECISION DATA PLATFORM</p>' +
        '  </div>' +
        uploadHtml +
        '  <ul class="flex flex-col gap-2 flex-grow">' + NAV_ITEMS.map(function (it) {
            var active = page === it.href;
            var icon = '<span class="material-symbols-outlined' + (active ? '" style="font-variation-settings:\'FILL\' 1"' : '"') + '>' + it.icon + '</span>';
            return '<li><a class="' + navLinkClass(active) + '" href="' + it.href + '">' + icon +
                '<span class="font-body-md text-body-md' + (active ? ' font-medium' : '') + '" data-i18n="' + it.key + '">' + it.label + '</span></a></li>';
        }).join('') + '</ul>' +
        '  <div class="mt-auto pt-6 border-t border-white/10">' +
        '    <ul class="flex flex-col gap-2">' + FOOTER_ITEMS.map(function (it) {
            return '<li><a class="' + navLinkClass(false) + '" href="' + it.href + '">' +
                '<span class="material-symbols-outlined">' + it.icon + '</span>' +
                '<span class="font-body-md text-body-md" data-i18n="' + it.key + '">' + it.label + '</span></a></li>';
        }).join('') + '</ul>' +
        '  </div>' +
        '</nav>';

    // SENKRON enjeksiyon (DOMContentLoaded beklemeden)
    document.body.insertAdjacentHTML('afterbegin', html);
})();
