/*
  Expected shape of pattern.frames (passed via data-frames on each .pat-item):
  [
    { "timestamp": "2025-04-21T07:47:23", "url": "/static/frames/abc.jpg" },
    ...
  ]
  Frames should already be sorted oldest → newest by the server.
*/

const TAG_CLASSES = {
    daily: 'tag-daily', vehicle: 'tag-vehicle',
    person: 'tag-person', anomaly: 'tag-anomaly', recurring: 'tag-recurring'
};

let activePattern = null;   // the currently selected pattern object
let activeFrames  = [];     // parsed frames array for active pattern
let viewMode      = 'grid';
let tlPct         = 0;

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmtTime(d) {
    return d.toTimeString().slice(0, 8);
}

function fmtDate(d) {
    return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}

// ── Sidebar ───────────────────────────────────────────────────────────────────

function filterSidebar(q) {
    document.querySelectorAll('.pat-item').forEach(el => {
        const name = el.querySelector('.pat-name').textContent.toLowerCase();
        const desc = el.querySelector('.pat-desc').textContent.toLowerCase();
        el.style.display = (!q || name.includes(q) || desc.includes(q)) ? '' : 'none';
    });
}

document.querySelectorAll('.pat-item').forEach(el => {
    el.addEventListener('click', () => {
        document.querySelectorAll('.pat-item').forEach(i => i.classList.remove('active'));
        el.classList.add('active');

        console.log(el.dataset.frames)

        activePattern = { id: el.dataset.id, name: el.querySelector('.pat-name').textContent };
        activeFrames  = JSON.parse(el.dataset.frames).map(f => ({
            ...f,
            ts: new Date(f.timestamp)
        }));
        renderFeed();
    });
});

document.getElementById('pat-search').addEventListener('input', e => filterSidebar(e.target.value.toLowerCase()));

// ── Feed ──────────────────────────────────────────────────────────────────────

function renderFeed()
{
    const feed   = document.getElementById('feed');
    const title  = document.getElementById('c-title');
    const sub    = document.getElementById('c-sub');

    if (!activePattern) {
        title.textContent = 'Select a pattern';
        sub.textContent   = 'Choose a detected pattern from the panel on the right';
        feed.innerHTML    = '<div class="empty-feed">No pattern selected</div>';
        return;
    }
    
    title.textContent   = activePattern.name;

    // Filter by timeline position
    const minSec = tlPct * 86400;
    const frames = activeFrames.filter(f => {
        const sec = f.ts.getHours() * 3600 + f.ts.getMinutes() * 60 + f.ts.getSeconds();
        return sec >= minSec;
    });

    if (!frames.length) {
        feed.innerHTML = '<div class="empty-feed">No frames after selected time</div>';
        return;
    }

    // Group by day
    const byDay = {};
    frames.forEach(f => {
        const dk = f.ts.toDateString();
        if (!byDay[dk]) byDay[dk] = { label: fmtDate(f.ts), frames: [] };
        byDay[dk].frames.push(f);
    });

    let html = '';
    Object.values(byDay).forEach(day => {
        html += `<div class="day-sep">
            <div class="day-line"></div>
            <span class="day-label">${day.label}</span>
            <div class="day-line"></div>
        </div>`;

        if (viewMode === 'grid') {
            html += `<div class="grid-view">`;
            day.frames.forEach(f => {
                html += `<div class="img-card">
                    <img class="img-thumb" src="${f.url}" alt="Frame at ${fmtTime(f.ts)}" loading="lazy">
                    <div class="img-foot">
                        <div class="img-time">${fmtTime(f.ts)}</div>
                    </div>
                </div>`;
            });
            html += `</div>`;
        } else {
            html += `<div class="list-view">`;
            day.frames.forEach(f => {
                html += `<div class="img-row">
                    <img class="row-thumb" src="${f.url}" alt="Frame at ${fmtTime(f.ts)}" loading="lazy">
                    <div class="row-info">
                        <div class="row-time">${fmtTime(f.ts)}</div>
                    </div>
                </div>`;
            });
            html += `</div>`;
        }
    });

    feed.innerHTML = html;
}

// ── View toggle ───────────────────────────────────────────────────────────────

document.getElementById('btn-grid').addEventListener('click', () => {
    viewMode = 'grid';
    document.getElementById('btn-grid').classList.add('active');
    document.getElementById('btn-list').classList.remove('active');
    renderFeed();
});

document.getElementById('btn-list').addEventListener('click', () => {
    viewMode = 'list';
    document.getElementById('btn-list').classList.add('active');
    document.getElementById('btn-grid').classList.remove('active');
    renderFeed();
});