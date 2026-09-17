document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.planning-tab').forEach(button => {
    button.addEventListener('click', () => setPlanningView(button.dataset.view));
  });
  document.querySelector('#new-swim-draft').addEventListener('click', openSwimDraft);
  document.querySelector('#new-swim-plan').addEventListener('click', () => openSwimPlan());
  document.querySelector('#new-cycling-draft').addEventListener('click', openCyclingDraft);
  document.querySelector('#new-cycling-plan').addEventListener('click', () => openCyclingPlan());
  const sessions = document.querySelector('#coach-sessions');
  const swimming = document.querySelector('#coach-swimming-sessions');
  const cycling = document.querySelector('#coach-cycling-sessions');
  const syncSwimmingLimit = () => {
    swimming.max = sessions.value;
    cycling.max = sessions.value;
    if (Number(swimming.value) > Number(sessions.value)) swimming.value = sessions.value;
    if (Number(cycling.value) > Number(sessions.value)) cycling.value = sessions.value;
  };
  sessions.addEventListener('input', syncSwimmingLimit);
  syncSwimmingLimit();

  const originalOpenPlan = openPlan;
  window.openPlan = (plan = null, date = null, sport = null) => {
    originalOpenPlan(plan, date);
    const selectedSport = sport || planningView;
    if (!plan && selectedSport === 'swimming') {
      document.querySelector('#plan-title').textContent = 'Programma nuoto';
      document.querySelector('#plan-sport').value = 'swimming';
    } else if (!plan && selectedSport === 'cycling') {
      document.querySelector('#plan-title').textContent = 'Programma ciclismo';
      document.querySelector('#plan-sport').value = 'cycling';
    }
  };
});
