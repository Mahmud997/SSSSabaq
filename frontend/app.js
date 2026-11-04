const $ = (s)=>document.querySelector(s);
const DOC_LABELS={ksp:"КСП / КМЖ",tasks_abc:"Задания A / B / C",cards:"Карточки",worksheet:"Рабочий лист",test:"Тест с ключом",rubric:"Рубрика и дескрипторы",presentation:"Презентация",ktp:"КТП",sor:"СОР",soch:"СОЧ",diagnostic:"Диагностика",year_plan:"Годовой план",theme_plan:"Тематический план"};
const state={key:"",workspaceId:"",lessons:[]};
function toast(msg){const el=$("#toast");el.textContent=msg;el.classList.add("show");setTimeout(()=>el.classList.remove("show"),2600)}
async function api(path,opts={}){const headers={"Content-Type":"application/json",...(opts.headers||{})};if(state.key)headers["X-Workspace-Key"]=state.key;const r=await fetch(path,{...opts,headers});const data=await r.json().catch(()=>({}));if(!r.ok){const d=data.detail;const msg=Array.isArray(d)?d.map(x=>x.msg||JSON.stringify(x)).join("; "):(typeof d==="string"?d:(d&&typeof d==="object"?JSON.stringify(d):"Ошибка запроса"));throw new Error(msg)}return data}
function view(name){document.querySelectorAll(".view").forEach(x=>x.classList.add("hidden"));$("#"+name+"-view").classList.remove("hidden");document.querySelectorAll(".nav").forEach(x=>x.classList.toggle("active",x.dataset.view===name));const titles={builder:"Конструктор материалов",presentation:"Презентации",planning:"Планирование и оценивание",home:"Добро пожаловать в USTAZ AI",lesson:"Конструктор урока",library:"Общая библиотека",admin:"Администрирование"};$("#page-title").textContent=titles[name]||"USTAZ AI"}
document.querySelectorAll("[data-view]").forEach(b=>b.addEventListener("click",()=>view(b.dataset.view)));
document.querySelectorAll("[data-go]").forEach(b=>b.addEventListener("click",()=>view(b.dataset.go)));
function profileGate(){ $("#profile-gate").classList.toggle("hidden",!!state.key); $("#workspace-status").textContent=state.key?"Активно":"Не создано"; }
$("#profile-form").addEventListener("submit",async e=>{e.preventDefault();const f=new FormData(e.target);const payload={teacher_name:f.get("teacher_name"),school_name:f.get("school_name"),locality:f.get("locality"),subjects:f.get("subjects").split(",").map(x=>x.trim()).filter(Boolean)};try{const d=await api("/api/workspaces",{method:"POST",body:JSON.stringify(payload)});state.key=d.workspace_key;state.workspaceId=d.workspace_id;await (window.ustazStorage?ustazStorage.saveWorkspaceCredentials(state.key,state.workspaceId):Promise.resolve());alert("Сохраните ключ рабочего пространства в надёжном месте:\n\n"+state.key+"\n\nОн не восстанавливается сервером в открытом виде.");profileGate();await loadLessons();toast("Рабочее пространство создано");}catch(err){toast(err.message)}});
$("#lesson-form").addEventListener("submit",async e=>{e.preventDefault();if(!state.key){toast("Сначала заполните профиль учителя");$("#profile-gate").classList.remove("hidden");return}const f=new FormData(e.target);const content={notes:f.get("content")||""};try{await api("/api/lessons",{method:"POST",body:JSON.stringify({title:f.get("title"),subject:f.get("subject"),grade:f.get("grade"),topic:f.get("topic"),content})});e.target.reset();await loadLessons();toast("Личный материал сохранён");}catch(err){toast(err.message)}});
async function loadLessons(){if(!state.key)return;try{state.lessons=await api("/api/lessons");$("#my-lessons").textContent=state.lessons.length;$("#lesson-results").innerHTML=state.lessons.map(l=>`<article class="item"><h3>${esc(l.title)} <span class="mod-badge extra">${esc(DOC_LABELS[(l.content&&l.content.doc_type)||"ksp"]||"КСП / КМЖ")}</span></h3><p>${esc(l.subject)} · ${esc(l.grade)} · ${esc(l.topic)}</p><div class="actions"><button class="primary" data-edit="${l.id}">Открыть редактор</button><button class="secondary" data-publish="${l.id}">Опубликовать обезличенную копию</button></div></article>`).join("");document.querySelectorAll("[data-publish]").forEach(b=>b.addEventListener("click",()=>publish(b.dataset.publish)));document.querySelectorAll("[data-edit]").forEach(b=>b.addEventListener("click",()=>{
  const id=b.dataset.edit; const item=(state.lessons||[]).find(x=>x.id===id);
  const dt=item&&item.content&&item.content.doc_type;
  if(dt==="presentation"&&typeof openPresentationEditor==="function"){view("presentation");openPresentationEditor(id)}
  else openEditor(id);
}));}catch(e){toast(e.message)}}
function esc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
async function publish(id){if(!confirm("Будет создана отдельная копия для общей библиотеки. Проверьте, что в содержании нет персональных данных. Продолжить?"))return;try{await api(`/api/lessons/${id}/publish`,{method:"POST",body:JSON.stringify({confirm_anonymized:true})});toast("Копия отправлена в библиотеку");}catch(e){toast(e.message)}}
async function loadLibrary(){try{const rows=await api("/api/library");$("#public-count").textContent=rows.length;$("#library-list").innerHTML=rows.map(x=>`<article class="item"><h3>${esc(x.title)}</h3><p>${esc(x.public_subject||x.subject)} · ${esc(x.public_grade||x.grade)} · ${esc(x.public_topic||x.topic)}</p>${libBody(x)}</article>`).join("")||'<article class="item">Пока нет опубликованных материалов.</article>';}catch(e){toast(e.message)}}
$("#refresh-library").addEventListener("click",loadLibrary);


(async function boot(){
  try{
    if(window.ustazStorage){
      const c=await ustazStorage.loadWorkspaceCredentials();
      state.key=c.key||""; state.workspaceId=c.workspaceId||"";
    }
  }catch(e){}
  profileGate(); loadLessons(); loadLibrary();
})();

$("#generate-ai").addEventListener("click",async()=>{
  if(!state.key){toast("Сначала заполните профиль учителя");$("#profile-gate").classList.remove("hidden");return}
  const f=new FormData($("#lesson-form"));
  const payload={subject:f.get("subject"),grade:f.get("grade"),topic:f.get("topic"),
    room_conditions:f.get("room_conditions"),language:f.get("language"),
    methodical_profile:f.get("methodical_profile"),lesson_minutes:45};
  const btn=$("#generate-ai");btn.disabled=true;btn.textContent="Генерация...";
  try{
    const d=await api("/api/lessons/generate",{method:"POST",body:JSON.stringify(payload)});
    await loadLessons();toast("Материал создан и сохранён");
    await openEditor(d.id);
  }catch(e){toast(e.message)}
  finally{btn.disabled=false;btn.textContent="Сгенерировать КСП / КМЖ с AI"}
});

function libBody(x){
  const c=x.public_content||x.content||{};
  if(Array.isArray(c.blocks)&&c.blocks[0]&&c.blocks[0].parts&&typeof renderDocHtml==="function")
    return `<div class="paper-lite">${renderDocHtml({title:"",subject:"",grade:"",topic:""},c)}</div>`;
  return `<p>${esc(JSON.stringify(c))}</p>`;
}

async function downloadBackup(){
  if(!state.key){toast("Сначала заполните профиль");return}
  try{
    const r=await fetch("/api/workspace/backup",{headers:{"X-Workspace-Key":state.key}});
    if(!r.ok)throw new Error("Не удалось создать бэкап");
    const url=URL.createObjectURL(await r.blob()),a=document.createElement("a");
    a.href=url;a.download="ustaz-backup.json";a.click();URL.revokeObjectURL(url);toast("Бэкап скачан");
  }catch(e){toast(e.message)}
}
async function restoreBackupFile(file){
  if(!state.key){toast("Сначала заполните профиль");return}
  if(!file)return;
  try{
    const text=await file.text();
    const data=JSON.parse(text);
    const d=await api("/api/workspace/restore",{method:"POST",body:JSON.stringify(data)});
    await loadLessons();toast("Импортировано материалов: "+d.created);
  }catch(e){toast(e.message||"Ошибка импорта")}
}
["workspace-backup","workspace-backup-home"].forEach(id=>{
  const el=document.getElementById(id); if(el)el.addEventListener("click",downloadBackup);
});
["workspace-restore","workspace-restore-home"].forEach(id=>{
  const el=document.getElementById(id); if(el)el.addEventListener("change",e=>{restoreBackupFile(e.target.files[0]);e.target.value=""});
});
