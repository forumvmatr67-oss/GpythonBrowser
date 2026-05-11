document.addEventListener('DOMContentLoaded', () => {
    const searchInput = document.getElementById('search-input');
    const suggestionsBox = document.getElementById('suggestions');
    let timeoutId = null;

    if (searchInput) {
        searchInput.addEventListener('input', () => {
            clearTimeout(timeoutId);
            const query = searchInput.value.trim();
            if (query.length < 2) {
                suggestionsBox.style.display = 'none';
                return;
            }
            timeoutId = setTimeout(() => {
                fetch(`/suggest?q=${encodeURIComponent(query)}`)
                    .then(res => res.json())
                    .then(data => {
                        if (data.length) {
                            suggestionsBox.innerHTML = data.map(s => `<div class="suggestion-item">${s}</div>`).join('');
                            suggestionsBox.style.display = 'block';
                            document.querySelectorAll('.suggestion-item').forEach(el => {
                                el.addEventListener('click', () => {
                                    searchInput.value = el.innerText;
                                    suggestionsBox.style.display = 'none';
                                    document.querySelector('.search-form').submit();
                                });
                            });
                        } else {
                            suggestionsBox.style.display = 'none';
                        }
                    });
            }, 300);
        });
        document.addEventListener('click', (e) => {
            if (!searchInput.contains(e.target) && !suggestionsBox.contains(e.target)) {
                suggestionsBox.style.display = 'none';
            }
        });
    }
});
