const modal_backdrop = document.getElementsByClassName('modal-backdrop')[0];
const config_menu    = document.getElementsByClassName('config-menu'   )[0];

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
