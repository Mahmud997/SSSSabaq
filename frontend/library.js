// Этап 8: библиотека, избранное, шаблоны, история версий
async function loadFavorites(){
  const box=$("#favorites-list"); if(!box)return;
  if(!state.key){box.innerHTML='<article class="item">Создайте рабочее пространство.</article>';return}
  try{
    const rows=await api("/api/favorites");
    box.innerHTML=rows.length?rows.map(f=>`<article class="item">
      <h3>${esc(f.title||"Без названия")}</h3>
      <p>${esc(f.subject||"")} · ${esc(f.grade||"")} · ${esc(f.topic||"")} · <small>${esc(f.target_type)}</small></p>
      <div class="actions">
        ${f.target_type==="publication"?`<button class="primary sm" data-clone-pub="${f.target_id}">Копировать к себе</button>`:""}
        ${f.target_type==="lesson"?`<button class="primary sm" data-open-fav="${f.target_id}">Открыть</button>`:""}
        <button class="text-danger sm" data-unfav="${f.id}">Убрать</button>
      </div></article>`).join(""):'<article class="item">Избранное пусто.</article>';
    box.querySelectorAll("[data-unfav]").forEach(b=>b.addEventListener("click",async()=>{
      try{await api("/api/favorites/"+b.dataset.unfav,{method:"DELETE"});toast("Убрано");loadFavorites()}catch(e){toast(e.message)}
    }));
    box.querySelectorAll("[data-clone-pub]").forEach(b=>b.addEventListener("click",()=>clonePublication(b.dataset.clonePub)));
    box.querySelectorAll("[data-open-fav]").forEach(b=>b.addEventListener("click",()=>{
      const id=b.dataset.openFav; const item=(state.lessons||[]).find(x=>x.id===id);
      const dt=item&&item.content&&item.content.doc_type;
      if(dt==="presentation"&&typeof openPresentationEditor==="function"){view("presentation");openPresentationEditor(id)}
      else{view("lesson");openEditor(id)}
    }));
  }catch(e){box.innerHTML=`<article class="item">${esc(e.message)}</article>`}
}
async function loadTemplates(){
  const box=$("#templates-list"); if(!box)return;
  if(!state.key){box.innerHTML='<article class="item">—</article>';return}
  try{
    const rows=await api("/api/templates");
    box.innerHTML=rows.length?rows.map(x=>`<article class="item">
      <h3>${esc(x.title)} <span class="mod-badge extra">${esc(DOC_LABELS[x.doc_type]||x.doc_type||"")}</span></h3>
      <p>${esc(x.subject)} · ${esc(x.grade)} · ${esc(x.topic)}</p>
      <div class="actions">
        <button class="primary sm" data-use-tpl="${x.id}">Создать из шаблона</button>
        <button class="text-danger sm" data-del-tpl="${x.id}">Удалить</button>
      </div></article>`).join(""):'<article class="item">Нет шаблонов. В списке материалов нажмите «В шаблоны».</article>';
    box.querySelectorAll("[data-use-tpl]").forEach(b=>b.addEventListener("click",async()=>{
      try{
        const d=await api("/api/templates/"+b.dataset.useTpl+"/use",{method:"POST",body:"{}"});
        await loadLessons(); toast("Создано из шаблона"); view("lesson"); openEditor(d.id);
      }catch(e){toast(e.message)}
    }));
    box.querySelectorAll("[data-del-tpl]").forEach(b=>b.addEventListener("click",async()=>{
      if(!confirm("Удалить шаблон?"))return;
      try{await api("/api/templates/"+b.dataset.delTpl,{method:"DELETE"});loadTemplates();toast("Удалено")}catch(e){toast(e.message)}
    }));
  }catch(e){box.innerHTML=`<article class="item">${esc(e.message)}</article>`}
}
async function clonePublication(id){
  if(!state.key){toast("Сначала заполните профиль");return}
  try{
    const d=await api("/api/library/"+id+"/clone",{method:"POST",body:"{}"});
    await loadLessons(); toast("Скопировано в ваши материалы");
    view("lesson"); openEditor(d.id);
  }catch(e){toast(e.message)}
}
async function addFavorite(targetType, targetId){
  if(!state.key){toast("Сначала заполните профиль");return}
  try{
    await api("/api/favorites",{method:"POST",body:JSON.stringify({target_type:targetType,target_id:targetId})});
    toast("В избранном"); loadFavorites();
  }catch(e){toast(e.message)}
}
async function saveAsTemplate(lessonId){
  if(!state.key)return;
  try{
    const d=await api("/api/templates",{method:"POST",body:JSON.stringify({lesson_id:lessonId,title:""})});
    toast("Шаблон сохранён: "+d.title); loadTemplates();
  }catch(e){toast(e.message)}
}

// Override / enhance loadLibrary
const _loadLibraryOrig = typeof loadLibrary==="function"?loadLibrary:null;
async function loadLibrary(){
  try{
    const q=$("#lib-q")?$("#lib-q").value.trim():"";
    const subject=$("#lib-subject")?$("#lib-subject").value.trim():"";
    const grade=$("#lib-grade")?$("#lib-grade").value.trim():"";
    const params=new URLSearchParams();
    if(q)params.set("q",q); if(subject)params.set("subject",subject); if(grade)params.set("grade",grade);
    const qs=params.toString()?"?"+params.toString():"";
    const rows=await api("/api/library"+qs);
    $("#public-count")&&($("#public-count").textContent=rows.length);
    $("#library-list").innerHTML=rows.map(x=>`<article class="item">
      <h3>${esc(x.title)} <span class="mod-badge extra">${esc(DOC_LABELS[x.doc_type]||"")}</span></h3>
      <p>${esc(x.subject)} · ${esc(x.grade)} · ${esc(x.topic)}</p>
      ${typeof libBody==="function"?libBody(x):""}
      <div class="actions">
        <button class="primary sm" data-clone-pub="${x.id}">Копировать к себе</button>
        <button class="secondary sm" data-fav-pub="${x.id}">В избранное</button>
      </div>
    </article>`).join("")||'<article class="item">Пока нет опубликованных материалов.</article>';
    document.querySelectorAll("[data-clone-pub]").forEach(b=>b.addEventListener("click",()=>clonePublication(b.dataset.clonePub)));
    document.querySelectorAll("[data-fav-pub]").forEach(b=>b.addEventListener("click",()=>addFavorite("publication",b.dataset.favPub)));
    loadFavorites(); loadTemplates();
  }catch(e){toast(e.message)}
}
window.loadLibrary=loadLibrary;

$("#refresh-library")&&$("#refresh-library").addEventListener("click",loadLibrary);
["lib-q","lib-subject","lib-grade"].forEach(id=>{
  const el=$("#"+id); if(el)el.addEventListener("keydown",e=>{if(e.key==="Enter")loadLibrary()});
});
document.querySelector('[data-view="library"]')&&document.querySelector('[data-view="library"]').addEventListener("click",()=>{loadLibrary();loadFavorites();loadTemplates()});

// Versions in editor
async function loadVersions(){
  if(!ED||!ED.id)return;
  const box=$("#versions-list"); if(!box)return;
  try{
    const rows=await api(`/api/lessons/${ED.id}/versions`);
    box.innerHTML=rows.length?rows.map(v=>`<div class="version-row">
      <div><b>${esc(v.note||"Снимок")}</b><br><small>${esc(v.created_at)} · ${esc(DOC_LABELS[v.doc_type]||"")}</small></div>
      <button type="button" class="secondary sm" data-restore="${v.id}">Восстановить</button>
    </div>`).join(""):'<p class="hint">Пока нет сохранённых версий. Они появляются после правок.</p>';
    box.querySelectorAll("[data-restore]").forEach(b=>b.addEventListener("click",async()=>{
      if(!confirm("Восстановить эту версию? Текущее состояние сохранится в истории."))return;
      try{
        const d=await api(`/api/lessons/${ED.id}/versions/${b.dataset.restore}/restore`,{method:"POST",body:JSON.stringify({})});
        ED.doc=d.content; ED.dirty=false;
        $("#editor-title").value=d.title||$("#editor-title").value;
        renderEditor(); renderWarnings(d.warnings||[]);
        setSaveState("Восстановлено","saved"); toast("Версия восстановлена"); loadVersions();
      }catch(e){toast(e.message)}
    }));
  }catch(e){box.innerHTML=`<p class="hint">${esc(e.message)}</p>`}
}
$("#versions-toggle")&&$("#versions-toggle").addEventListener("click",()=>{
  const panel=$("#versions-panel");
  panel.classList.toggle("hidden");
  if(!panel.classList.contains("hidden"))loadVersions();
});

// Enhance lesson list: template + favorite buttons via patching after loadLessons
const _loadLessons = window.loadLessons;
// We monkey-patch by redefining after app.js - attach to existing flow
document.addEventListener("click",e=>{
  const tpl=e.target.closest("[data-template]");
  if(tpl){e.preventDefault();saveAsTemplate(tpl.dataset.template);return}
  const fav=e.target.closest("[data-fav-lesson]");
  if(fav){e.preventDefault();addFavorite("lesson",fav.dataset.favLesson);return}
});

// Patch list HTML: wrap loadLessons if possible
(function patchLoadLessons(){
  if(typeof loadLessons!=="function")return;
  const orig=loadLessons;
  window.loadLessons=async function(){
    await orig();
    // inject extra buttons into lesson-results
    document.querySelectorAll("#lesson-results .item").forEach(art=>{
      if(art.querySelector("[data-template]"))return;
      const editBtn=art.querySelector("[data-edit]");
      if(!editBtn)return;
      const id=editBtn.dataset.edit;
      const actions=art.querySelector(".actions");
      if(!actions)return;
      const t=document.createElement("button");
      t.className="secondary sm"; t.dataset.template=id; t.textContent="В шаблоны";
      const f=document.createElement("button");
      f.className="secondary sm"; f.dataset.favLesson=id; f.textContent="★";
      actions.appendChild(t); actions.appendChild(f);
    });
  };
})();
