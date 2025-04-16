// Toggle
document.addEventListener('DOMContentLoaded', function () {
    const themeToggle = document.getElementById('theme-toggle');

    if (!themeToggle) return;

    // Initialize icon state based on saved preference
    const savedTheme = localStorage.getItem('theme');
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        themeToggle.classList.remove('bi-moon-fill');
        themeToggle.classList.add('bi-sun-fill');
    }

    themeToggle.addEventListener('click', function () {
        document.body.classList.toggle('dark-mode');

        const isDark = document.body.classList.contains('dark-mode');
        localStorage.setItem('theme', isDark ? 'dark' : 'light');

        themeToggle.classList.toggle('bi-moon-fill');
        themeToggle.classList.toggle('bi-sun-fill');
    });
});

// Search songs suggestion box
document.addEventListener('DOMContentLoaded', function () {
    const searchBox = document.getElementById('search-box');
    const suggestionBox = document.getElementById('suggestion-box');

    let debounceTimer;

    searchBox.addEventListener('input', () => {
        const query = searchBox.value.trim();
        clearTimeout(debounceTimer);

        if (query.length === 0) {
            suggestionBox.style.display = 'none';
            suggestionBox.innerHTML = '';
            return;
        }

        debounceTimer = setTimeout(() => {
            fetch(`/search?q=${encodeURIComponent(query)}`)
                .then(res => res.json())
                .then(data => {
                    suggestionBox.innerHTML = '';
                    if (data.length === 0) {
                        suggestionBox.style.display = 'none';
                        return;
                    }

                    data.forEach(hit => {
                        const item = document.createElement('a');
                        item.className = 'dropdown-item';
                        // item.href = `/song/${hit.result.id}?title=${encodeURIComponent(hit.result.title)}&artist=${encodeURIComponent(hit.result.primary_artist.name)}`;
                        item.textContent = hit.result.full_title;

                        item.style.cursor = 'pointer';
                        item.addEventListener('click', () => {
                            const title = hit.result.title;
                            const artist = hit.result.primary_artist.name;
                            const song_id = hit.result.id;

                            fetch('/start_processing', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({ title, artist, song_id })
                            })
                            .then(res => res.json())
                            .then(data => {
                                if (data.redirect_url) {
                                    window.location.href = data.redirect_url;
                                } else {
                                    alert('Failed to start processing.');
                                }
                            })
                            .catch(err => {
                                console.error('Error starting processing:', err);
                                alert('Error occurred while starting processing.');
                            });
                        });

                        suggestionBox.appendChild(item);
                    });

                    suggestionBox.style.display = 'block';
                })
                .catch(err => {
                    console.error('Error fetching Genius suggestions:', err);
                });
        }, 300);
    });

    // Hide dropdown on blur
    searchBox.addEventListener('blur', () => {
        setTimeout(() => {
            suggestionBox.style.display = 'none';
        }, 200);
    });
});


// Lyrics Interface - 2nd Page

const audio = document.getElementById('audio');
const playBtn = document.getElementById('playpause');
const seekbar = document.getElementById('seekbar');
const restartBtn = document.getElementById('restart');
const fullscreenBtn = document.getElementById('fullscreen');
const lyricsDiv = document.getElementById('lyrics-container');
const lyricsBox = document.getElementById('lyrics-box');
const lyricsUrl = lyricsDiv.dataset.json;
const timeDisplay = document.getElementById('time-display');

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, '0')}`;
}

let lyrics = [];
let currentLineIndex = -1;

fetch(lyricsUrl)
    .then(res => res.json())
    .then(data => {
        lyrics = data;
        renderLyricsLines();
    })
    .catch(err => console.error("Failed to load lyrics:", err));

function renderLyricsLines() {
    lyricsDiv.innerHTML = '';

    lyrics.forEach((lineObj, index) => {
        const div = document.createElement("div");
        div.textContent = lineObj.line;
        div.id = `line-${index}`;
        lyricsDiv.appendChild(div);
    });
}

function highlightLine(index) {
    // Remove existing highlight
    document.querySelectorAll(".highlight").forEach(el => el.classList.remove("highlight"));

    const lineEl = document.getElementById(`line-${index}`);
    const lyricsContainer = document.getElementById('lyrics-container');

    if (lineEl && lyricsContainer) {
        lineEl.classList.add("highlight");

        // Check if line is out of visible container viewport
        const containerTop = lyricsContainer.scrollTop;
        const containerBottom = containerTop + lyricsContainer.clientHeight;

        const lineOffsetTop = lineEl.offsetTop;
        const lineOffsetBottom = lineOffsetTop + lineEl.offsetHeight;

        if (lineOffsetTop < containerTop || lineOffsetBottom > containerBottom) {
            // Only scroll the lyrics container, not the whole page
            lyricsContainer.scrollTo({
                top: lineOffsetTop - lyricsContainer.clientHeight / 2,
                behavior: 'smooth'
            });
        }
    }
}


audio.ontimeupdate = () => {
    const t = audio.currentTime;
    seekbar.value = t;

    if (!isNaN(audio.duration)) {
        timeDisplay.textContent = `${formatTime(audio.currentTime)} / ${formatTime(audio.duration)}`;
    }    

    for (let i = 0; i < lyrics.length; i++) {
        if (t >= lyrics[i].start && t <= lyrics[i].end) {
            if (currentLineIndex !== i) {
                currentLineIndex = i;
                highlightLine(i);
            }
            break;
        }
    }
};

audio.onloadedmetadata = () => {
    seekbar.max = audio.duration;
    timeDisplay.textContent = `0:00 / ${formatTime(audio.duration)}`;
};

seekbar.oninput = () => {
    audio.currentTime = seekbar.value;
};

playBtn.onclick = () => {
    if (audio.paused) {
        audio.play();
        playBtn.innerHTML = '<i class="bi bi-pause-fill"></i>';
    } else {
        audio.pause();
        playBtn.innerHTML = '<i class="bi bi-play-fill"></i>';
    }
};

restartBtn.onclick = () => {
    audio.currentTime = 0;
    highlightLine(-1);
};

fullscreenBtn.onclick = () => {
    if (!document.fullscreenElement) {
        lyricsBox.requestFullscreen();
        lyricsBox.classList.add("fullscreen-mode");
    } else {
        document.exitFullscreen();
        lyricsBox.classList.remove("fullscreen-mode");
    }
};



function processSong(songId, title, artist) {
    fetch('/start_processing', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({song_id: songId, title: title, artist: artist})
    })
    .then(res => res.json())
    .then(data => {
        if (data.redirect_url) {
            window.location.href = data.redirect_url;
        } else {
            alert("Something went wrong. Please try again later.");
        }
    })
    .catch(err => {
        console.error("Error triggering processing:", err);
        alert("An error occurred.");
    });
}
