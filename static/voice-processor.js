
(function () {
    let recognition;
    let isListening = false;
    let activeBtn = null;
    let activeInput = null;

    // Check for browser support
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        console.warn("Speech Recognition not supported in this browser.");
        return;
    }

    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    // We don't set recognition.lang to allow automatic multi-language support (browser default)

    recognition.onstart = () => {
        isListening = true;
        if (activeBtn) activeBtn.classList.add('recording');
        updateStatus("Listening... Speak in any language.");
    };

    recognition.onresult = async (event) => {
        const transcript = event.results[0][0].transcript;
        updateStatus("Translating to English...");

        try {
            const response = await fetch('/api/translate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ text: transcript })
            });
            const data = await response.json();

            if (data.success && activeInput) {
                activeInput.value = data.translated_text;
                updateStatus("Translated to English!");

                // If it's the search input on the map page, trigger the search automatically
                if (activeInput.id === 'search-input' && typeof window.searchLocation === 'function') {
                    window.searchLocation();
                }
            } else if (activeInput) {
                activeInput.value = transcript;
                updateStatus("Done (Translation unavailable).");
            }
        } catch (err) {
            console.error("Translation error:", err);
            if (activeInput) activeInput.value = transcript;
            updateStatus("Done (Error).");
        }
    };

    recognition.onerror = (event) => {
        console.error("Speech Recognition Error:", event.error);
        updateStatus("Error: " + event.error);
        stopState();
    };

    recognition.onend = () => {
        stopState();
    };

    function stopState() {
        isListening = false;
        if (activeBtn) {
            activeBtn.classList.remove('recording');
            activeBtn.innerHTML = '🎤';
        }
    }

    function updateStatus(msg) {
        const statusBox = document.getElementById('voice-status');
        if (statusBox) {
            statusBox.innerText = msg;
        } else {
            console.log("Voice Status:", msg);
        }
    }

    // Attach to all microphone buttons
    function attachListeners() {
        // Support various button patterns used in the project
        const selectors = [
            '#voice-btn',           // reviews.html
            '#voice-btn-login',     // login.html
            '#voice-btn-register',  // login.html
            '#voice-btn-search',    // navigation.html
            '[data-target]'          // generic with data-target
        ];

        document.querySelectorAll(selectors.join(',')).forEach(btn => {
            if (btn.dataset.voiceAttached) return;
            btn.dataset.voiceAttached = "true";

            btn.addEventListener('click', () => {
                if (isListening) {
                    recognition.stop();
                    return;
                }

                activeBtn = btn;
                // Determine target input
                const targetId = btn.dataset.target || 'message-input';
                activeInput = document.getElementById(targetId);

                if (!activeInput && btn.id === 'voice-btn') {
                    activeInput = document.getElementById('message-input');
                }

                if (activeInput) {
                    recognition.start();
                } else {
                    console.error("No target input found for voice button", btn);
                }
            });
        });
    }

    // Run on load and also provide a global way to re-attach if needed
    window.addEventListener('load', attachListeners);
    window.refreshVoiceListeners = attachListeners;

    // Immediate check for dynamically loaded elements or if script loaded after DOM
    if (document.readyState === "complete" || document.readyState === "interactive") {
        attachListeners();
    }
})();
