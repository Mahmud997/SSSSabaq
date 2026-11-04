// Этап 7: планирование и оценивание — КТП, СОР, СОЧ, диагностика, планы
const PLAN_HOURS = {ktp: 8, theme_plan: 8, year_plan: 68, sor: 1, soch: 1, diagnostic: 1};

function syncPlanningHours(){
  const k=$("#planning-kind").value;
  const inp=$("#planning-hours");
  if(!inp)return;
  if(PLAN_HOURS[k]!=null)inp.value=PLAN_HOURS[k];
  const wrap=inp.closest("label");
  if(wrap)wrap.classList.toggle("hidden", k==="sor"||k==="soch"||k==="diagnostic");
}
function fillPlanningLessons(){
  const sel=$("#planning-lesson"); if(!sel)return;
  const cur=sel.value;
  sel.innerHTML='<option value="">— без привязки —</option>'+(state.lessons||[])
    .filter(l=>{
      const d=l.content&&l.content.doc_type;
      return !d||d==="ksp"||d==="theme_plan"||d==="ktp";
    })
    .map(l=>`<option value="${l.id}">${esc(l.title)}</option>`).join("");
  sel.value=cur;
}
$("#planning-kind")&&$("#planning-kind").addEventListener("change",syncPlanningHours);
document.querySelector('[data-view="planning"]')&&document.querySelector('[data-view="planning"]').addEventListener("click",()=>{fillPlanningLessons();syncPlanningHours()});
document.querySelectorAll('[data-go="planning"]').forEach(b=>b.addEventListener("click",()=>{fillPlanningLessons();syncPlanningHours()}));
$("#planning-lesson")&&$("#planning-lesson").addEventListener("change",e=>{
  const l=(state.lessons||[]).find(x=>x.id===e.target.value); if(!l)return;
  const f=$("#planning-form");
  f.subject.value=l.subject; f.grade.value=l.grade; f.topic.value=l.topic;
  if(l.content&&l.content.room_conditions)f.room_conditions.value=l.content.room_conditions;
});
$("#planning-form")&&$("#planning-form").addEventListener("submit",async e=>{
  e.preventDefault();
  if(!state.key){toast("Сначала заполните профиль учителя");$("#profile-gate").classList.remove("hidden");return}
  const f=new FormData(e.target), payload={};
  f.forEach((v,k)=>{payload[k]=v});
  payload.hours=+payload.hours||8;
  if(!payload.lesson_id)delete payload.lesson_id;
  const btn=$("#planning-run"); btn.disabled=true; btn.textContent="Генерация…";
  try{
    const d=await api("/api/planning/generate",{method:"POST",body:JSON.stringify(payload)});
    await loadLessons(); toast("Документ создан и сохранён");
    view("lesson"); await openEditor(d.id);
  }catch(err){toast(err.message)}
  finally{btn.disabled=false; btn.textContent="Создать с AI"}
});
syncPlanningHours();
