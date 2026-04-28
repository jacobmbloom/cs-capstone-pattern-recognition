/**
 * A dynamic popup to ask for comfirmation before deleting
 * @param {String} title The title to give the current popup 
 * @param {String} bodyHTML Additional content to be show. Must be valid html
 * @param {Object} actions A list of objects the user can pick from. Must be form of { label: 'Cancel', cls: 'secondary', fn: closePopup }
 */
function showPopup(title, bodyHTML, actions)
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

function showSettingsPopup()
{
    showPopup(
        'Detection Settings',
        `<fieldset>
            <legend>Choose what classes are enabled:</legend>
            <div class="popup-check-item"><input type="checkbox" id="SEDAN" name="classes[]" value="SEDAN" checked><label for="SEDAN">Sedan</label></div>
            <div class="popup-check-item"><input type="checkbox" id="SEMI" name="classes[]" value="SEMI" checked><label for="SEMI">Semi</label></div>
            <div class="popup-check-item"><input type="checkbox" id="SUV" name="classes[]" value="SUV" checked><label for="SUV">SUV</label></div>
            <div class="popup-check-item"><input type="checkbox" id="TRUCK" name="classes[]" value="TRUCK" checked><label for="TRUCK">Truck</label></div>   
            <div class="popup-check-item"><input type="checkbox" id="VAN" name="classes[]" value="VAN" checked><label for="VAN">Van</label></div>
        </fieldset>`,
        [
            { label: 'Cancel', cls: 'secondary', fn: closePopup },
            { label: 'Save', cls: '', fn: () => {
                const data = new FormData();
                document.querySelectorAll('input[name="classes[]"]:checked').forEach(cb => data.append('classes[]', cb.value));
                data.append('time', document.getElementById('time').value);
                fetch('/settingChange', { method: 'POST', body: data })
                    .then(() => closePopup());
            }},
        ]
    );
}

function showExportPopup()
{
    showPopup(
        'Export as CSV',
        `Are you sure you want to export the current file list as a <strong>.csv</strong> file?`,
        [
            { label: 'Cancel', cls: 'secondary', fn: closePopup },
            { label: 'Download', cls: '', fn: () => {
                closePopup();
                window.location.href = '/api/export';
            }},
        ]
    );
}