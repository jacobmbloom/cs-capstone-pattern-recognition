///////////////
//  Globals  //
///////////////

//  The valid list of statuses that a file can have
//      For the most part, statuses move from left to right, one step at a time
const STATUS_LABELS = { uploading: 'Uploading', waiting: 'Waiting', processing: 'Processing', ready: 'Ready', failed: 'Failed', missing: 'Missing' };

let files = [];   //  List of all uploaded files, including placholders for missing
//  Example entry:
/*
    {
        id: 1,
        name: 'site_survey_batch_A.csv',
        size: '12 KB',
        uploadedAt: Date.now(),
        type: 'csv',
        status: 'ready',
        uploadProgress: 100,
        processingProgress: 100,
        selected: false,
        _cancel: null,
        childIds: [2, 3, 4],
        expanded: false
    }
*/
let nextId = 1;             //  Next id to use for files
let searchQuery = '';       //  Value of the searchbar  
let sortMode = 'recent';    //  Current sorting method
let newFileIds = new Set(); //  TODO: DESCRIBE




////////////////////////////
//  Server File Handling  //
////////////////////////////

//  Object to hold the various functions to handle files.
//  Build like this so that other functions can cancel it easily
const ServerAdapter = {

    /**
     * Called when a file is dropped/picked and ready to upload.
     * @param {File} file  - The actual file blob returned from a file dialog
     * @param {Int} fileId - The id assigned to the file state from files
     * @param {Function} onProgress        - The function called to render updates of upload
     * @param {Function} onReady           - The function called when upload is finished
     * @param {Function} onProcessingError - The function called when something goes wrong
     * @returns 
     */
    subscribeUpload(file, fileId, { onProgress, onUploaded, onUploadError })
    {
        //  Create hidden form data
        const fd = new FormData();
        fd.append("files", file);

        //  Create POST request and subscribe to progress results
        const xhr = new XMLHttpRequest();
        xhr.open("POST", "/api/upload");
        xhr.upload.onprogress = e => onProgress(fileId, Math.round(e.loaded/e.total*100));
        xhr.onload  = e => onUploaded(fileId, e.dependancies);
        xhr.onerror = () => onUploadError(fileId, "Network error");       
        xhr.send(fd);
    },

    /**
     * Called after a file is uploaded and server starts processing.
     * @param {Int} fileId - The id assigned to the file state from files
     * @param {Function} onProgress        - The function called to render updates of processing
     * @param {Function} onReady           - The function called when processing is finished
     * @param {Function} onProcessingError - The function called when something goes wrong
     * @returns 
     */
    subscribeProcessing(fileId, { onProgress, onReady, onProcessingError } )
    {
        console.log(fileId);
        // Create an absolute URL based on the current location and relative path
        const url = new URL(`./process/${fileId}`, window.location.href);
        url.protocol = url.protocol.replace(/^http/, 'ws');

        const ws = new WebSocket(url.href);
        ws.onmessage = e => {
            const msg = JSON.parse(e.data);

            if (msg.type === "error")
            {
                ws.close();
                onProcessingError(fileId, msg.message);
            }
            else if (msg.type === "done")
            {
                ws.close();
                onReady(files.find(f => fileId === f.name).id);
            }
            else if (msg.type === "status")
            {
                onProgress(fileId, msg.progress);
            }
        };

    return () => ws.close();
    },
};

/**
 * Generate new files as children of a parent file, replacing any existing files that should be tied to parent
 * @param {Int} parentId The id of the parent file from global "files"
 * @param {Array} childDefs List of Objects that partially define the child files
 */
function onChildrenResolved(parentId, childDefs)
{
    //  Get the actual parent object, exit early if missing
    const parent = files.find(f => f.id === parentId);
    if (!parent)
        return;

    //  For each child, create the new full file object
    const newChildren = childDefs.map(def => ({
        ...def,
        uploadedAt: Date.now(),
        uploadProgress: def.status === 'missing' ? 0 : 100,
        processingProgress: 0,
        selected: false,
        _cancel: null,
        parentId,
    }));

    //  If the files dont already exist, add them to the end of the files list
    newChildren.forEach(c => {
        if (!files.find(f => f.id === c.id))
            files.push(c);
    });
    //  Set child ids list of parent to match the new files
    parent.childIds = newChildren.map(c => c.id);
    //  If children are missing, open the expanded mode for parent
    parent.expanded = hasMissingChild(parent);
    //  Re-render file list to update based on new files
    render();
}

/**
 * Wrapper for setting up and managing the ServerAdapter for uploading
 * @param {File} f File object from global "files"
 * @returns {void}
 */
function _startUpload(f)
{
    ServerAdapter.subscribeUpload(f.file, f.id, {
        onProgress(id, pct) {
            const file = files.find(x => x.id === id); if (!file) return; // Get the actual file object based on id
            file.uploadProgress = pct;                                    // Set file's progress based on send result
            _patchBar(id, pct);                                           // Update the progress bar
        },
        onUploaded(id, dependancies) {
            const file = files.find(x => x.id === id); if (!file) return; // Get the actual file object based on id
            file.uploadProgress = 100;                                    // Set progress to 100%

            //  If the file has dependancies, mark them here
            if (dependancies == true)
            {
                file.dependancies
            }

            _transitionTo(file, 'waiting'); // Change file state 
        },
        onUploadError(id, msg) {
            const file = files.find(x => x.id === id); if (!file) return; // Get the actual file object based on id
            file.errorMsg = msg || 'Upload failed';                       // Set the error message
            _transitionTo(file, 'failed');                                // Change file state
        },
    });
}

/**
 * Wrapper for setting up and managing the ServerAdapter for processing
 * @param {Object | Int} f 
 * @return {void}
 */
function _startProcessing(f)
{
    //  If the passed "f" variable is not the actual object, get the object
    if (f.id == undefined)
        f = files.find(x => x.id === f)

    //  If the file is currently running something, cancel it
    if (f._cancel)
        f._cancel();

    //  Set up the server processing object as the current processing to be canceled by others
    f._cancel = ServerAdapter.subscribeProcessing(f.name, {
        onProgress(id, pct)
        {
            const file = files.find(x => x.id === id);if (!file) return; // Get the actual file object based on id
            file.processingProgress = pct;                               // Set file's progress based on send result
            _patchBar(id, pct);                                          // Update progress bar
        },
        onReady(id)
        {
            const file = files.find(x => x.id === id); if (!file) return; // Get the actual file object based on id
            file.processingProgress = 100;                                // Set the progress to 100%
            file._cancel = null;                                          // Remove cancel call from file
            _transitionTo(file, 'ready');                                 // Change file state
        },
        onProcessingError(id, msg)
        {
            const file = files.find(x => x.id === id); if (!file) return; // Get the actual file object based on id
            file.errorMsg = msg || 'Processing failed';                   // Set the error message
            file._cancel = null;                                          // Remove cancel call from file
            _transitionTo(file, 'failed');                                // Change file state
        },
    });
}

/*
//  Defunct simulation function
//  TODO: replace with actual logic to wait until the user manually starts processing
function _waitThenProcess(f)
{
    // Simulate waiting for a processing slot (~1-2 s).
    // In production: server will push a "slot_available" event instead.
    const delay = 1000 + Math.random() * 1000;
    const t = setTimeout(() => {
        if (f.status !== 'waiting')
            return; // cancelled / removed

        _transitionTo(f, 'processing');
        _startProcessing(f);

        // If this is a child, don't double-relay; parent relay handles siblings
        if (!f.parentId)
            _relayProcessingToChildren(f.id);
    }, delay);
    f._cancel = () => clearTimeout(t);
}*/

////////////////////////
//  Helper Functions  //
////////////////////////

/**
 * Extracts timestamp from filename like:
 * "2026-04-22 134523 image.png"
 * @argument {String} name the given file name
 * @returns {Number} returns epoch time 
 */
function parseDateFromFilename(name)
{
    const match = name.match(/^(\d{4}-\d{2}-\d{2}) (\d{6})/);
    if (!match) return null;

    const [_, datePart, timePart] = match;

    const year = datePart.slice(0, 4);
    const month = datePart.slice(5, 7);
    const day = datePart.slice(8, 10);

    const hours = timePart.slice(0, 2);
    const minutes = timePart.slice(2, 4);
    const seconds = timePart.slice(4, 6);

    // Construct ISO string (local time)
    const iso = `${year}-${month}-${day}T${hours}:${minutes}:${seconds}`;
    return new Date(iso).getTime();
}

/**
 * Looks at the content of the global "files" list and groups the files together by an appropriet metric
 * @returns {void}
 */
function regroupFilesByDate({ amount = 12, unit = 'hours' } = {}) {
    const unitToMs = {
        minutes:           60 * 1000,
        hours  :      60 * 60 * 1000,
        days   : 24 * 60 * 60 * 1000
    };

    const intervalMs = amount * unitToMs[unit];
    const buckets = {};

    for (const file of files)
        {
        const ts = parseDateFromFilename(file.name);
        if (ts === null) continue; // skip invalid format

        const bucketId = Math.floor(ts / intervalMs);
        const bucketStart = bucketId * intervalMs;

        if (!buckets[bucketId])
        {
            buckets[bucketId] = {
                start: new Date(bucketStart),
                end: new Date(bucketStart + intervalMs),
                files: []
            };
        }

        buckets[bucketId].files.push(file);
    }

    return buckets;
}

/**
 * Switches the variable data based on sort mode
 * @returns {void}
 */
function toggleSort()
{
    const btn = document.getElementById('sort-btn');
    const label = btn.childNodes[0];

    //  TODO: Change so that sorting methods arent hard coded
    if (sortMode === 'recent')
    {
        sortMode = 'az';
        label.textContent = 'Sort: Name A–Z ';
    }
    else if (sortMode === 'az')
    {
        sortMode = 'za';
        label.textContent = 'Sort: Name Z–A ';
    }
    else
    {
        sortMode = 'recent';
        label.textContent = 'Sort: Recently uploaded ';
    }
    render();
}

/**
 * Set up the deletion animation for removing a file
 * @param {Int} id 
 * @returns {void}
 */
function _removeId(id)
{
    //  Get all the actual file objects
    const f = files.find(f => f.id === id);
    //  If something is running on them cancel it
    if (f?._cancel)
        f._cancel();
    
    //  Get the elements associated with the file
    const row = document.getElementById(`row-${id}`);
    const barRow = document.getElementById(`prog-row-${id}`);
    
    //  Set css properties for the objects to let them smoothly exit
    if (row)
        row.classList.add('removing');
    if (barRow)
        barRow.style.opacity = '0';
}

/**
 * Helper to call _removeId on a list instead of individually
 * @param {Array} ids Int array of valid file ids
 * @returns {void}
 */
function _removeIds(ids)
{
    ids.forEach(id => _removeId(id));
    setTimeout(() => { files = files.filter(f => !ids.includes(f.id)); render(); }, 220);
}

/**
 *  Determines what buttons should be rendered for a given file
 *  @param {Object} f A file object from the global "files" list
 *  @returns {String} the HTML for the set of buttons
 */
function _actionHTML(f)
{
    if (f.status === 'missing')
        return `<button class="upload-missing-btn" onclick="event.stopPropagation();uploadMissing(${f.id})">Upload</button>`;
    if (f.status === 'failed')
        return `<div class="row-actions">
                    <button class="retry-btn"  onclick="event.stopPropagation();retryFile(${f.id})">Retry</button>
                    <button class="remove-btn" onclick="event.stopPropagation();removeFile(${f.id})">Remove</button>
                </div>`;
    if (f.status === 'waiting')
        return `<div class="row-actions">
            <button class="btn" onclick="event.stopPropagation();processFile(${f.id})">Process</button>
            <button class="remove-btn" onclick="event.stopPropagation();removeFile(${f.id})">Remove</button>
        </div>`;

    return `<button class="remove-btn" onclick="event.stopPropagation();removeFile(${f.id})">Remove</button>`
}

/**
 * Update progress bar
 * @param {Int} id file Id from a valid file object
 * @param {Int} pct Integer percentage of progress so far
 * @returns {void}
 */
function _patchBar(id, pct)
{
    const fill = document.getElementById(`prog-fill-${id}`);
    const label = document.getElementById(`prog-label-${id}`);
    if (fill)
        fill.style.width = pct + '%';
    if (label)
        label.textContent = pct + '%';
}

/**
 * Helper to get the right html for the checkbox object
 * Decides what class to use, and if an svg checkmark should be used
 * @param {Object} f A valid file object from global "files"
 * @returns {String} The html for the checkbox
 */
function cbHTML(f)
{
    return `<div class="row-checkbox ${f.selected ? 'checked' : ''}" onclick="toggleSelect(${f.id})">
        ${f.selected ? `<svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="white" stroke-width="2.5"><polyline points="2 6 5 9 10 3"/></svg>` : ''}
    </div>`;
}

/**
 * Changes a file objects status to match a new state
 * @param {Object} f A file object from the global "files" list
 * @param {String} newStatus The string key of the new status
 * @returns {void}
 */
function _transitionTo(f, newStatus)
{
    //  update file objects status to match
    f.status = newStatus;

    //  Get the current file row, exit early if currently hidden
    const row = document.getElementById(`row-${f.id}`);
    if (!row)
        return;

    //  Set the new status badge based on state
    const badgeEl = row.querySelector('.status-badge');
    if (badgeEl)
        badgeEl.outerHTML = _badgeHTML(f);

    //  Set the new action buttons based on state
    const lastCell = row.lastElementChild;
    lastCell.outerHTML = `<div>${_actionHTML(f)}</div>`;

    //  Remove any existing progress bar for this file
    const existingBar = document.getElementById(`prog-row-${f.id}`);
    if (existingBar)
        existingBar.remove();

    //  If the state should have a progress bar, add one back in
    if (newStatus === 'uploading' || newStatus === 'processing')
    {
        const barEl = document.createElement('div');
        barEl.className = 'progress-row';
        barEl.id = `prog-row-${f.id}`;

        //  Set progress based on internal file status
        const pct = newStatus === 'uploading' ? Math.round(f.uploadProgress) : Math.round(f.processingProgress);

        //  This makes sure the bar is always one of these two classes
        const barClass = newStatus === 'processing' ? 'processing' : 'uploading';

        barEl.innerHTML = `<div style="display:flex;align-items:center;margin-left:42px;">
            <div class="progress-wrap" style="flex:1;display:inline-block;">
                <div class="progress-fill ${barClass}" id="prog-fill-${f.id}" style="width:${pct}%"></div>
            </div>
            <span class="progress-label" id="prog-label-${f.id}">${pct}%</span>
        </div>`;

        //  Add this new bar after the file row
        const rowEl = document.getElementById(`row-${f.id}`);
        if (rowEl)
            rowEl.insertAdjacentElement('afterend', barEl);
    }

    //  Refresh checkbox after transition
    //      Since the file has been handled, the old reason for checking it is invalid
    const cb = row.querySelector('.row-checkbox');
    if (cb)
    {
        cb.style.opacity = '';
        cb.style.cursor = '';
        cb.onclick = () => toggleSelect(f.id);
    }

    //  Update the top details bar to reflect all changes
    updateDetails();
}

/**
 * Send processing command to file children
 * @param {Int} parentId The ID of the parent file object
 */
function relayProcessingToChildren(parentId)
{
    //  Get the actual file object from the global "files" list
    const parent = files.find(f => f.id === parentId);
    //  if no file, or it has no children, exit early
    if (!parent || !parent.childIds)
        return;

    //  Relay the processsing signal down to each of the child objects
    parent.childIds.forEach(cid => {
        const child = files.find(f => f.id === cid);
        if (child && child.status === 'waiting')
        {
            _transitionTo(child, 'processing');
            _startProcessing(child);
        }
    });
}

/** 
 * Construct the progress bar for a given file object, return empty if no bar needed
 * @param {Object} f File object from the global "files" list
 * @returns {String} The html for the progress bar
 */
function progressRowHTML(f)
{
    //  Should the file have a progress bar? if not, return empty
    const hasBar = (f.status === 'uploading' || f.status === 'processing') && f.status !== 'missing';
    if (!hasBar)
        return '';

    //  Get the progress value from the correct variable
    const pct = f.status === 'uploading' ? Math.round(f.uploadProgress) : Math.round(f.processingProgress);
    //  Make sure the bar class is always one of these two option
    const barClass = f.status === 'processing' ? 'processing' : 'uploading';
    //  Construct html for progress bar
    return `<div class="progress-row" id="prog-row-${f.id}">
        <div style="display:flex;align-items:center;margin-left:42px;">
            <div class="progress-wrap" style="flex:1;display:inline-block;">
                <div class="progress-fill ${barClass}" id="prog-fill-${f.id}" style="width:${pct}%"></div>
            </div>
            <span class="progress-label" id="prog-label-${f.id}">${pct}%</span>
        </div>
    </div>`;
}

/**
 * Check whether a file has children that are not uploaded
 * @param {Object} f file object from the global "files" list
 * @returns {boolean} True if file is missing children
 */
function hasMissingChild(f)
{
    //  If the file has no children, return false early
    if (!f.childIds)
        return false;

    //  If any of the children are missing, return true
    //      Otherwise false
    return f.childIds.some(cid => {
        const c = files.find(x => x.id === cid);
        return c && c.status === 'missing';
    });
}

/**
 *  Gives a human readable string for the time between a given time and now
 * @param {Number} ts The base time to be compared against
 * @returns {String} The human readable output for the time diffrence
 */
function timeAgo(ts)
{
    //  get time diffrence in seconds
    const s = Math.floor((Date.now() - ts) / 1000);
    
    //  If it is "recent" use words or seconds
    if (s < 10)
        return 'just now';
    if (s < 60)
        return `${s}s ago`;
    
    //  Longer than 1 min
    const m = Math.floor(s / 60);
    if (m < 60)
        return `${m}m ago`;

    //  Longer than 1 hour
    //      Realistically, no file should be older than a few hours since server would remove them
    const h = Math.floor(m / 60);
    return `${h}h ago`;
}

//////////////////////
//  Page Rendering  //
//////////////////////

/**
 * Keeps a parent objects progress consistent with the children
 * 
 */
function parentProgressUpdate(id)
{
    //  Get the actual object based on the file id.
    //      If files doesnt exist, exit early
    const f = files.find(f => f.id === id);
    if (!f)
        return;

    let childCount = f.childIds.length
    let statuses = Array(STATUS_LABELS.keys().length).fill(0);
    for (child_id of f.childIds)
    {
        const c = files.find(f => f.id === child_id);
        statuses[STATUS_LABELS.keys().findIndex(s => c.status === s)] += 1;
    }

    let final_status = "";
    let progress = 0;
    for (const [index, entry] of statuses.entries())
    {
        //  If all the children have the same state, theres no point in checking others
        if (entry === childCount)
        {
            final_status = STATUS_LABELS.keys()[entry];
            break;
        }
        
        switch (index)
        {
            case 0:
                final_status = "uploading"
                progress += entry;
                break;
            case 1:
                if (progress == 0)
                {
                    final_status = "waiting"
                }
                break;
            case 2:
                if (progress == 0)
                {
                    final_status = "processing"
                    progress += entry;
                }
                break;
            case 3:
                if (progress == 0)
                {
                    final_status = "ready"
                }
            case 4:
                final_status = "failed";
            case 5:
                final_status = "missing";
        }
    }

    //  Let Failed or missing options take priority over everything
    if (statuses[4] != 0)
    {
        return ("failed", 0);
    }
    if (statuses[5] != 0)
    {
        return ("missing", 0);
    }

    //  Next see if any are still being uploaded
    final_status = "uploading";
    progress = statuses[0];

    //  if it is being uploaded, exit early
    if (progress != 0)
    {
        return (final_status, progress / childCount)
    }

    progress = statuses[0];
}

/**
 * A dynamic popup to ask for comfirmation before deleting
 * @param {String} title The title to give the current popup 
 * @param {String} bodyHTML Additional content to be show. Must be valid html
 * @param {Object} actions A list of objects the user can pick from. Must be form of { label: 'Cancel', cls: 'secondary', fn: closeModal }
 */
function showRemovePopup(title, bodyHTML, actions)
{
    //  The pop up already exists on the page but is hidden until it is needed
    //      Set the internal content before enabling
    document.querySelector('.popup-title').textContent = title;
    document.getElementById('popup-body').innerHTML = bodyHTML;

    //  Get the popup objects
    const overlay = document.getElementById('remove-popup');
    const actionsEl = document.getElementById('popup-actions');

    //  Remove leftover actions, then fill in with the passed actions
    actionsEl.innerHTML = '';
    actions.forEach(({ label, cls, fn }) => {
        const btn = document.createElement('button');
        btn.className = `popup-btn ${cls}`;
        btn.textContent = label;
        btn.onclick = fn;
        actionsEl.appendChild(btn);
    });

    //  Make the popup visible
    overlay.classList.add('visible');
    
    //  Close on backdrop click
    overlay.onclick = e => {
        if (e.target === overlay)
            closePopup();
    };
}

/**
 * Helper function to close popup from anywhere
 * @returns {void}
 */
function closePopup()
{
    document.getElementById('remove-popup').classList.remove('visible');
}

/**
 * Sets the satus indicatior for each file row
 * @param {Object} f A file object from the global "files" list
 * @returns {String} The html span element for the status indicatior
 */
function _badgeHTML(f)
{
    const s = f.status;
    // If any child is missing, show warning badge instead
    if (hasMissingChild(f))
    {
        return `<span class="status-badge missing">Missing files</span>`;
    }
    //  If it is uploading or processing, an extra ui element is shown, the dot.
    const dot = (s === 'uploading' || s === 'processing') ? `<span class="status-dot"></span> ` : '';
    //  Construct the span to show the status label, use the status as a class, and display the human readable name for it
    return `<span class="status-badge ${s}">${dot}${STATUS_LABELS[s]}</span>`;
}

/**
 * Generates the html for a file row
 * @param {Object} f The file data used to construct the render
 * @param {Boolean} isChild Whether the given object is a child of another
 * @returns {String} The generated html
 */
function _rowHTML(f, isChild = false)
{
    const isParent = f.childIds && f.childIds.length > 0;
    //  Create class list for new row
    const classes = [
        'file-row',
        f.selected ? 'selected' : '',
        isParent ? 'is-parent' : '',
        isChild ? 'is-child' : '',
        (isChild && f.status === 'missing') ? 'missing-file' : '',
    ].filter(Boolean).join(' ');    //  Remove empty strings from class list

    //  Account for multiple ways to store jpeg's
    const iconLabel = f.type === 'jpeg' ? 'JPG' : f.type.toUpperCase();

    //  Add the dropdown button if file is a parent
    const childCount = isParent ? f.childIds.length : 0;
    const pillLabel = f.expanded ? 'Collapse' : (childCount + ' file' + (childCount !== 1 ? 's' : ''));
    const expandPill = isParent ?
        `<button class="expand-toggle ${(f.expanded ? 'open' : '')}" onclick="event.stopPropagation();toggleExpand(${f.id})">
            <svg width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="9 18 15 12 9 6"/></svg>
            <span class="toggle-label">${pillLabel}</span>
        </button>`
        : '';
    //  Enable click event for row if file is a parent
    const onclickAttr = isParent ? ' onclick="toggleExpand(' + f.id + ')"' : '';

    //  Construct Row
    const row = `<div class="${classes}" id="row-${f.id}"${onclickAttr}>
        ${cbHTML(f)}
        <div style="width:18px;flex-shrink:0;"></div>
        <div class="file-info">
            <div class="file-icon ${f.type}">${iconLabel}</div>
            <div class="file-details">
                <div class="file-name" title="${f.name}">${f.name}</div>
                <div class="file-date">${timeAgo(f.uploadedAt)}</div>
            </div>
            ${expandPill}
        </div>
        <div class="file-size">${f.size}</div>
        <div>${_badgeHTML(f)}</div>
        <div>${_actionHTML(f)}</div>
    </div>
    ${progressRowHTML(f)}`;

    //  If file is a parent, and the user has chosen to expand it, generate all the children as well
    if (isParent && f.expanded)
    {
        //  Get the original file objects for the children then generate based on those.
        const children = (f.childIds || []).map(cid => files.find(x => x.id === cid)).filter(Boolean);
        return row + children.map(c => _rowHTML(c, true)).join('');
    }

    return row;
}

/**
 * Switch a parent file between expanded states
 * @param {Int} id id of parent file in global "files" list
 * @returns {void}
 */
function toggleExpand(id)
{
    //  Get the actual object based on the file id.
    //      If files doesnt exist, exit early
    const f = files.find(f => f.id === id);
    if (!f)
        return;
    //  Flip the stored value
    f.expanded = !f.expanded;

    //  Get the row for the parent file
    const toggle = document.querySelector(`#row-${id} .expand-toggle`);
    if (toggle)
    {
        //  Change row css to match the state file 
        toggle.classList.toggle('open', f.expanded);
        const lbl = toggle.querySelector('.toggle-label');

        //  Set the text of row based on the number of files, and whether it is open or closed
        if (lbl)
            lbl.textContent = f.expanded ? 'Collapse' : `${(f.childIds || []).length} file${(f.childIds || []).length !== 1 ? 's' : ''}`;
    }

    //  If the file is expanded, render the children
    if (f.expanded)
    {
        // Insert child rows after parent's last element, progress bar or row itself
        const progRow = document.getElementById(`prog-row-${id}`);
        const anchor = progRow || document.getElementById(`row-${id}`);

        //  Get the actual file objects for all of the children
        const children = (f.childIds || []).map(cid => files.find(x => x.id === cid)).filter(Boolean);
        //  Generate the HTML for each child's row, put them all together, the insert first row into parent
        //      createRange() and createContextualFragment() are more efficient ways to modify the DOM
        //      idk really, I was having issues before and found something that said to try this
        const frag = document.createRange().createContextualFragment(children.map(c => _rowHTML(c, true)).join(''));
        anchor.after(frag); //  Add fragment to full dom
    }
    else    //  i.e. File is not expanded
    {
        // Remove child rows and their progress bars
        (f.childIds || []).forEach(cid => {
            const r = document.getElementById(`row-${cid}`);
            const b = document.getElementById(`prog-row-${cid}`);
            if (b)
                b.remove();
            if (r)
                r.remove();
        });
    }
}

/**
 * Update various details pieces around the file list
 * @returns {void}
 */
function updateDetails()
{
    //  Create filters for the selected files, and the non-child files
    const selectedCount = files.filter(f => f.selected).length;
    const topLevel = files.filter(f => !f.parentId);

    //  Update the total file count
    document.getElementById('file-count').innerHTML = `<strong>${topLevel.length}</strong> file${topLevel.length !== 1 ? 's' : ''}`;
    //  Update the selected file count
    document.getElementById('selected-info').innerHTML = selectedCount > 0
        ? `<strong>${selectedCount}</strong> file${selectedCount !== 1 ? 's' : ''} selected`
        : '0 files selected';
    //  Toggle the visibility of selection controls, depending on if any selected
    document.getElementById('bulk-remove-btn').classList.toggle('visible', selectedCount > 0);
    document.getElementById('bulk-reprocess-btn').classList.toggle('visible', selectedCount > 0);

    //  Change the look of the "select all" checkbox to match the actual state
    const cb = document.getElementById('select-all-cb');
    const ready = files;
    const allSel = ready.length > 0 && ready.every(f => f.selected);
    const someSel = ready.some(f => f.selected);
    cb.className = allSel ? 'checked' : someSel ? 'indeterminate' : '';
    cb.innerHTML = allSel
        ? `<svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="white" stroke-width="2.5"><polyline points="2 6 5 9 10 3"/></svg>`
        : someSel
            ? `<svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="white" stroke-width="2.5"><line x1="2" y1="6" x2="10" y2="6"/></svg>`
            : '';
}

/**
 * Filters and sorts the user added files based on certain criteria
 * @returns {Array} The sorted, filter file list
 */
function getFiltered()
{
    //  Remove any child nodes from the final list
    let list = files.filter(f => !f.parentId);

    //  Filter based on search parameters first
    if (searchQuery)
    {
        const q = searchQuery.toLowerCase();
        list = list.filter(f => {
            if (f.name.toLowerCase().includes(q))
                return true;

            // Keep parent if any child matches
            if (f.childIds)
                return f.childIds.some(cid => {
                    const c = files.find(x => x.id === cid);
                    return c && c.name.toLowerCase().includes(q);
                });
            return false;
        });
    }

    //  Decide how to sort the files
    if (sortMode === 'az')
        list.sort((a, b) => a.name.localeCompare(b.name));
    else if (sortMode === 'za')
        list.sort((a, b) => b.name.localeCompare(a.name));
    return list;
}

/**
 * Updates the page with the current file list
 * @returns {void}
 */
function render()
{
    //  Update surrounding details
    updateDetails();

    //  Filter elements based on user set criteria
    const filtered = getFiltered();
    const tbody = document.getElementById('table-body');

    //  If there are no files present, give the reason instead of rending rows
    if (filtered.length === 0)
    {
        tbody.innerHTML = `
        <div class="empty-state">
            <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
            <p>${searchQuery ? 'No files match your search.' : 'No files yet — drop some above!'}</p>
        </div>`;
        return;
    }

    //  Otherwise we render each row.
    tbody.innerHTML = filtered.map(f => _rowHTML(f)).join('');
}

///////////////////////
//  Button Handling  //
///////////////////////

/**
 * Ran on button click
 *  Enable selection flag on all file objects
 * @returns {void}
 */
function toggleSelectAll()
{
    const ready = files;
    const allSel = ready.every(f => f.selected);  //    Are all files selected? 

    //  If all files already selected, unselect all
    //  otherwise make sure everything is selected
    ready.forEach(f => f.selected = !allSel);

    //  For each file 
    ready.forEach(f => {
        //  Get the file row, exit early on failure
        const row = document.getElementById(`row-${f.id}`);
        if (!row)
            return;

        //  Change row CSS to match the selection state
        row.classList.toggle('selected', f.selected);
        //  Change the checkbox to match the selection state
        const cb = row.querySelector('.row-checkbox');
        if (cb)
        {
            cb.classList.toggle('checked', f.selected);
            cb.innerHTML = f.selected
                ? `<svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="white" stroke-width="2.5"><polyline points="2 6 5 9 10 3"/></svg>` // Checkmark
                : '';
        }
    });
    //  Re-render detail menu with new states
    updateDetails();
}

/**
 * Ran on button click
 *  Changes the state of a files selection status, and updates styling to match
 * @param {Int} id Id of the file from the global "files" list
 * @returns {void}
 */
function toggleSelect(id)
{
    //  Get the file object associated with the id, if it doesnt exist return early
    const f = files.find(f => f.id === id);
    if (!f)
        return;

    //  toggle selection state
    f.selected = !f.selected;

    //  If the file has a currently active row, force details to match
    const row = document.getElementById(`row-${id}`);
    if (row)
    {
        //  Change row CSS to match the selection state
        row.classList.toggle('selected', f.selected);
        //  Change the checkbox to match the selection state
        const cb = row.querySelector('.row-checkbox');
        if (cb)
        {
            cb.classList.toggle('checked', f.selected);
            cb.innerHTML = f.selected
                ? `<svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke="white" stroke-width="2.5"><polyline points="2 6 5 9 10 3"/></svg>` // Checkmark
                : '';
        }
    }
    //  Change main details bar to match new states
    updateDetails();
}

/**
 * Ran on button click,
 *  Send process signal to server for all the selected files
 * @returns {void}
 */
function processSelected()
{
    //  Get all the files currently selected. if none selected return
    const targets = files.filter(f => f.selected);
    if (!targets.length) 
        return;

    targets.forEach(f => {
        f.selected = false;
        processFile(f.id);
    });
    render();
    showToast(`Processing ${targets.length} file${targets.length > 1 ? 's' : ''}…`);
}

/**
 * Ran on button click,
 *  Remove the selected fiels from the list of files, send delete signal to server
 * @returns {void}
 */
function removeSelected()
{
    const ids = files.filter(f => f.selected).map(f => f.id);   //  Get the ds of all the selected files.
    _removeIds(ids)                                           //  Remove selected files based on ids
    showToast(`${ids.length} file${ids.length > 1 ? 's' : ''} removed`);
}

/**
 * Function ran when a CSV parent is missing child files
 * @param {Int} id Id of the placeholder objects file
 * @returns
 */
function uploadMissing(id)
{    
    //  Create a hidden file input form
    const picker = document.createElement('input');
    picker.type = 'file';
    picker.accept = '.mp4,.mov,.jpg,.jpeg,.png,.webm,.csv';

    //  Code that runs once file is submited
    picker.onchange = () => {
        
        //  Get entered file, exiting if there is none
        const file = picker.files[0];
        if (!file)
            return;

        //  Get the existing placholder file id, if it doesnt exist fail
        const f = files.find(f => f.id === id);
        if (!f)
            return;

        //  Fill in the missing placeholder information, based on new file object
        const kb = file.size / 1024;
        f.name = file.name;
        f.size = kb < 1024 ? `${Math.round(kb)} KB` : `${(kb / 1024).toFixed(1)} MB`;
        f.uploadedAt = Date.now();
        f.uploadProgress = 0;
        f.processingProgress = 0;
        
        //  Start upload to server
        _transitionTo(f, 'uploading');
        _startUpload(f);
        
        // Check if parent should now collapse (no more missing children)
        const parent = f.parentId ? files.find(p => p.id === f.parentId) : null;
        if (parent && !hasMissingChild(parent))
        {
            parent.expanded = false;
            render();   //  refresh renderer
        }
        showToast(`Uploading ${file.name}…`);
    };

    //  Force a click onto the hidden input to create dialog
    picker.click();
}

/**
 * Function ran when a single file is sent to be processed
 * @param {Int} id Id of the file from the global "files" list
 * @param {void}
 */
function processFile(id)
{
    //  Find the actual file object from global "files" list
    const f = files.find(f => f.id === id);

    //  If the file has something running, call the specific cancel function
    if (f._cancel)
    {
        f._cancel();
        f._cancel = null;
    }

    //  Reset the progress variables and clear exisitng errors
    f.processingProgress = 0;
    delete f.errorMsg;

    //  Start processing
    _transitionTo(f, 'processing');
    _startProcessing(f);
}

/**
 * Button handler for the Retry File Download
 * @param {Int} id The local file id 
 * @returns 
 */
function retryFile(id)
{
    //  Get the file object from the id
    const f = files.find(f => f.id === id);
    if (!f)
        return;

    //  If the file has something running, call the specific cancel function
    if (f._cancel)
    {
        f._cancel();
        f._cancel = null;
    }

    //  Reset progress values and remove existing errors
    f.uploadProgress = 0;
    f.processingProgress = 0;
    delete f.errorMsg;
    
    //  Try and upload again
    _transitionTo(f, 'uploading');
    _startUpload(f);
    showToast('Retrying…');
}

/**
 * Called after the dialog menu for adding a file
 * @param {FileList} fileList - The returned file list from a file dialog
 * @returns 
 */
function addFiles(fileList)
{
    const arr = Array.from(fileList);
    const validFiles = [];
    
    arr.forEach(file => {
        //  Check valid type, otherwise exit with error
        const ext = file.name.split('.').pop().toLowerCase();
        const type = ['mp4', 'mov', 'jpg', 'jpeg', 'png', 'webm', 'gif', 'csv'].includes(ext) ? ext : null;
        if (type == null) return;   //  TODO: Add proper error message

        //  Calculate filesize for display
        const kb = file.size / 1024;
        const sizeStr = kb < 1024 ? `${Math.round(kb)} KB` : `${(kb / 1024).toFixed(1)} MB`;

        //  Create the file dictionary and save to global list
        const id = nextId++;
        newFileIds.add(id);
        const f = {
            id, name: file.name, size: sizeStr, uploadedAt: Date.now(), type,
            status: 'uploading', uploadProgress: 0, processingProgress: 0,
            selected: false, _cancel: null, file: file
        };
        validFiles.push(f);
        _startUpload(f); //  TODO: Change to providing an upload button and waiting until user clicks it
    });
    
    let addedCount = 0;
    const ungroupable = validFiles.filter(f => parseDateFromFilename(f.name) === null);
    ungroupable.forEach(f => {
        newFileIds.add(f.id);
        files.unshift(f);
        _startUpload(f);
        addedCount++;
    });

    const groupable = validFiles.filter(f => parseDateFromFilename(f.name) !== null);
    const snapshot = files;
    files = [...snapshot, ...groupable];
    const buckets = regroupFilesByDate();
    files = snapshot;

    Object.values(buckets).forEach(bucket => {
        //  Only act on files that came from this batch
        const bucketNewFiles = bucket.files.filter(bf => groupable.find(vf => vf.id === bf.id));
        if (bucketNewFiles.length === 0) return;

        if (bucketNewFiles.length === 1)
        {
            //  Single file in bucket add it directly, no parent needed
            const f = bucketNewFiles[0];
            newFileIds.add(f.id);
            files.unshift(f);
            _startUpload(f);
            addedCount++;
        }
        else
        {
            //  Multiple files share a bucket so create a parent entry to group them
            const parentId = nextId++;
            const bucketStart = bucket.start;

            const pad     = n => String(n).padStart(2, '0');
            const dateStr = `${bucketStart.getFullYear()}-${pad(bucketStart.getMonth() + 1)}-${pad(bucketStart.getDate())}`;
            const timeStr = `${pad(bucketStart.getHours())}${pad(bucketStart.getMinutes())}${pad(bucketStart.getSeconds())}`;
            const parentName = `${dateStr} ${timeStr} batch`;

            const totalKb = bucketNewFiles.reduce((sum, f) => {
                const raw = f.size.includes('MB')
                    ? parseFloat(f.size) * 1024
                    : parseFloat(f.size);
                return sum + raw;
            }, 0);
            const parentSize = totalKb < 1024
                ? `${Math.round(totalKb)} KB`
                : `${(totalKb / 1024).toFixed(1)} MB`;

            const parent = {
                id: parentId,
                name: parentName,
                size: parentSize,
                uploadedAt: Date.now(),
                type: 'csv',
                status: 'uploading',
                uploadProgress: 0,
                processingProgress: 0,
                selected: false,
                _cancel: null,
                childIds: bucketNewFiles.map(f => f.id),
                expanded: false,
            };

            bucketNewFiles.forEach(f => {
                f.parentId = parentId;
                newFileIds.add(f.id);
                files.unshift(f);
                _startUpload(f);
            });

            newFileIds.add(parentId);
            files.unshift(parent);
            addedCount++;
        }
    });

    //  Update the page to reflect new files
    render();
    newFileIds.forEach(id => {
        const row = document.getElementById(`row-${id}`);
        if (row)
            row.classList.add('row-new');
    });
    newFileIds.clear();

    if (addedCount > 0)
        showToast(`${addedCount} file${addedCount !== 1 ? 's' : ''} added`);
}

/**
 * Ran on button click,
 *  Removes a file from the global array based on the id
 * @param {Int} id
 * @returns {void}
 */
function removeFile(id)
{
    //  Get the actual file object based on ID, if invalid exit
    const f = files.find(f => f.id === id);
    if (!f)
        return;

    //  Get a list of all of the children the object has
    //      but only if the children are already uploaded.
    //  List of actual child objects, not just ids
    const uploadedChildren = (f.childIds || [])
        .map(cid => files.find(x => x.id === cid))
        .filter(c => c && c.status !== 'missing');

    //  If there were valid children, show the option dialog,
    //      Lets user cancel, Remove only the parent, or remove all.
    if (uploadedChildren.length > 0)
    {
        showRemovePopup(
            'Remove files',
            `Also remove the <strong>${uploadedChildren.length} child file${uploadedChildren.length !== 1 ? 's' : ''}</strong> associated with <strong>${f.name}</strong>?`
                + '<ul class="modal-child-list">'
                + uploadedChildren.map(c => {
                    const lbl = c.type === 'jpeg' ? 'JPG' : c.type.toUpperCase();
                    return `<li><span class="file-icon ${c.type}">${lbl}</span>${c.name}</li>`;
                }).join('')
                + '</ul>',
            [
                { label: 'Cancel', cls: 'secondary', fn: closeModal },
                { label: 'Remove parent only', cls: 'secondary', fn: () => {
                    closeModal();                                       //  Close popup
                    uploadedChildren.forEach(c => delete c.parentId);   //  Unlink the children from parent
                    _removeIds([id]);                                 //  Remove parent
                    showToast('File removed');
                }},
                { label: 'Remove all', cls: 'danger', fn: () => {
                    closeModal();                                               //  Close the popup
                    _removeIds([id, ...uploadedChildren.map(c => c.id)]);     //  Remove all files including children
                    showToast(`${1 + uploadedChildren.length} files removed`);
                } },
            ]
        );
        return;
    }
    //  Else

    //  Remove the file
    _removeIds([id]);
    showToast('File removed');
}

/**
 * Called on page load to make sure the current file list is accurate to the session
 * TODO: Better comments
 */
function pullFromSource()
{
    const xhr = new XMLHttpRequest();
    xhr.open('GET', '/api/getUploads', true);
    xhr.responseType = 'json';

    xhr.onload = function()
    {
        if (xhr.status === 200)
        {
            const response = xhr.response;

            if (response && Array.isArray(response.files))
            {
                files = response.files.map(fileStr => {
                    try
                    {                        
                        return fileStr;
                    } catch (e) {
                        console.error("Invalid JSON string:", fileStr);
                        return null;
                    }
                }).filter(f => f !== null);
            }

            console.log(files);
            render();
        }
    };

    xhr.send();
}

/**
 * Called on page close to make sure the current file list is stored on the server
 */
function pushToSource()
{
    fetch('/api/saveUploads',{
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(files)
    })
    .then(res => res.json())
    .then(data => console.log(data));
}


// Set up events for drag and drop
const dropZone  = document.getElementById('drop-zone' );
const fileInput = document.getElementById('file-input');

dropZone.addEventListener('click', () => fileInput.click());
dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
});
dropZone.addEventListener('dragleave', e => {
    if (!dropZone.contains(e.relatedTarget))
        dropZone.classList.remove('drag-over');
});
dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    addFiles(e.dataTransfer.files);
});
fileInput.addEventListener('change', e => {
     addFiles(e.target.files);
     fileInput.value = '';
});

//  Set event for typing into search bar
document.getElementById('search-input').addEventListener('input', e => {
    searchQuery = e.target.value;   //  Update global variable for other functions
    render();                       //  Re-render page to filter results based on search
});

pullFromSource();

//  Initialize the empty file list.
render();

//  When the user leaves the file page, a message gets sent to the server containing the current state of the 
//  global files menu
window.addEventListener('beforeunload', () => {
    const payload = JSON.stringify(files);
    navigator.sendBeacon('/api/saveUploads', new Blob([payload], { type: 'application/json' }));
});

//  Every 15 seconds, update the time since uploaded for each file
setInterval(() => {
    files.forEach(f => {
        const el = document.querySelector(`#row-${f.id} .file-date`);
        if (el)
            el.textContent = timeAgo(f.uploadedAt);
    });
}, 15000);

let toastTimer;
/**
 * Displays a small message at the bottom of the screen to show process was complete
 * @param {String} message - The message to be printed out
 * @returns 
 */
function showToast(message)
{
    const t = document.getElementById('toast');
    t.textContent = message;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
}