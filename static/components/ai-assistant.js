(function () {
    if (document.getElementById('aiChatWidget')) return;

    // ---------- Tasarım değişkenleri ----------
    var COLORS = {
        primary: '#006b33',
        primaryHover: '#008742',
        bg: '#fcf9f8',
        text: '#1e293b',
        muted: '#64748b',
        border: '#e2e8f0',
        chip: '#f0fdf4',
        chipBorder: '#bbf7d0',
        userBubble: '#006b33',
        userText: '#ffffff',
        botBubble: '#f1f5f9',
        botText: '#1e293b'
    };

    // ---------- API anahtarı (settings'ten) ----------
    function getApiKey() {
        try {
            var s = JSON.parse(localStorage.getItem('trex_datalab_settings') || '{}');
            return s.geminiApiKey || '';
        } catch (e) { return ''; }
    }

    // Başlangıçta anahtar varsa backend'e bildir
    var savedKey = getApiKey();
    if (savedKey) {
        var API_BASE_INIT = (location.protocol === 'file:' || location.protocol === 'about:') ? 'http://127.0.0.1:8000' : '';
        fetch(API_BASE_INIT + '/api/ai-assistant/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ apiKey: savedKey })
        }).catch(function () {});
    }

    // ---------- Widget HTML ----------
    var widget = document.createElement('div');
    widget.id = 'aiChatWidget';
    widget.innerHTML = `
        <style>
            #ai-chat-btn { position: fixed; bottom: 24px; right: 24px; width: 60px; height: 60px; border-radius: 50%;
                background: linear-gradient(135deg, #006b33, #008742); border: none; cursor: pointer; z-index: 9999;
                display: flex; align-items: center; justify-content: center; box-shadow: 0 8px 24px rgba(0,107,51,0.35);
                transition: transform .2s ease, box-shadow .2s ease; }
            #ai-chat-btn:hover { transform: scale(1.08); box-shadow: 0 10px 30px rgba(0,107,51,0.5); }
            #ai-chat-btn svg { width: 34px; height: 34px; }
            #ai-chat-modal { position: fixed; bottom: 96px; right: 24px; width: 380px; max-width: calc(100vw - 32px);
                max-height: min(620px, calc(100vh - 120px)); background: ${COLORS.bg}; border: 1px solid ${COLORS.border};
                border-radius: 18px; box-shadow: 0 24px 60px rgba(0,0,0,0.25); z-index: 10000; overflow: hidden;
                display: none; flex-direction: column; transform-origin: bottom right;
                animation: aiChatPop .25s cubic-bezier(0.16, 1, 0.3, 1); }
            @keyframes aiChatPop { from { opacity: 0; transform: translateY(16px) scale(.96); }
                to { opacity: 1; transform: translateY(0) scale(1); } }
            #ai-chat-header { display: flex; align-items: center; gap: 10px; padding: 14px 16px;
                background: linear-gradient(135deg, #002812, #006b33); color: #fff; }
            #ai-chat-header svg { width: 28px; height: 28px; }
            #ai-chat-title { font-weight: 700; font-size: 14px; font-family: Inter, system-ui, sans-serif; }
            #ai-chat-subtitle { font-size: 11px; color: rgba(255,255,255,0.7); }
            #ai-chat-close { margin-left: auto; background: none; border: none; color: #fff; cursor: pointer;
                font-size: 20px; line-height: 1; padding: 4px 8px; border-radius: 8px; }
            #ai-chat-close:hover { background: rgba(255,255,255,0.15); }
            #ai-chat-chips { display: flex; flex-wrap: wrap; gap: 6px; padding: 10px 14px; border-bottom: 1px solid ${COLORS.border}; background: #ffffff; }
            .ai-chip { background: ${COLORS.chip}; border: 1px solid ${COLORS.chipBorder}; color: ${COLORS.primary};
                font-size: 11px; font-weight: 600; padding: 5px 10px; border-radius: 999px; cursor: pointer;
                transition: background .15s, transform .1s; font-family: Inter, system-ui, sans-serif; text-align: left; }
            .ai-chip:hover { background: #dcfce7; transform: translateY(-1px); }
            #ai-chat-messages { flex: 1; overflow-y: auto; padding: 14px; display: flex; flex-direction: column; gap: 10px;
                min-height: 180px; max-height: 380px; background: ${COLORS.bg}; }
            .ai-msg { max-width: 84%; padding: 10px 13px; border-radius: 14px; font-size: 13px; line-height: 1.5;
                font-family: Inter, system-ui, sans-serif; white-space: pre-wrap; word-break: break-word; }
            .ai-msg-user { align-self: flex-end; background: ${COLORS.userBubble}; color: ${COLORS.userText};
                border-bottom-right-radius: 4px; box-shadow: 0 2px 6px rgba(0,107,51,0.2); }
            .ai-msg-bot { align-self: flex-start; background: ${COLORS.botBubble}; color: ${COLORS.botText};
                border-bottom-left-radius: 4px; border: 1px solid #e2e8f0; }
            .ai-msg-error { align-self: flex-start; background: #fef2f2; color: #ba1a1a; border: 1px solid #fecaca; }
            #ai-chat-input-row { display: flex; gap: 8px; padding: 12px 14px; border-top: 1px solid ${COLORS.border}; background: #fff; }
            #ai-chat-input { flex: 1; border: 1px solid ${COLORS.border}; border-radius: 12px; padding: 10px 12px;
                font-size: 13px; font-family: Inter, system-ui, sans-serif; outline: none; color: ${COLORS.text}; }
            #ai-chat-input:focus { border-color: ${COLORS.primary}; box-shadow: 0 0 0 2px rgba(0,107,51,0.15); }
            #ai-chat-send { background: ${COLORS.primary}; color: #fff; border: none; border-radius: 12px; padding: 0 16px;
                cursor: pointer; font-weight: 600; font-size: 13px; transition: background .15s; }
            #ai-chat-send:hover { background: ${COLORS.primaryHover}; }
            #ai-chat-send:disabled { opacity: 0.5; cursor: not-allowed; }
            .ai-typing { align-self: flex-start; color: ${COLORS.muted}; font-size: 12px; font-style: italic;
                font-family: Inter, system-ui, sans-serif; padding: 4px 8px; }
        </style>

        <button id="ai-chat-btn" title="trex AI Asistanı">
            <svg viewBox="0 0 24 24" fill="#ffffff" xmlns="http://www.w3.org/2000/svg">
                <path d="M12 2c-4 0-7 2.5-7 6 0 1.5.6 2.8 1.5 3.8-.2 1.7-1 3.2-2.3 4.4 2.4.3 4.4-.2 5.9-1.3.6.2 1.2.3 1.9.3 4 0 7-2.5 7-6s-3-7-7-7zM9 7c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1zm6 0c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1zm-3 6c1.5 0 2.8-.6 3.7-1.5-.4 2-1.6 3.5-3.7 3.5s-3.3-1.5-3.7-3.5c.9.9 2.2 1.5 3.7 1.5z"/>
            </svg>
        </button>

        <div id="ai-chat-modal">
            <div id="ai-chat-header">
                <svg viewBox="0 0 24 24" fill="#ffffff" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 2c-4 0-7 2.5-7 6 0 1.5.6 2.8 1.5 3.8-.2 1.7-1 3.2-2.3 4.4 2.4.3 4.4-.2 5.9-1.3.6.2 1.2.3 1.9.3 4 0 7-2.5 7-6s-3-7-7-7zM9 7c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1zm6 0c.6 0 1 .4 1 1s-.4 1-1 1-1-.4-1-1 .4-1 1-1zm-3 6c1.5 0 2.8-.6 3.7-1.5-.4 2-1.6 3.5-3.7 3.5s-3.3-1.5-3.7-3.5c.9.9 2.2 1.5 3.7 1.5z"/>
                </svg>
                <div>
                    <div id="ai-chat-title">trex AI Asistanı</div>
                    <div id="ai-chat-subtitle">Veri setinize dair sorularınızı yanıtlar</div>
                </div>
                <button id="ai-chat-close" title="Kapat">&times;</button>
            </div>
            <div id="ai-chat-chips">
                <button class="ai-chip" data-q="Veri kalitesini özetle">Veri kalitesini özetle</button>
                <button class="ai-chip" data-q="En önemli değişkenler hangileri?">En önemli değişkenler hangileri?</button>
                <button class="ai-chip" data-q="Aykırı değer analizi yap">Aykırı değer analizi yap</button>
            </div>
            <div id="ai-chat-messages"></div>
            <div id="ai-chat-input-row">
                <input id="ai-chat-input" type="text" placeholder="Sorunuzu yazın..." autocomplete="off">
                <button id="ai-chat-send">Gönder</button>
            </div>
        </div>
    `;
    document.body.appendChild(widget);

    var btn = document.getElementById('ai-chat-btn');
    var modal = document.getElementById('ai-chat-modal');
    var closeBtn = document.getElementById('ai-chat-close');
    var messages = document.getElementById('ai-chat-messages');
    var input = document.getElementById('ai-chat-input');
    var sendBtn = document.getElementById('ai-chat-send');
    var chips = document.querySelectorAll('.ai-chip');

    function currentPage() {
        var p = location.pathname.split('/').pop() || 'index.html';
        return p || 'index.html';
    }

    function addMessage(text, kind) {
        var div = document.createElement('div');
        div.className = 'ai-msg ai-msg-' + kind;
        div.textContent = text;
        messages.appendChild(div);
        messages.scrollTop = messages.scrollHeight;
    }

    async function ask(question) {
        if (!question) return;
        addMessage(question, 'user');
        input.value = '';
        var typing = document.createElement('div');
        typing.className = 'ai-typing';
        typing.textContent = 'trex asistanı yazıyor...';
        messages.appendChild(typing);
        messages.scrollTop = messages.scrollHeight;
        sendBtn.disabled = true;

        var API_BASE = (location.protocol === 'file:' || location.protocol === 'about:') ? 'http://127.0.0.1:8000' : '';

        try {
            var res = await fetch(API_BASE + '/api/ai-assistant/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: question, page: currentPage() })
            });
            var data = await res.json();
            typing.remove();
            if (res.ok && data.reply) {
                addMessage(data.reply, 'bot');
            } else {
                addMessage((data.detail || data.message || 'Bir hata oluştu.'), 'error');
            }
        } catch (err) {
            typing.remove();
            addMessage('Asistanla bağlantı kurulamadı. Sunucunun çalıştığından emin olun.', 'error');
        }
        sendBtn.disabled = false;
        messages.scrollTop = messages.scrollHeight;
    }

    btn.addEventListener('click', function () {
        if (modal.style.display === 'flex') {
            modal.style.display = 'none';
        } else {
            modal.style.display = 'flex';
            if (messages.children.length === 0) {
                var greet = document.createElement('div');
                greet.className = 'ai-msg ai-msg-bot';
                greet.textContent = 'Merhaba! Veri setiniz ve şu anki sayfanız hakkında sorularınızı yanıtlayabilirim. Bir öneriye tıklayın veya sorunuzu yazın.';
                messages.appendChild(greet);
            }
            input.focus();
        }
    });

    closeBtn.addEventListener('click', function () { modal.style.display = 'none'; });

    sendBtn.addEventListener('click', function () { ask(input.value.trim()); });
    input.addEventListener('keydown', function (e) { if (e.key === 'Enter') ask(input.value.trim()); });
    chips.forEach(function (c) { c.addEventListener('click', function () { ask(c.getAttribute('data-q')); }); });
})();
