
//  Name with which to store pattern in session
const SESSION_KEY = 'patterns_active_id';

let activePattern = null;   // the currently selected pattern object
let activeFrames  = [];     // parsed frames array for active pattern
let viewMode      = 'grid'; // state of the view
let tlPct         = 0;      // timeline postion

/**
 * Formate a datetime object to time string
 * @param {Object} d A datetime object to format
 * @returns {String} String representation of that time
 */
function fmtTime(d)
{
    return d.toTimeString().slice(0, 8);
}

/**
 * Formate a datetime object to date string
 * @param {Object} d A datetime object to format
 * @returns {String} String representation of that date
 */
function fmtDate(d) {
    return d.toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' });
}

/**
 * Save the id of the currently selected pattern to usersession so it can loaded later
 * @param {int} id The currently selected id of a pattern
 * @returns {void} 
 */
function saveSession(id){
    try { sessionStorage.setItem(SESSION_KEY, id); } catch (_) {}
}

/**
 * Loads a saved id if one exists, otherwise null
 * @returns {int} pattern id or null
 */
function loadSession() {
    try { return sessionStorage.getItem(SESSION_KEY); } catch (_) { return null; }
}

/**
 * Erase a stored id from the session
 * @returns {void} 
 */
function clearSession() {
    try { sessionStorage.removeItem(SESSION_KEY); } catch (_) {}
}

/**
 * Select the given pattern to be the newly selected one
 * @param {Element} el The html element corrisponding to a pattern from the pattern list
 * @returns {void}
 */
function selectPatternEl(el)
{
    //  Set all other patterns to be inactive, then make the selected one active
    document.querySelectorAll('.pat-item').forEach(i => i.classList.remove('active'));
    el.classList.add('active');
    //  Move the pattern 
    el.scrollIntoView({ block: 'nearest', behavior: 'smooth' });

    //  Get the information about said pattern, and move it to the global variables for it
    activePattern = { id: el.dataset.id, name: el.querySelector('.pat-name').textContent };
    activeFrames  = JSON.parse(el.dataset.frames).map(f => ({
        ...f,
        ts: new Date(f.timestamp)
    }));

    //  Save the selection to user session, then update view
    saveSession(activePattern.id);
    renderFeed();
}

/**
 * Filter the list of patterns of the right side by the given query
 * @param {String} q the current search query
 * @returns {void}
 */
function filterSidebar(q)
{
    document.querySelectorAll('.pat-item').forEach(el => {
        //  get all of the names and descriptions for each pattern
        const name = el.querySelector('.pat-name').textContent.toLowerCase();
        const desc = el.querySelector('.pat-desc').textContent.toLowerCase();

        //  if the query does not exist, show everything, else
        //      if the quesry is not in the name or description, hide the element
        el.style.display = (!q || name.includes(q) || desc.includes(q)) ? '' : 'none';
    });
}

//  Set a click listener for every item in the pattern menu
//      if clicked, show that pattern to main view
document.querySelectorAll('.pat-item').forEach(el => {
    el.addEventListener('click', () => selectPatternEl(el));
});

//  If the search bar content changes, try filtering the list again
document.getElementById('pat-search').addEventListener('input', e => filterSidebar(e.target.value.toLowerCase()));

/**
 * Renders all of the new content based on the selected pattern.
 * @returns {void}
 */
function renderFeed() {
    const feed  = document.getElementById('feed');
    const title = document.getElementById('c-title');
    const sub   = document.getElementById('c-sub');

    //  If no pattern is selected, render a default empty block
    if (!activePattern) {
        title.textContent = 'Select a pattern';
        sub.textContent   = 'Choose a detected pattern from the panel on the right';
        feed.innerHTML    = '<div class="empty-feed">No pattern selected</div>';
        return;
    }

    title.textContent = activePattern.name;
    sub.textContent   = `${activeFrames.length} frame${activeFrames.length !== 1 ? 's' : ''}`;

    // Filter by timeline position
    const minSec = tlPct * 86400;
    const frames = activeFrames.filter(f => {
        const sec = f.ts.getHours() * 3600 + f.ts.getMinutes() * 60 + f.ts.getSeconds();
        return sec >= minSec;
    });

    //  if filter removes all, show a message
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

    //  based on the selcted view state, change which block is shown
    let html = '';
    Object.values(byDay).forEach(day => {
        html += `<div class="day-sep">
            <div class="day-line"></div>
            <span class="day-label">${day.label}</span>
            <div class="day-line"></div>
        </div>`;

        //  grid mode, larger picture and multiple per block
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
        //  list mode, smaller pictures single entry per line
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

//  add event listeners to the grid selector
document.getElementById('btn-grid').addEventListener('click', () => {
    viewMode = 'grid';
    document.getElementById('btn-grid').classList.add('active');
    document.getElementById('btn-list').classList.remove('active');
    renderFeed();
});

//  add event listeners to the list selectors
document.getElementById('btn-list').addEventListener('click', () => {
    viewMode = 'list';
    document.getElementById('btn-list').classList.add('active');
    document.getElementById('btn-grid').classList.remove('active');
    renderFeed();
});

//  when rendering in mobile mode, the regular pattern selector is hidden
//  instead a full down menu is shown
const drawer = (function () {
    const sidebar   = document.querySelector('.sidebar');
    const backdrop  = document.getElementById('sidebar-backdrop');
    const drawerBtn = document.getElementById('btn-patterns');

    if (!sidebar || !backdrop || !drawerBtn) return { open() {}, close() {} };

    function open() {
        sidebar.classList.add('open');
        backdrop.classList.add('open');
        document.body.style.overflow = 'hidden';
    }

    function close() {
        sidebar.classList.remove('open');
        backdrop.classList.remove('open');
        document.body.style.overflow = '';
    }

    drawerBtn.addEventListener('click', () => {
        sidebar.classList.contains('open') ? close() : open();
    });

    backdrop.addEventListener('click', close);

    // Close drawer and mark button when a pattern is selected
    document.querySelectorAll('.pat-item').forEach(el => {
        el.addEventListener('click', () => {
            close();
            drawerBtn.classList.add('has-selection');
        });
    });

    // Swipe-up to close
    let startY = 0;
    sidebar.addEventListener('touchstart', e => { startY = e.touches[0].clientY; }, { passive: true });
    sidebar.addEventListener('touchend', e => {
        if (startY - e.changedTouches[0].clientY > 60) close();
    }, { passive: true });

    return { open, close };
})();

(function init() {
    const savedId = loadSession();

    if (savedId) {
        // Try to restore the previously selected pattern
        const el = document.querySelector(`.pat-item[data-id="${savedId}"]`);
        if (el) {
            selectPatternEl(el);
            // Mark the drawer button as having a selection
            const drawerBtn = document.getElementById('btn-patterns');
            if (drawerBtn) drawerBtn.classList.add('has-selection');
            return;
        }
        // Saved ID no longer exists
        clearSession();
    }

    // No saved pattern: open the drawer on mobile so the user sees the list
    // immediately. On desktop the sidebar is always visible so nothing extra needed.
    if (window.matchMedia('(max-width: 768px)').matches) {
        drawer.open();
    }
})();

//  this is what sets up the magnified view when an image is clicked from the main view
const lightbox = (function () {
    const lb        = document.getElementById('lightbox');
    const lbImg     = document.getElementById('lb-img');
    const lbCounter = document.getElementById('lb-counter');
    const lbTime    = document.getElementById('lb-time');
    const lbStrip   = document.getElementById('lb-strip');
    const lbClose   = document.getElementById('lb-close');
    const lbPrev    = document.getElementById('lb-prev');
    const lbNext    = document.getElementById('lb-next');

    let frames  = [];   // flat array of all visible frames at open time
    let current = 0;    // index into frames

    function fmtFull(d) {
        return d.toLocaleString('en-GB', {
            weekday: 'short', day: 'numeric', month: 'short',
            year: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit'
        });
    }

    function show(index) {
        if (!frames.length) return;
        current = Math.max(0, Math.min(index, frames.length - 1));
        const f = frames[current];

        // Fade swap
        lbImg.classList.add('switching');
        setTimeout(() => {
            lbImg.src = f.url;
            lbImg.alt = `Frame at ${fmtFull(f.ts)}`;
            lbImg.classList.remove('switching');
        }, 100);

        lbCounter.textContent = `${current + 1} / ${frames.length}`;
        lbTime.textContent    = fmtFull(f.ts);

        // Update filmstrip active state and scroll into view
        lbStrip.querySelectorAll('.lb-strip-thumb').forEach((el, i) => {
            el.classList.toggle('active', i === current);
        });
        const activeThumb = lbStrip.children[current];
        if (activeThumb) activeThumb.scrollIntoView({ inline: 'center', behavior: 'smooth', block: 'nearest' });

        lbPrev.disabled = current === 0;
        lbNext.disabled = current === frames.length - 1;
    }

    function open(allFrames, startIndex) {
        frames  = allFrames;
        current = startIndex;

        // Build filmstrip
        lbStrip.innerHTML = frames.map((f, i) =>
            `<img class="lb-strip-thumb" src="${f.url}" alt="Frame ${i + 1}" data-index="${i}" loading="lazy">`
        ).join('');

        lbStrip.querySelectorAll('.lb-strip-thumb').forEach(el => {
            el.addEventListener('click', () => show(parseInt(el.dataset.index, 10)));
        });

        lb.classList.add('open');
        document.body.style.overflow = 'hidden';
        show(startIndex);
    }

    function close() {
        lb.classList.remove('open');
        document.body.style.overflow = '';
        lbImg.src = '';
    }

    lbClose.addEventListener('click', close);
    lbPrev.addEventListener('click',  () => show(current - 1));
    lbNext.addEventListener('click',  () => show(current + 1));

    // Keyboard navigation
    document.addEventListener('keydown', e => {
        if (!lb.classList.contains('open')) return;
        if (e.key === 'ArrowLeft')  show(current - 1);
        if (e.key === 'ArrowRight') show(current + 1);
        if (e.key === 'Escape')     close();
    });

    // Click outside image to close
    lb.addEventListener('click', e => {
        if (e.target === lb) close();
    });

    // Swipe left/right on mobile
    let touchStartX = 0;
    lb.addEventListener('touchstart', e => { touchStartX = e.touches[0].clientX; }, { passive: true });
    lb.addEventListener('touchend', e => {
        const dx = e.changedTouches[0].clientX - touchStartX;
        if (Math.abs(dx) > 50) dx < 0 ? show(current + 1) : show(current - 1);
    }, { passive: true });

    return { open, close };
})();

document.getElementById('feed').addEventListener('click', e => {
    const card = e.target.closest('.img-card, .img-row');
    if (!card) return;

    // Collect all currently rendered frames in DOM order
    const allCards = [...document.querySelectorAll('#feed .img-card, #feed .img-row')];
    const index    = allCards.indexOf(card);
    const frames   = allCards.map(c => {
        const img  = c.querySelector('img');
        const time = c.querySelector('.img-time, .row-time');
        return {
            url: img ? img.src : '',
            ts:  time ? new Date(`1970-01-01T${time.textContent}`) : new Date()
        };
    });

    // Use the richer activeFrames data if available (has full date, not just time)
    // Match by position since order is preserved by renderFeed
    const richFrames = activeFrames.length === frames.length
        ? activeFrames
        : frames;

    lightbox.open(richFrames, index);
});