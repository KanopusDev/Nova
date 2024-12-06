// Search form handling
document.querySelector('.search-form')?.addEventListener('submit', (e) => {
    const form = e.target;
    const input = form.querySelector('input[name="q"]');
    const button = form.querySelector('.search-button');

    if (!input.value.trim()) {
        e.preventDefault();
        input.classList.add('shake');
        setTimeout(() => input.classList.remove('shake'), 820);
        return;
    }

    button.classList.add('loading');
});

// Voice search
document.querySelector('.voice-search')?.addEventListener('click', () => {
    if ('webkitSpeechRecognition' in window) {
        const recognition = new webkitSpeechRecognition();
        recognition.continuous = false;
        recognition.interimResults = false;

        recognition.onresult = (event) => {
            const input = document.querySelector('.search-input');
            input.value = event.results[0][0].transcript;
            input.form.submit();
        };

        recognition.start();
    }
});

// Animate results on scroll
const observeResults = () => {
    const observer = new IntersectionObserver(
        (entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                }
            });
        },
        { threshold: 0.1 }
    );

    document.querySelectorAll('.result-item').forEach(item => {
        observer.observe(item);
    });
};

// Initialize
if (window.location.pathname === '/') {
    document.querySelector('.search-input')?.focus();
}

document.addEventListener('DOMContentLoaded', observeResults);