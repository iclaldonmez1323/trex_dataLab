/**
 * trex DataLab - Uygulama Geneli Çeviri ve Dil Motoru (i18n)
 * Türkçe (varsayılan) ve İngilizce dil desteği.
 */

(function () {
    'use strict';

    const I18N_DICT = {
        tr: {
            // Brand & Navigation
            'brand.name': 'trex DataLab',
            'brand.tagline': 'PRECISION DATA PLATFORM',
            'nav.newUpload': 'Yeni Veri Yükle',
            'nav.dashboard': 'Analiz Paneli',
            'nav.dataQuality': 'Veri Kalitesi',
            'nav.preprocessing': 'Veri Hazırlama',
            'nav.visualization': 'Görselleştirme',
            'nav.machineLearning': 'Makine Öğrenmesi',
            'nav.portfolio': 'Portföy',
            'nav.settings': 'Settings',
            'nav.support': 'Support',
            'nav.fastActions': 'Hızlı İşlemler',
            'nav.reports': 'Raporlar',
            'nav.export': 'Dışa Aktar',
            'nav.profile': 'Kullanıcı Profili',
            'nav.notifications': 'Bildirimler',

            // Common
            'common.back': 'Geri',
            'common.save': 'Kaydet',
            'common.cancel': 'İptal',
            'common.close': 'Kapat',
            'common.download': 'İndir',
            'common.delete': 'Sil',
            'common.loading': 'Yükleniyor...',
            'common.success': 'Başarılı',
            'common.error': 'Hata',
            'common.warning': 'Uyarı',
            'common.info': 'Bilgi',
            'common.apply': 'Uygula',
            'common.reset': 'Sıfırla',
            'common.undo': 'Geri Al',
            'common.all': 'Tümü',
            'common.actions': 'İşlemler',
            'common.status': 'Durum',
            'common.yes': 'Evet',
            'common.no': 'Hayır',
            'common.search': 'Arama...',
            'common.demoNotice': 'Bu özellik demo modundadır.',

            // Index / Dashboard
            'index.title': 'Veri Yükleme ve Analiz',
            'index.subtitle': 'CSV dosyanızı yükleyin ve anında temel kalite metriklerini inceleyin.',
            'index.dropzoneTitle': 'CSV Dosyanızı Buraya Sürükleyin veya Seçin',
            'index.dropzoneSub': 'Maksimum dosya boyutu: 50MB. Desteklenen format: .csv',
            'index.browseBtn': 'Dosya Seç',
            'index.activeDataset': 'Aktif Veri Seti',
            'index.deleteDataset': 'Veri Setini Sıfırla',
            'index.statRows': 'Toplam Satır',
            'index.statCols': 'Toplam Sütun',
            'index.statMissing': 'Eksik Değer',
            'index.statDuplicates': 'Tekrar Eden Satır',
            'index.statNumeric': 'Sayısal Sütun',
            'index.statCategorical': 'Kategorik Sütun',
            'index.tipRows': 'Toplam satır sayısı',
            'index.tipCols': 'Toplam sütun sayısı',
            'index.tipMissing': 'Toplam eksik / boş hücre sayısı',
            'index.tipDuplicates': 'Birebir yinelenen satır sayısı',
            'index.tipNumeric': 'Sayısal veri tipindeki sütun sayısı',
            'index.tipCategorical': 'Kategorik / metin tipindeki sütun sayısı',
            'index.previewTitle': 'Veri Önizleme',
            'index.previewSub': 'Yüklenen veri setinin ilk satırları',
            'index.analyzeCta': 'Detaylı Veri Kalitesini Analiz Et',
            'index.noDataTitle': 'Henüz Veri Yüklenmedi',
            'index.noDataSub': 'Analize başlamak için yukarıdaki alandan bir CSV dosyası yükleyin.',
            'index.loadingTitle': 'Dosya İşleniyor...',
            'index.loadingSub': 'Veri seti okunuyor ve özet çıkartılıyor',
            'index.loadedStatus': 'YÜKLENDİ',
            'index.waitingStatus': 'BEKLENİYOR',
            'index.first10': 'İLK 10 SATIR',
            'index.noPreviewMsg': 'Önizleme tablosunu görüntülemek için lütfen bir CSV veri seti yükleyin.',
            'index.noMatches': 'Eşleşen kayıt bulunamadı.',
            'index.matches': '{count} EŞLEŞME',
            'index.emptyCell': 'Boş',
            'index.confirmOverwrite': 'Mevcut veri seti ve tüm ön işleme adımları değiştirilecek. Devam etmek istiyor musunuz?',
            'index.confirmDelete': 'Yüklenen veri seti ve tüm işlemler silinecek. Emin misiniz?',
            'index.dataDeleted': 'Veri seti sıfırlandı.',
            'index.dataLoaded': 'Veri seti başarıyla yüklendi.',
            'index.viewInPrep': 'Veri Hazırlama\'da Tam Tabloyu Gör',
            'index.multipleFiles': 'Birden fazla dosya bırakıldı; yalnızca "{name}" işlendi.',
            'index.uploadProgressNote': 'Dosya boyutu büyük; işlem biraz sürebilir.',
            'index.oldDataKept': 'Mevcut veri korundu; yeni dosya işlenemedi.',
            'index.searchLoading': 'Aranıyor...',
            'index.clearSearch': 'Aramayı temizle',

            // Data Quality
            'dq.pageTitle': 'Veri Kalitesi Raporu',
            'dq.pageSubtitle': 'Yüklenen veri setinin eksik veri, tutarlılık ve anomali analiz özeti.',
            'dq.loadingTitle': 'Veri Kalitesi Analiz Ediliyor',
            'dq.loadingSub': 'Lütfen bekleyin, metrikler hesaplanıyor...',
            'dq.overallScore': 'Genel Kalite Skoru',
            'dq.statusExcellent': 'Mükemmel',
            'dq.statusGood': 'İyi',
            'dq.statusWarning': 'İyileştirme Gerekli',
            'dq.statusCritical': 'Kritik Düzeyde Sorunlu',
            'dq.completeness': 'Veri Tamlığı',
            'dq.uniqueness': 'Tekillik (Uniqueness)',
            'dq.typeConsistency': 'Tip Uyumu',
            'dq.outliers': 'Aykırı Değerler',
            'dq.missingSummary': 'Eksik Değer Özeti',
            'dq.columnBreakdown': 'Kolon Bazlı Dağılım',
            'dq.scoreBreakdown': 'Skor Dağılımı ve Ağırlıklar',
            'dq.recommendations': 'Önerilen Eylemler',
            'dq.proceedPrep': 'Veri Hazırlama Adımına Geç',

            // Preprocessing
            'prep.pageTitle': 'Veri Hazırlama & Ön İşleme',
            'prep.pageSubtitle': 'Eksik değerleri doldurun, tipleri dönüştürün ve verinizi temizleyin.',
            'prep.loadingTitle': 'Veri Hazırlama Modülü Yükleniyor',
            'prep.loadingSub': 'Veri seti bilgileri alınıyor...',
            'prep.missingSection': 'Eksik Değer Yönetimi',
            'prep.dropMissing': 'Eksik Değer İçeren Satırları Sil',
            'prep.fillMean': 'Ortalama ile Doldur',
            'prep.fillMedian': 'Medyan ile Doldur',
            'prep.fillMode': 'En Çok Tekrar Eden ile Doldur',
            'prep.fillConstant': 'Sabit Değer ile Doldur',
            'prep.duplicateSection': 'Tekrar Eden Kayıtlar',
            'prep.dropDuplicates': 'Tekrar Eden Satırları Kaldır',
            'prep.typeSection': 'Tip Dönüşümleri',
            'prep.outlierSection': 'Aykırı Değer Yönetimi',
            'prep.undoBtn': 'Son İşlemi Geri Al',
            'prep.resetBtn': 'Tümünü Sıfırla',
            'prep.downloadCleaned': 'Temizlenmiş CSV\'yi İndir',
            'prep.proceedViz': 'Görselleştirmeye Geç',

            // Visualization
            'viz.pageTitle': 'Veri Görselleştirme & Analiz',
            'viz.pageSubtitle': 'Otomatik önerilen grafiklerle verinizi çok boyutlu keşfedin.',
            'viz.loadingTitle': 'Görselleştirme Modülü Hazırlanıyor',
            'viz.univariate': 'Tek Değişkenli Analiz',
            'viz.bivariate': 'İki Değişkenli Analiz',
            'viz.correlation': 'Korelasyon Matrisi',
            'viz.selectColX': 'X Ekseni Sütunu Seçin',
            'viz.selectColY': 'Y Ekseni Sütunu Seçin',
            'viz.chartType': 'Grafik Tipi',
            'viz.exportCharts': 'Tüm Grafikleri Dışa Aktar',

            // Portfolio
            'port.pageTitle': 'trex OEE Staj Portföy Raporu',
            'port.pageSubtitle': 'Endüstriyel Veri Analizi ve Makine Öğrenimi Raporu',
            'port.overview': 'Proje Genel Bakış',
            'port.methodology': 'Metodoloji & Süreç',
            'port.keyFindings': 'Öne Çıkan Bulgular',
            'port.deliverables': 'Çıktılar & Görseller',

            // Settings
            'settings.pageTitle': 'Uygulama Ayarları',
            'settings.pageSubtitle': 'Görünüm, analiz parametreleri, dışa aktarma ve bildirim tercihlerinizi yönetin.',
            'settings.appearanceTitle': 'Genel Görünüm & Arayüz',
            'settings.appearanceSub': 'Tema, sistem dili ve görsel önizleme ayarları.',
            'settings.theme': 'Tema Seçimi',
            'settings.themeLight': 'Açık Mod',
            'settings.themeLightDesc': 'Klasik aydınlık arayüz',
            'settings.themeDark': 'Koyu Mod',
            'settings.themeDarkDesc': 'Göz yormayan koyu yeşil ve antrasit tonlar',
            'settings.themeSystem': 'Sistem Varsayılanı',
            'settings.themeSystemDesc': 'İşletim sistemi temasını takip eder',
            'settings.language': 'Arayüz Dili',
            'settings.langTr': 'Türkçe (TR)',
            'settings.langEn': 'English (EN)',
            'settings.palette': 'Vurgu Renk Paleti',
            'settings.paletteDefault': 'Standart Zümrüt',
            'settings.paletteOcean': 'Okyanus Mavisi',
            'settings.paletteForest': 'Derin Orman',
            'settings.tableRows': 'Tablo Önizleme Satır Sayısı',
            'settings.dataTitle': 'Veri & Analiz Varsayılanları',
            'settings.dataSub': 'CSV ayracı, kalite eşikleri ve önbellek yönetimi.',
            'settings.csvDelimiter': 'Varsayılan CSV Ayracı',
            'settings.delimiterComma': 'Virgül (,)',
            'settings.delimiterSemicolon': 'Noktalı Virgül (;)',
            'settings.delimiterTab': 'Sekme (\\t)',
            'settings.missingThreshold': 'Kritik Eksik Veri Eşik Değeri (%)',
            'settings.missingThresholdHelp': 'Bu oranın üzerindeki eksik veriler kritik uyarı olarak işaretlenir.',
            'settings.retentionDays': 'İşlem Geçmişi Saklama Süresi (Gün)',
            'settings.clearCache': 'Önbelleği ve Geçici Verileri Temizle',
            'settings.clearCacheDesc': 'Tüm yerel oturum verilerini, yüklenmiş veri setlerini ve ayarları temizler.',
            'settings.clearCacheBtn': 'Önbelleği Temizle',
            'settings.exportTitle': 'Dışa Aktarma & Rapor Tercihleri',
            'settings.exportSub': 'PDF ve tablo dışa aktarma bölümleri, başlık ve kurumsal logo.',
            'settings.exportSections': 'Varsayılan Rapora Dahil Edilecek Bölümler',
            'settings.secSummary': 'Özet Kartlar',
            'settings.secMissing': 'Eksik Değer Analizi',
            'settings.secDuplicates': 'Tekrar Eden Kayıtlar',
            'settings.secDtypes': 'Veri Tipi Kontrolü',
            'settings.secOutliers': 'Aykırı Değerler',
            'settings.secScore': 'Kalite Skoru & Dağılımı',
            'settings.exportReportTitle': 'Varsayılan Rapor Başlığı',
            'settings.exportLogo': 'Rapor Kurumsal Logosu',
            'settings.exportLogoUpload': 'Logo Yükle (PNG/JPG)',
            'settings.exportLogoRemove': 'Logoyu Kaldır',
            'settings.exportFormat': 'Varsayılan Dışa Aktarma Formatı',
            'settings.notifyTitle': 'Bildirim Tercihleri',
            'settings.notifySub': 'Bildirim merkezinin ve sistem uyarılarının çalışma kuralları.',
            'settings.notifyAnalysis': 'Analiz tamamlandığında bildirim gönder',
            'settings.notifyExport': 'PDF veya rapor dışa aktarma hazır olduğunda bildir',
            'settings.notifyErrors': 'Sistem ve kritik veri uyumsuzluklarında uyar',
            'settings.notifySound': 'Bildirim seslerini etkinleştir',
            'settings.accountTitle': 'Hesap & Güvenlik (Demo)',
            'settings.accountSub': 'Kullanıcı profili ve güvenlik yönetimi görsel demosu.',
            'settings.name': 'Ad',
            'settings.surname': 'Soyad',
            'settings.email': 'E-posta',
            'settings.avatar': 'Profil Fotoğrafı',
            'settings.avatarUpload': 'Fotoğraf Yükle',
            'settings.changePassword': 'Şifre Değiştir',
            'settings.currentPassword': 'Mevcut Şifre',
            'settings.newPassword': 'Yeni Şifre',
            'settings.confirmPassword': 'Yeni Şifre (Tekrar)',
            'settings.updatePasswordBtn': 'Şifreyi Güncelle',
            'settings.dangerZone': 'Hesap Durumu & Tehlikeli Alan',
            'settings.logoutBtn': 'Oturumu Kapat',
            'settings.deleteAccountBtn': 'Hesabı Sil',
            'settings.resetDefaultsBtn': 'Varsayılanlara Sıfırla',
            'settings.autoSaved': 'Tüm değişiklikler anında kaydedilir',
            'settings.savedToast': 'Ayarlar başarıyla kaydedildi ✓',
            'settings.resetConfirm': 'Tüm ayarları varsayılan değerlerine döndürmek istediğinize emin misiniz?',
            'settings.clearCacheConfirm': 'Tüm önbellek ve oturum verileri silinecek. Onaylıyor musunuz?',
            'settings.demoAlert': 'Demo Modu: Bu uygulamada gerçek hesap/sunucu sistemi bulunmamaktadır.',

            // Profile & Account Menu
            'profile.edit': 'Profilimi Düzenle',
            'profile.accountSecurity': 'Hesap Ayarları & Güvenlik',
            'profile.usage': 'Kullanım & Limit Bilgisi',
            'profile.usage.dailyQuota': 'Günlük Analiz Kotası',
            'profile.usage.uploadLimit': 'Yüklenen Veri Limiti',
            'profile.appearance': 'Görünüm Modu',
            'profile.theme': 'Tema',
            'profile.themeDark': 'Koyu Mod',
            'profile.themeLight': 'Açık Mod',
            'profile.language': 'Dil Seçimi',
            'profile.help': 'Yardım & Dokümantasyon',
            'profile.feedback': 'Geri Bildirim Gönder',
            'profile.version': 'Sürüm v1.0.0',
            'profile.logout': 'Çıkış Yap',
            'profile.confirmLogout': 'Oturumu kapatmak istediğinize emin misiniz?',
            'profile.demoLogout': 'Demo modu: Bu uygulamada gerçek oturum sistemi bulunmuyor.',
            'profile.role.analyst': 'Veri Analisti',
            'profile.role.admin': 'Yönetici',
            'profile.role.user': 'Kullanıcı',
            'profile.quotaUsed': '8 / 10 İşlem',
            'profile.limitUsed': '42 MB / 50 MB',
            'profile.defaultName': 'Demo Kullanıcı',
            'profile.defaultEmail': 'demo@trexdatalab.com',
            'profile.feedbackToast': 'Geri bildiriminiz başarıyla iletildi!',
            'profile.helpModalTitle': 'trex DataLab Yardım ve Kılavuz',
            'profile.helpModalDesc': 'Veri kalitesi skoru; kayıp veri, yinelenen kayıt, aykırı değer ve tip uyumsuzluklarının ağırlıklı hesaplanmasıyla oluşturulur.',

            // Support & Help Desk
            'support.title': 'Destek & Yardım Merkezi',
            'support.subtitle': 'Kullanım kılavuzları, kalite metrikleri, sıkça sorulan sorular ve teknik destek.',
            'support.helpDocs': 'Hızlı Yardım & Dokümantasyon',
            'support.helpDocsSub': 'Platformu verimli kullanmanız için hazırlanmış adım adım rehberler.',
            'support.guides': 'Kullanım Rehberleri',
            'support.guide.csv': 'CSV Yükleme Rehberi',
            'support.guide.csvDesc': 'Veri setinizi hazırlama, format uyumluluğu ve 50MB sınırına dair ipuçları.',
            'support.guide.preprocess': 'Veri Temizleme & Ön İşleme Rehberi',
            'support.guide.preprocessDesc': 'Eksik değerleri doldurma, aykırı değerleri filtreleme ve tip dönüşümleri.',
            'support.guide.export': 'Dışa Aktarma & Raporlama Rehberi',
            'support.guide.exportDesc': 'PDF kalite raporları, temizlenmiş CSV ve Excel formatında indirme.',
            'support.guide.visualization': 'Görselleştirme & Grafik Rehberi',
            'support.guide.visualizationDesc': 'Otomatik grafik önerileri, dağılım, saçılım ve korelasyon çizimleri.',
            'support.metrics': 'Metrikler & Skor Hesaplama',
            'support.metricsSub': 'Veri Kalite Skoru (0-100) arkasındaki ağırlıklı ceza formülü.',
            'support.metrics.qualityScore': 'Kalite Skoru Ceza Formülü',
            'support.faq': 'Sıkça Sorulan Sorular (SSS)',
            'support.faqSub': 'En çok merak edilen sorular ve hızlı yanıtları.',
            'support.faq.q1': 'Desteklenen dosya formatları ve boyut limitleri nelerdir?',
            'support.faq.a1': 'trex DataLab şu anda yalnızca .csv (Virgül, Noktalı Virgül ve Sekme ayrılmış) formatındaki tabloları destekler. Maksimum dosya boyutu 50 MB’tır.',
            'support.faq.q2': 'PDF raporu neden inmiyor veya hatalı görünüyor?',
            'support.faq.a2': 'PDF oluşturma motoru (html2pdf) tarayıcı tabanlı çalışır. Sayfayı yerel web sunucusu üzerinden (http://localhost:8000) açtığınızdan emin olun ve gerekirse sayfayı sert yenileyin (Ctrl+F5).',
            'support.faq.q3': 'Verilerim sistemde saklanıyor mu, gizliliğim güvende mi?',
            'support.faq.a3': 'Hayır. Yüklenen veriler yalnızca sunucu hafızasında (in-memory) aktif oturum süresince tutulur. Sunucu kapandığında veya sıfırlandığında tüm veri tamamen silinir. Tercihler ise yalnızca yerel tarayıcınızda (localStorage) saklanır.',
            'support.faq.q4': 'Hangi analizler ve veri işlemleri yapılabilir?',
            'support.faq.a4': 'Veri kalitesi tespiti (eksiklik, aykırılık, tekillik), eksik veri tamamlama (ortalama, medyan, mod, sabit değer), tip dönüşümleri, Z-Score/IQR aykırı değer temizleme ve 7 farklı interaktif grafik görselleştirmesi yapılabilir.',
            'support.faq.q5': 'Dil ve tema nasıl değiştirilir?',
            'support.faq.a5': 'Ayarlar sayfasından veya üst sağ köşedeki Profil Menüsü içerisinden tek tıklamayla Koyu/Açık Tema ve Türkçe/İngilizce dil seçimi yapabilirsiniz.',
            'support.contact': 'İletişim & Destek Talebi',
            'support.contactSub': 'Sorununuzu bize bildirin veya geçmiş taleplerinizi takip edin.',
            'support.ticket.create': 'Yeni Destek Talebi Oluştur',
            'support.ticket.title': 'Talep Başlığı',
            'support.ticket.titlePlaceholder': 'Örn: PDF dışa aktarma hatası alıyorum',
            'support.ticket.category': 'Kategori',
            'support.ticket.catBug': 'Hata Bildirimi',
            'support.ticket.catUpload': 'Veri Yükleme Sorunu',
            'support.ticket.catReport': 'Raporlama Hatası',
            'support.ticket.catViz': 'Görselleştirme Sorunu',
            'support.ticket.catOther': 'Diğer / Genel Soru',
            'support.ticket.priority': 'Önem Derecesi',
            'support.ticket.priLow': 'Düşük',
            'support.ticket.priMed': 'Orta',
            'support.ticket.priHigh': 'Yüksek',
            'support.ticket.priCrit': 'Kritik',
            'support.ticket.description': 'Açıklama',
            'support.ticket.descPlaceholder': 'Karşılaştığınız sorunu veya adımları detaylıca açıklayın...',
            'support.ticket.attach': 'Ekran Görüntüsü Ekle (İsteğe Bağlı)',
            'support.ticket.attachBtn': 'Görsel Seç',
            'support.ticket.removeAttach': 'Görseli Kaldır',
            'support.ticket.submit': 'Destek Talebini Gönder',
            'support.ticket.myTickets': 'Destek Taleplerim',
            'support.ticket.empty': 'Henüz oluşturulmuş bir destek talebi bulunmuyor.',
            'support.ticket.status.inceleniyor': 'İnceleniyor',
            'support.ticket.status.cozuldu': 'Çözüldü',
            'support.ticket.status.yanitBekleniyor': 'Yanıt Bekleniyor',
            'support.email': 'Doğrudan E-posta Desteği',
            'support.emailSub': 'Daha kapsamlı teknik sorularınız için ekibimize e-posta gönderin.',
            'support.emailBtn': 'E-posta Gönder',
            'support.feedback': 'Geri Bildirim & İyileştirme',
            'support.feedbackSub': 'Görüşleriniz trex DataLab platformunu geliştirmemize yardımcı olur.',
            'support.feedback.feature': 'Özellik / İyileştirme Önerisi',
            'support.feedback.featurePlaceholder': 'Görmek istediğiniz yeni bir özellik veya analiz türü...',
            'support.feedback.sendFeature': 'Öneri Gönder',
            'support.feedback.bug': 'Hızlı Hata Bildir',
            'support.status': 'Sistem & Altyapı Durumu',
            'support.statusSub': 'trex DataLab mikro servislerinin anlık çalışma durumu.',
            'support.status.allOperational': 'Tüm servisler sorunsuz çalışıyor',
            'support.status.lastCheck': 'Son kontrol: az önce',
            'support.status.service1': 'Analiz & Kalite Motoru',
            'support.status.service2': 'Görselleştirme & Grafik Servisi',
            'support.status.service3': 'PDF & Raporlama Modülü',
            'support.status.service4': 'FastAPI Web & API Sunucusu',
            'support.demoTicketCreated': 'Destek talebiniz başarıyla oluşturuldu ✓',
            'support.demoFeedbackSent': 'Geri bildiriminiz başarıyla iletildi ✓',

            // Machine Learning
            'ml.pageTitle': 'Makine Öğrenmesi Model Eğitimi',
            'ml.smallSampleNote': 'Veri seti 50 satırdan az; çapraz doğrulama uygulanmadı.',
            'ml.cvFixedHint': 'Küçük veri seti: K=3 sabitlendi',
            'ml.hyperParamsTitle': 'Model Hiperparametreleri',
            'ml.hyperParams.noModel': 'Seçili modeller için ayarlanabilir hiperparametre bulunmuyor.',
            'ml.hyperParams.nEstimators': 'Ağaç Sayısı (n_estimators)',
            'ml.hyperParams.maxDepth': 'Maksimum Derinlik (max_depth)',
            'ml.hyperParams.c': 'Regülarizasyon Gücü (C)',
            'ml.hyperParams.autoDepth': 'Otomatik (Sınırsız)',
            'ml.textColumnsNote': '{count} metin sütunu tespit edildi ve otomatik dışlandı: {cols}',
            'ml.profileRows': 'satır',
            'ml.profileNumeric': 'Sayısal',
            'ml.profileCategorical': 'Kategorik',
            'ml.profileDatetime': 'Tarih',
            'ml.profileText': 'Metin',
            'ml.profileMissing': 'Eksik',
            'ml.profileTiny': 'Çok Küçük Örneklem (<50)',
            'ml.profileSmall': 'Küçük Örneklem (50-150)',
            'ml.profileNormal': 'Normal Örneklem',
            'ml.profileLarge': 'Geniş Veri Seti (>2000)'
        },
        en: {
            // Brand & Navigation
            'brand.name': 'trex DataLab',
            'brand.tagline': 'PRECISION DATA PLATFORM',
            'nav.newUpload': 'Upload New Data',
            'nav.dashboard': 'Dashboard',
            'nav.dataQuality': 'Data Quality',
            'nav.preprocessing': 'Preprocessing',
            'nav.visualization': 'Visualization',
            'nav.machineLearning': 'Machine Learning',
            'nav.portfolio': 'Portfolio',
            'nav.settings': 'Settings',
            'nav.support': 'Support',
            'nav.fastActions': 'Quick Actions',
            'nav.reports': 'Reports',
            'nav.export': 'Export',
            'nav.profile': 'User Profile',
            'nav.notifications': 'Notifications',

            // Common
            'common.back': 'Back',
            'common.save': 'Save',
            'common.cancel': 'Cancel',
            'common.close': 'Close',
            'common.download': 'Download',
            'common.delete': 'Delete',
            'common.loading': 'Loading...',
            'common.success': 'Success',
            'common.error': 'Error',
            'common.warning': 'Warning',
            'common.info': 'Info',
            'common.apply': 'Apply',
            'common.reset': 'Reset',
            'common.undo': 'Undo',
            'common.all': 'All',
            'common.actions': 'Actions',
            'common.status': 'Status',
            'common.yes': 'Yes',
            'common.no': 'No',
            'common.search': 'Search...',
            'common.demoNotice': 'This feature is running in demo mode.',

            // Index / Dashboard
            'index.title': 'Data Upload & Overview',
            'index.subtitle': 'Upload your CSV file and immediately inspect key quality metrics.',
            'index.dropzoneTitle': 'Drag & Drop your CSV file here or Browse',
            'index.dropzoneSub': 'Maximum file size: 50MB. Supported format: .csv',
            'index.browseBtn': 'Browse Files',
            'index.activeDataset': 'Active Dataset',
            'index.deleteDataset': 'Reset Dataset',
            'index.statRows': 'Total Rows',
            'index.statCols': 'Total Columns',
            'index.statMissing': 'Missing Values',
            'index.statDuplicates': 'Duplicate Rows',
            'index.statNumeric': 'Numeric Columns',
            'index.statCategorical': 'Categorical Columns',
            'index.tipRows': 'Total row count',
            'index.tipCols': 'Total column count',
            'index.tipMissing': 'Total missing / empty cells',
            'index.tipDuplicates': 'Duplicate row count',
            'index.tipNumeric': 'Numeric column count',
            'index.tipCategorical': 'Categorical / text column count',
            'index.previewTitle': 'Data Preview',
            'index.previewSub': 'First rows of the uploaded dataset',
            'index.analyzeCta': 'Analyze Detailed Data Quality',
            'index.noDataTitle': 'No Data Uploaded Yet',
            'index.noDataSub': 'Upload a CSV file above to begin your analysis.',
            'index.loadingTitle': 'Processing File...',
            'index.loadingSub': 'Reading dataset and generating summary',
            'index.loadedStatus': 'LOADED',
            'index.waitingStatus': 'WAITING',
            'index.first10': 'FIRST 10 ROWS',
            'index.noPreviewMsg': 'Please upload a CSV dataset to view the preview table.',
            'index.noMatches': 'No matching records found.',
            'index.matches': '{count} MATCHES',
            'index.emptyCell': 'Empty',
            'index.confirmOverwrite': 'Current dataset and all preprocessing steps will be overwritten. Do you want to proceed?',
            'index.confirmDelete': 'The loaded dataset and all steps will be deleted. Are you sure?',
            'index.dataDeleted': 'Dataset has been reset.',
            'index.dataLoaded': 'Dataset loaded successfully.',
            'index.viewInPrep': 'View Full Table in Preprocessing',
            'index.multipleFiles': 'Multiple files dropped; only "{name}" was processed.',
            'index.uploadProgressNote': 'Large file size; processing may take a while.',
            'index.oldDataKept': 'Previous dataset preserved; new file could not be processed.',
            'index.searchLoading': 'Searching...',
            'index.clearSearch': 'Clear search',

            // Data Quality
            'dq.pageTitle': 'Data Quality Report',
            'dq.pageSubtitle': 'Summary of missing values, consistency, and anomaly analysis for the dataset.',
            'dq.loadingTitle': 'Analyzing Data Quality',
            'dq.loadingSub': 'Please wait, calculating metrics...',
            'dq.overallScore': 'Overall Quality Score',
            'dq.statusExcellent': 'Excellent',
            'dq.statusGood': 'Good',
            'dq.statusWarning': 'Needs Improvement',
            'dq.statusCritical': 'Critically Flawed',
            'dq.completeness': 'Completeness',
            'dq.uniqueness': 'Uniqueness',
            'dq.typeConsistency': 'Type Consistency',
            'dq.outliers': 'Outliers',
            'dq.missingSummary': 'Missing Value Summary',
            'dq.columnBreakdown': 'Column Breakdown',
            'dq.scoreBreakdown': 'Score Breakdown & Weights',
            'dq.recommendations': 'Recommended Actions',
            'dq.proceedPrep': 'Proceed to Preprocessing',

            // Preprocessing
            'prep.pageTitle': 'Data Cleaning & Preprocessing',
            'prep.pageSubtitle': 'Handle missing values, convert data types, and clean your dataset.',
            'prep.loadingTitle': 'Loading Preprocessing Module',
            'prep.loadingSub': 'Fetching dataset information...',
            'prep.missingSection': 'Missing Value Management',
            'prep.dropMissing': 'Drop Rows with Missing Values',
            'prep.fillMean': 'Fill with Mean',
            'prep.fillMedian': 'Fill with Median',
            'prep.fillMode': 'Fill with Mode',
            'prep.fillConstant': 'Fill with Constant Value',
            'prep.duplicateSection': 'Duplicate Records',
            'prep.dropDuplicates': 'Remove Duplicate Rows',
            'prep.typeSection': 'Type Conversions',
            'prep.outlierSection': 'Outlier Management',
            'prep.undoBtn': 'Undo Last Action',
            'prep.resetBtn': 'Reset All Steps',
            'prep.downloadCleaned': 'Download Cleaned CSV',
            'prep.proceedViz': 'Proceed to Visualization',

            // Visualization
            'viz.pageTitle': 'Data Visualization & Analysis',
            'viz.pageSubtitle': 'Explore your dataset multi-dimensionally with auto-recommended charts.',
            'viz.loadingTitle': 'Preparing Visualization Module',
            'viz.univariate': 'Univariate Analysis',
            'viz.bivariate': 'Bivariate Analysis',
            'viz.correlation': 'Correlation Matrix',
            'viz.selectColX': 'Select X-Axis Column',
            'viz.selectColY': 'Select Y-Axis Column',
            'viz.chartType': 'Chart Type',
            'viz.exportCharts': 'Export All Charts',

            // Portfolio
            'port.pageTitle': 'trex OEE Internship Portfolio Report',
            'port.pageSubtitle': 'Industrial Data Analysis & Machine Learning Report',
            'port.overview': 'Project Overview',
            'port.methodology': 'Methodology & Process',
            'port.keyFindings': 'Key Findings',
            'port.deliverables': 'Deliverables & Visuals',

            // Settings
            'settings.pageTitle': 'Application Settings',
            'settings.pageSubtitle': 'Manage appearance, analysis parameters, export, and notification preferences.',
            'settings.appearanceTitle': 'Appearance & Interface',
            'settings.appearanceSub': 'Theme, system language, and visual preview settings.',
            'settings.theme': 'Theme Mode',
            'settings.themeLight': 'Light Mode',
            'settings.themeLightDesc': 'Classic bright interface',
            'settings.themeDark': 'Dark Mode',
            'settings.themeDarkDesc': 'Comfortable dark pine and slate tones',
            'settings.themeSystem': 'System Default',
            'settings.themeSystemDesc': 'Follows your operating system theme',
            'settings.language': 'Interface Language',
            'settings.langTr': 'Turkish (TR)',
            'settings.langEn': 'English (EN)',
            'settings.palette': 'Accent Color Palette',
            'settings.paletteDefault': 'Default Emerald',
            'settings.paletteOcean': 'Ocean Blue',
            'settings.paletteForest': 'Deep Forest',
            'settings.tableRows': 'Table Preview Row Count',
            'settings.dataTitle': 'Data & Analysis Defaults',
            'settings.dataSub': 'CSV delimiter, quality thresholds, and cache management.',
            'settings.csvDelimiter': 'Default CSV Delimiter',
            'settings.delimiterComma': 'Comma (,)',
            'settings.delimiterSemicolon': 'Semicolon (;)',
            'settings.delimiterTab': 'Tab (\\t)',
            'settings.missingThreshold': 'Critical Missing Data Threshold (%)',
            'settings.missingThresholdHelp': 'Missing data rates above this percentage trigger critical warnings.',
            'settings.retentionDays': 'History Retention Period (Days)',
            'settings.clearCache': 'Clear Cache & Temporary Data',
            'settings.clearCacheDesc': 'Clears all local session data, uploaded datasets, and settings.',
            'settings.clearCacheBtn': 'Clear Cache',
            'settings.exportTitle': 'Export & Report Preferences',
            'settings.exportSub': 'PDF and table export sections, report title, and corporate logo.',
            'settings.exportSections': 'Default Sections Included in Reports',
            'settings.secSummary': 'Summary Cards',
            'settings.secMissing': 'Missing Value Analysis',
            'settings.secDuplicates': 'Duplicate Records',
            'settings.secDtypes': 'Data Type Check',
            'settings.secOutliers': 'Outliers',
            'settings.secScore': 'Quality Score & Breakdown',
            'settings.exportReportTitle': 'Default Report Title',
            'settings.exportLogo': 'Report Corporate Logo',
            'settings.exportLogoUpload': 'Upload Logo (PNG/JPG)',
            'settings.exportLogoRemove': 'Remove Logo',
            'settings.exportFormat': 'Default Export Format',
            'settings.notifyTitle': 'Notification Preferences',
            'settings.notifySub': 'Rules for notification center and system alerts.',
            'settings.notifyAnalysis': 'Notify when analysis is completed',
            'settings.notifyExport': 'Notify when PDF or report is ready',
            'settings.notifyErrors': 'Alert on system and critical data inconsistencies',
            'settings.notifySound': 'Enable notification sounds',
            'settings.accountTitle': 'Account & Security (Demo)',
            'settings.accountSub': 'Visual demo of user profile and security management.',
            'settings.name': 'First Name',
            'settings.surname': 'Last Name',
            'settings.email': 'Email Address',
            'settings.avatar': 'Profile Picture',
            'settings.avatarUpload': 'Upload Photo',
            'settings.changePassword': 'Change Password',
            'settings.currentPassword': 'Current Password',
            'settings.newPassword': 'New Password',
            'settings.confirmPassword': 'Confirm New Password',
            'settings.updatePasswordBtn': 'Update Password',
            'settings.dangerZone': 'Account Status & Danger Zone',
            'settings.logoutBtn': 'Sign Out',
            'settings.deleteAccountBtn': 'Delete Account',
            'settings.resetDefaultsBtn': 'Reset to Defaults',
            'settings.autoSaved': 'All changes are automatically saved',
            'settings.savedToast': 'Settings saved successfully ✓',
            'settings.resetConfirm': 'Are you sure you want to reset all settings to default values?',
            'settings.clearCacheConfirm': 'All cache and session data will be cleared. Do you confirm?',
            'settings.demoAlert': 'Demo Mode: This application has no real server authentication system.',

            // Profile & Account Menu
            'profile.edit': 'Edit Profile',
            'profile.accountSecurity': 'Account Settings & Security',
            'profile.usage': 'Usage & Limit Info',
            'profile.usage.dailyQuota': 'Daily Analysis Quota',
            'profile.usage.uploadLimit': 'Uploaded Data Limit',
            'profile.appearance': 'Appearance Mode',
            'profile.theme': 'Theme',
            'profile.themeDark': 'Dark Mode',
            'profile.themeLight': 'Light Mode',
            'profile.language': 'Language',
            'profile.help': 'Help & Documentation',
            'profile.feedback': 'Send Feedback',
            'profile.version': 'Version v1.0.0',
            'profile.logout': 'Sign Out',
            'profile.confirmLogout': 'Are you sure you want to sign out?',
            'profile.demoLogout': 'Demo mode: This application does not have a real session system.',
            'profile.role.analyst': 'Data Analyst',
            'profile.role.admin': 'Administrator',
            'profile.role.user': 'User',
            'profile.quotaUsed': '8 / 10 Operations',
            'profile.limitUsed': '42 MB / 50 MB',
            'profile.defaultName': 'Demo User',
            'profile.defaultEmail': 'demo@trexdatalab.com',
            'profile.feedbackToast': 'Your feedback has been sent successfully!',
            'profile.helpModalTitle': 'trex DataLab Help & Guide',
            'profile.helpModalDesc': 'Data quality score is calculated by weighted penalties on missing data, duplicates, outliers, and type inconsistencies.',

            // Support & Help Desk
            'support.title': 'Support & Help Desk',
            'support.subtitle': 'User guides, quality metrics, FAQs, and technical assistance.',
            'support.helpDocs': 'Quick Help & Documentation',
            'support.helpDocsSub': 'Step-by-step guides prepared for efficient platform usage.',
            'support.guides': 'User Guides',
            'support.guide.csv': 'CSV Upload Guide',
            'support.guide.csvDesc': 'Tips on dataset preparation, format compatibility, and 50MB limit.',
            'support.guide.preprocess': 'Data Cleaning & Preprocessing Guide',
            'support.guide.preprocessDesc': 'Handling missing values, filtering outliers, and type casting.',
            'support.guide.export': 'Export & Reporting Guide',
            'support.guide.exportDesc': 'Downloading PDF quality reports, cleaned CSV, and Excel formats.',
            'support.guide.visualization': 'Visualization & Chart Guide',
            'support.guide.visualizationDesc': 'Automated chart recommendations, distribution, scatter, and correlation plots.',
            'support.metrics': 'Metrics & Score Calculation',
            'support.metricsSub': 'The weighted penalty formula behind the Data Quality Score (0-100).',
            'support.metrics.qualityScore': 'Quality Score Penalty Formula',
            'support.faq': 'Frequently Asked Questions (FAQ)',
            'support.faqSub': 'Most frequently asked questions and quick answers.',
            'support.faq.q1': 'What are the supported file formats and size limits?',
            'support.faq.a1': 'trex DataLab currently supports .csv files only (comma, semicolon, or tab-delimited). The maximum file upload size is 50 MB.',
            'support.faq.q2': 'Why is the PDF report not downloading or looks distorted?',
            'support.faq.a2': 'The PDF generator (html2pdf) runs browser-side. Ensure you access the app via a web server (http://localhost:8000) and perform a hard refresh (Ctrl+F5) if needed.',
            'support.faq.q3': 'Are my data stored on the server? Is my privacy safe?',
            'support.faq.a3': 'No. Uploaded datasets are stored only in server memory during your active session. When the server restarts or is reset, all data is purged. User preferences reside only in your local browser (localStorage).',
            'support.faq.q4': 'What analyses and data operations are available?',
            'support.faq.a4': 'Automated quality audits (completeness, uniqueness, outliers), missing imputation (mean, median, mode, constant), type casting, Z-score/IQR outlier handling, and 7 interactive charts.',
            'support.faq.q5': 'How can I change the language and theme?',
            'support.faq.a5': 'You can change theme (Dark/Light) and language (TR/EN) with a single click in the Settings page or via the Profile Menu in the top header.',
            'support.contact': 'Contact & Support Ticket',
            'support.contactSub': 'Submit a support ticket or track your previous requests.',
            'support.ticket.create': 'Create New Support Ticket',
            'support.ticket.title': 'Ticket Subject',
            'support.ticket.titlePlaceholder': 'e.g., Encountering an error while exporting PDF',
            'support.ticket.category': 'Category',
            'support.ticket.catBug': 'Bug Report',
            'support.ticket.catUpload': 'Data Upload Issue',
            'support.ticket.catReport': 'Reporting Issue',
            'support.ticket.catViz': 'Visualization Issue',
            'support.ticket.catOther': 'Other / General Question',
            'support.ticket.priority': 'Priority',
            'support.ticket.priLow': 'Low',
            'support.ticket.priMed': 'Medium',
            'support.ticket.priHigh': 'High',
            'support.ticket.priCrit': 'Critical',
            'support.ticket.description': 'Description',
            'support.ticket.descPlaceholder': 'Describe the issue or reproduction steps in detail...',
            'support.ticket.attach': 'Attach Screenshot (Optional)',
            'support.ticket.attachBtn': 'Choose Image',
            'support.ticket.removeAttach': 'Remove Image',
            'support.ticket.submit': 'Submit Ticket',
            'support.ticket.myTickets': 'My Support Tickets',
            'support.ticket.empty': 'No support tickets created yet.',
            'support.ticket.status.inceleniyor': 'Under Review',
            'support.ticket.status.cozuldu': 'Resolved',
            'support.ticket.status.yanitBekleniyor': 'Awaiting Response',
            'support.email': 'Direct Email Support',
            'support.emailSub': 'For in-depth technical inquiries, send an email to our team.',
            'support.emailBtn': 'Send Email',
            'support.feedback': 'Feedback & Suggestions',
            'support.feedbackSub': 'Your suggestions help us improve trex DataLab.',
            'support.feedback.feature': 'Feature / Improvement Suggestion',
            'support.feedback.featurePlaceholder': 'A new feature or analysis method you would like to see...',
            'support.feedback.sendFeature': 'Submit Suggestion',
            'support.feedback.bug': 'Quick Bug Report',
            'support.status': 'System & Service Status',
            'support.statusSub': 'Live operational status of trex DataLab services.',
            'support.status.allOperational': 'All systems operational',
            'support.status.lastCheck': 'Last check: just now',
            'support.status.service1': 'Analysis & Quality Engine',
            'support.status.service2': 'Visualization & Chart Service',
            'support.status.service3': 'PDF & Reporting Module',
            'support.status.service4': 'FastAPI Web & API Server',
            'support.demoTicketCreated': 'Support ticket created successfully ✓',
            'support.demoFeedbackSent': 'Feedback submitted successfully ✓',

            // Machine Learning
            'ml.pageTitle': 'Machine Learning Model Training',
            'ml.smallSampleNote': 'Dataset has less than 50 rows; cross-validation skipped.',
            'ml.cvFixedHint': 'Small dataset: K=3 fixed',
            'ml.hyperParamsTitle': 'Model Hyperparameters',
            'ml.hyperParams.noModel': 'No adjustable hyperparameters for selected models.',
            'ml.hyperParams.nEstimators': 'Number of Trees (n_estimators)',
            'ml.hyperParams.maxDepth': 'Max Depth (max_depth)',
            'ml.hyperParams.c': 'Regularization Strength (C)',
            'ml.hyperParams.autoDepth': 'Automatic (Unlimited)',
            'ml.textColumnsNote': '{count} text column(s) detected and auto-excluded: {cols}',
            'ml.profileRows': 'rows',
            'ml.profileNumeric': 'Numeric',
            'ml.profileCategorical': 'Categorical',
            'ml.profileDatetime': 'Datetime',
            'ml.profileText': 'Text',
            'ml.profileMissing': 'Missing',
            'ml.profileTiny': 'Tiny Sample (<50)',
            'ml.profileSmall': 'Small Sample (50-150)',
            'ml.profileNormal': 'Normal Sample',
            'ml.profileLarge': 'Large Dataset (>2000)'
        }
    };

    let currentLang = 'tr';

    /**
     * Aktif dili al
     */
    function getLang() {
        if (window.SettingsStore && typeof window.SettingsStore.get === 'function') {
            return window.SettingsStore.get().language || 'tr';
        }
        return currentLang;
    }

    /**
     * Anahtara göre çeviri getir
     */
    function t(key, fallback) {
        const lang = getLang();
        const dict = I18N_DICT[lang] || I18N_DICT.tr;
        if (dict && typeof dict[key] !== 'undefined') {
            return dict[key];
        }
        // Bulunamazsa TR sözlüğüne bak
        if (I18N_DICT.tr && typeof I18N_DICT.tr[key] !== 'undefined') {
            return I18N_DICT.tr[key];
        }
        return fallback !== undefined ? fallback : key;
    }

    /**
     * DOM elemanına çeviriyi güvenle uygula (ikonları koruyarak)
     */
    function updateElementText(el, text) {
        if (!el) return;

        // Elemanın içinde ikon (span.material-symbols-outlined) var mı?
        const icons = el.querySelectorAll('.material-symbols-outlined');
        if (icons.length > 0) {
            // İkonları koruyup sadece metin düğümünü veya ikon dışındaki metni güncelle
            let textNodeFound = false;
            for (let i = 0; i < el.childNodes.length; i++) {
                const node = el.childNodes[i];
                if (node.nodeType === Node.TEXT_NODE && node.textContent.trim().length > 0) {
                    node.textContent = ' ' + text.trim() + ' ';
                    textNodeFound = true;
                    break;
                }
            }
            if (!textNodeFound) {
                // Metin düğümü yoksa veya span içine sarılıysa
                const textSpan = el.querySelector('span:not(.material-symbols-outlined)');
                if (textSpan) {
                    textSpan.textContent = text;
                } else {
                    // Sona metin ekle
                    el.appendChild(document.createTextNode(' ' + text));
                }
            }
        } else {
            el.textContent = text;
        }
    }

    /**
     * Sayfadaki tüm data-i18n elemanlarını güncelle
     */
    function applyTranslations(rootEl) {
        const root = rootEl || document.body;
        if (!root) return;

        // 1. Text Content
        const textElements = root.querySelectorAll('[data-i18n]');
        textElements.forEach(el => {
            const key = el.getAttribute('data-i18n');
            if (key) {
                const translated = t(key);
                updateElementText(el, translated);
            }
        });

        // 2. Placeholder
        const placeholderElements = root.querySelectorAll('[data-i18n-placeholder]');
        placeholderElements.forEach(el => {
            const key = el.getAttribute('data-i18n-placeholder');
            if (key) {
                el.placeholder = t(key, el.placeholder);
            }
        });

        // 3. Title
        const titleElements = root.querySelectorAll('[data-i18n-title]');
        titleElements.forEach(el => {
            const key = el.getAttribute('data-i18n-title');
            if (key) {
                el.title = t(key, el.title);
            }
        });

        // 4. Aria Label
        const ariaElements = root.querySelectorAll('[data-i18n-aria]');
        ariaElements.forEach(el => {
            const key = el.getAttribute('data-i18n-aria');
            if (key) {
                el.setAttribute('aria-label', t(key, el.getAttribute('aria-label')));
            }
        });
    }

    /**
     * Dili değiştir
     */
    function setLanguage(lang, persist = true) {
        if (lang !== 'tr' && lang !== 'en') lang = 'tr';
        currentLang = lang;

        document.documentElement.lang = lang;
        document.documentElement.setAttribute('data-lang', lang);

        if (persist && window.SettingsStore && typeof window.SettingsStore.set === 'function') {
            window.SettingsStore.set({ language: lang });
        }

        applyTranslations();

        const event = new CustomEvent('trex:lang-changed', { detail: { language: lang } });
        window.dispatchEvent(event);
    }

    // Global API
    window.I18N_DICT = I18N_DICT;
    window.t = t;
    window.applyTranslations = applyTranslations;
    window.setLanguage = setLanguage;

    // İlk çalıştırma
    function init() {
        const lang = getLang();
        setLanguage(lang, false);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
