const modal_backdrop = document.getElementsByClassName('modal-backdrop')[0];
const config_menu    = document.getElementsByClassName('config-menu'   )[0];
const slider         = document.getElementById('amountSlider');
const unitSelect     = document.getElementById('timeUnit');

function openConfigMenu()
{
    modal_backdrop.classList.remove('hidden');
    config_menu.classList.remove('hidden');
}

function closeConfigMenu()
{
    modal_backdrop.classList.add('hidden');
    config_menu.classList.add('hidden');
}

modal_backdrop.addEventListener('click', (e) => {
  if (e.target === modal_backdrop) {
    closeConfigMenu();
  }
});

//  Modify the max time units for the setting slider
unitSelect.addEventListener('change', () => {
    const limits = {
        minutes: 60,
        hours: 24,
        days: 31,
        weeks: 4,
        months: 12,
        years: 10
    };

    slider.max = limits[unitSelect.value];
    if (slider.value > slider.max) slider.value = slider.max;
    document.getElementById('amountValue').innerText = slider.value;
});