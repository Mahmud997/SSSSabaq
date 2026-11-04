// Методический конструктор: форма создания материала и переход в редактор.
const BUILDER_COUNT={cards:"Количество карточек",test:"Количество вопросов",rubric:"Количество критериев"};
function syncBuilder(){
  const k=$("#builder-kind").value;
  $("#builder-count-wrap").classList.toggle("hidden",!BUILDER_COUNT[k]);
  $("#builder-format-wrap").classList.toggle("hidden",k!=="test");
  if(BUILDER_COUNT[k]){$("#builder-count-label").textContent=BUILDER_COUNT[k];$("#builder-form [name=count]").value={cards:6,test:5,rubric:4}[k]}
}
function fillBuilderLessons(){
  const sel=$("#builder-lesson"),cur=sel.value;
  sel.innerHTML='<option value="">— без привязки —</option>'+(state.lessons||[]).filter(l=>!l.content||!l.content.doc_type||l.content.doc_type==="ksp")
    .map(l=>`<option value="${l.id}">${esc(l.title)}</option>`).join("");
  sel.value=cur;
}
$("#builder-kind").addEventListener("change",syncBuilder);
$("#builder-lesson").addEventListener("change",e=>{
  const l=(state.lessons||[]).find(x=>x.id===e.target.value);if(!l)return;
  const f=$("#builder-form");f.subject.value=l.subject;f.grade.value=l.grade;f.topic.value=l.topic;
  if(l.content&&l.content.room_conditions)f.room_conditions.value=l.content.room_conditions;
});
document.querySelector('[data-view="builder"]').addEventListener("click",fillBuilderLessons);
document.querySelectorAll('[data-go="builder"]').forEach(b=>b.addEventListener("click",fillBuilderLessons));
$("#builder-form").addEventListener("submit",async e=>{
  e.preventDefault();
  if(!state.key){toast("Сначала заполните профиль учителя");$("#profile-gate").classList.remove("hidden");return}
  const f=new FormData(e.target),payload={};
  f.forEach((v,k)=>{payload[k]=v});
  payload.count=+payload.count||6;if(!payload.lesson_id)delete payload.lesson_id;
  const btn=$("#builder-run");btn.disabled=true;btn.textContent="Генерация…";
  try{
    const d=await api("/api/materials/generate",{method:"POST",body:JSON.stringify(payload)});
    await loadLessons();toast("Материал создан и сохранён");view("lesson");await openEditor(d.id);
  }catch(err){toast(err.message)}finally{btn.disabled=false;btn.textContent="Создать материал с AI"}
});
syncBuilder();
