// Этап 6: презентации — форма, редактор слайдов, PPTX / просмотр PDF
const PRES = {id: null, doc: null, dirty: false, saving: false, timer: null, undo: {}};
const PRES_LAYOUTS = {title: "Титул", section: "Раздел", content: "Текст", bullets: "Список", two_col: "Две колонки", closing: "Финал"};

function presRid(){return (Math.random().toString(36)+"00000000").slice(2,10)}
function setPresSave(t,c=""){const el=$("#pres-save-indicator");if(el){el.textContent=t;el.className="save-indicator "+c}}
function renderPresWarnings(list){
  const box=$("#pres-warnings");
  if(!box)return;
  box.innerHTML=list&&list.length
    ?list.map(w=>`<li class="${w.level}">${esc(w.message)}</li>`).join("")
    :'<li class="ok">Структура презентации в порядке.</li>';
}
function emptySlide(layout){
  return {id:presRid(),layout:layout||"content",title:"",subtitle:"",body:"",bullets:[],left:"",right:"",notes:"",accent:""};
}
function fillPresLessons(){
  const sel=$("#pres-lesson"); if(!sel)return;
  const cur=sel.value;
  sel.innerHTML='<option value="">— без привязки —</option>'+(state.lessons||[])
    .filter(l=>{const d=l.content&&l.content.doc_type; return !d||d==="ksp"})
    .map(l=>`<option value="${l.id}">${esc(l.title)}</option>`).join("");
  sel.value=cur;
}
function slideHtml(s,i){
  const bullets=(s.bullets||[]).join("\n");
  return `<article class="pres-slide" data-i="${i}">
    <div class="pres-slide-head">
      <span class="mod-badge">Слайд ${i+1}</span>
      <label>Макет<select data-f="layout">${Object.keys(PRES_LAYOUTS).map(k=>`<option value="${k}" ${s.layout===k?"selected":""}>${PRES_LAYOUTS[k]}</option>`).join("")}</select></label>
      <button type="button" class="secondary sm" data-act="up" title="Выше">↑</button>
      <button type="button" class="secondary sm" data-act="down" title="Ниже">↓</button>
      <button type="button" class="secondary sm" data-act="regen">AI</button>
      <button type="button" class="text-danger" data-act="del">Удалить</button>
    </div>
    <div class="form-grid pres-fields">
      <label class="full">Заголовок<input data-f="title" value="${esc(s.title||"")}"></label>
      <label class="full">Подзаголовок<input data-f="subtitle" value="${esc(s.subtitle||"")}"></label>
      <label class="full">Текст<textarea data-f="body" rows="3">${esc(s.body||"")}</textarea></label>
      <label class="full">Пункты списка (по одному в строке)<textarea data-f="bullets" rows="4">${esc(bullets)}</textarea></label>
      <label>Левая колонка<textarea data-f="left" rows="3">${esc(s.left||"")}</textarea></label>
      <label>Правая колонка<textarea data-f="right" rows="3">${esc(s.right||"")}</textarea></label>
      <label class="full">Ключевая фраза / формула<input data-f="accent" value="${esc(s.accent||"")}"></label>
      <label class="full">Заметки учителя (не на экране)<textarea data-f="notes" rows="2">${esc(s.notes||"")}</textarea></label>
    </div>
    <div class="regen-panel hidden"><textarea data-f="instr" rows="2" placeholder="Что изменить на этом слайде?"></textarea>
      <button type="button" class="primary sm" data-act="regen-run">Перегенерировать слайд</button></div>
  </article>`;
}
function renderPresSlides(){
  const box=$("#pres-slides");
  if(!box||!PRES.doc)return;
  box.innerHTML=(PRES.doc.slides||[]).map(slideHtml).join("")||'<p class="hint">Нет слайдов. Добавьте первый.</p>';
}
function markPresDirty(){
  PRES.dirty=true; setPresSave("Есть изменения","pending");
  clearTimeout(PRES.timer); PRES.timer=setTimeout(()=>savePresentation(false),1200);
}
async function openPresentation(id){
  try{
    const l=await api("/api/presentations/"+id);
    PRES.id=id; PRES.doc=l.content; PRES.dirty=false; PRES.undo={};
    $("#pres-title").value=l.title||"";
    $("#pres-subject").value=l.subject||"";
    $("#pres-grade").value=l.grade||"";
    $("#pres-topic").value=l.topic||"";
    $("#pres-language").value=PRES.doc.language||"";
    $("#pres-room").value=PRES.doc.room_conditions||"";
    $("#pres-editor-title").textContent=l.title||"Презентация";
    renderPresSlides(); renderPresWarnings(l.warnings);
    $("#presentation-editor").classList.remove("hidden");
    $("#presentation-editor").scrollIntoView({behavior:"smooth",block:"start"});
    setPresSave("Сохранено","saved");
  }catch(e){toast(e.message)}
}
function readSlideFromDom(art){
  const g=f=>art.querySelector(`[data-f="${f}"]`);
  const bullets=(g("bullets").value||"").split("\n").map(x=>x.trim()).filter(Boolean);
  return {
    id: PRES.doc.slides[+art.dataset.i].id,
    layout: g("layout").value,
    title: g("title").value,
    subtitle: g("subtitle").value,
    body: g("body").value,
    bullets,
    left: g("left").value,
    right: g("right").value,
    accent: g("accent").value,
    notes: g("notes").value,
  };
}
function syncSlidesFromDom(){
  if(!PRES.doc)return;
  const arts=[...document.querySelectorAll("#pres-slides .pres-slide")];
  PRES.doc.slides=arts.map(readSlideFromDom);
}
function presPayload(){
  syncSlidesFromDom();
  PRES.doc.language=$("#pres-language").value;
  PRES.doc.room_conditions=$("#pres-room").value.trim();
  return {
    title: $("#pres-title").value.trim(),
    subject: $("#pres-subject").value.trim(),
    grade: $("#pres-grade").value.trim(),
    topic: $("#pres-topic").value.trim(),
    content: PRES.doc,
  };
}
async function savePresentation(showToast=true){
  if(!PRES.id||!PRES.dirty||PRES.saving)return;
  const payload=presPayload();
  if(!payload.title||!payload.subject||!payload.grade||!payload.topic){setPresSave("Заполните реквизиты","error");return}
  PRES.saving=true; setPresSave("Сохранение…","pending");
  try{
    const d=await api(`/api/presentations/${PRES.id}`,{method:"PUT",body:JSON.stringify(payload)});
    PRES.dirty=false; PRES.doc=d.content;
    setPresSave("Все изменения сохранены","saved");
    renderPresWarnings(d.warnings);
    if(showToast)toast("Презентация сохранена");
    loadLessons();
  }catch(e){setPresSave("Ошибка сохранения","error"); if(showToast)toast(e.message)}
  finally{PRES.saving=false}
}

// form
$("#pres-form")&&$("#pres-form").addEventListener("submit",async e=>{
  e.preventDefault();
  if(!state.key){toast("Сначала заполните профиль учителя");$("#profile-gate").classList.remove("hidden");return}
  const f=new FormData(e.target), payload={};
  f.forEach((v,k)=>{payload[k]=v});
  payload.slide_count=+payload.slide_count||10;
  if(!payload.lesson_id)delete payload.lesson_id;
  const btn=$("#pres-run"); btn.disabled=true; btn.textContent="Генерация…";
  try{
    const d=await api("/api/presentations/generate",{method:"POST",body:JSON.stringify(payload)});
    await loadLessons(); toast("Презентация создана");
    view("presentation"); await openPresentation(d.id);
  }catch(err){toast(err.message)}
  finally{btn.disabled=false; btn.textContent="Создать презентацию с AI"}
});

$("#pres-lesson")&&$("#pres-lesson").addEventListener("change",e=>{
  const l=(state.lessons||[]).find(x=>x.id===e.target.value); if(!l)return;
  const f=$("#pres-form");
  f.subject.value=l.subject; f.grade.value=l.grade; f.topic.value=l.topic;
  if(l.content&&l.content.room_conditions)f.room_conditions.value=l.content.room_conditions;
});

document.querySelector('[data-view="presentation"]')&&document.querySelector('[data-view="presentation"]').addEventListener("click",fillPresLessons);
document.querySelectorAll('[data-go="presentation"]').forEach(b=>b.addEventListener("click",fillPresLessons));

["pres-title","pres-subject","pres-grade","pres-topic","pres-language","pres-room"].forEach(id=>{
  const el=$("#"+id); if(!el)return;
  el.addEventListener("input",markPresDirty); el.addEventListener("change",markPresDirty);
});

$("#pres-slides")&&$("#pres-slides").addEventListener("input",e=>{
  if(!e.target.dataset.f||e.target.dataset.f==="instr")return;
  markPresDirty();
});
$("#pres-slides")&&$("#pres-slides").addEventListener("change",e=>{
  if(e.target.dataset.f==="layout")markPresDirty();
});

$("#pres-slides")&&$("#pres-slides").addEventListener("click",async e=>{
  const btn=e.target.closest("[data-act]"); if(!btn)return;
  const art=btn.closest(".pres-slide"); if(!art)return;
  const i=+art.dataset.i;
  const act=btn.dataset.act;
  syncSlidesFromDom();
  if(act==="del"){
    if(PRES.doc.slides.length<=1)return toast("Нужен хотя бы один слайд");
    if(!confirm("Удалить слайд?"))return;
    PRES.doc.slides.splice(i,1); renderPresSlides(); markPresDirty(); return;
  }
  if(act==="up"&&i>0){
    [PRES.doc.slides[i-1],PRES.doc.slides[i]]=[PRES.doc.slides[i],PRES.doc.slides[i-1]];
    renderPresSlides(); markPresDirty(); return;
  }
  if(act==="down"&&i<PRES.doc.slides.length-1){
    [PRES.doc.slides[i+1],PRES.doc.slides[i]]=[PRES.doc.slides[i],PRES.doc.slides[i+1]];
    renderPresSlides(); markPresDirty(); return;
  }
  if(act==="regen"){art.querySelector(".regen-panel").classList.toggle("hidden");return}
  if(act==="regen-run"){
    if(!PRES.doc.language)return toast("Выберите язык документа");
    clearTimeout(PRES.timer); await savePresentation(false);
    if(PRES.dirty)return toast("Не удалось сохранить перед перегенерацией");
    const instr=art.querySelector("[data-f=instr]").value;
    const slide=PRES.doc.slides[i];
    btn.disabled=true; const old=btn.textContent; btn.textContent="…";
    try{
      const d=await api(`/api/presentations/${PRES.id}/slides/${slide.id}/regenerate`,{
        method:"POST",body:JSON.stringify({instruction:instr})
      });
      PRES.doc.slides[i]=d.slide; renderPresSlides(); renderPresWarnings(d.warnings);
      markPresDirty(); toast("Слайд перегенерирован");
    }catch(err){toast(err.message)}
    finally{btn.disabled=false; btn.textContent=old}
  }
});

$("#pres-add-slide")&&$("#pres-add-slide").addEventListener("click",()=>{
  syncSlidesFromDom();
  const layout=$("#pres-new-layout").value||"content";
  PRES.doc.slides.push(emptySlide(layout));
  renderPresSlides(); markPresDirty();
});
$("#pres-save")&&$("#pres-save").addEventListener("click",()=>savePresentation(true));
$("#pres-close")&&$("#pres-close").addEventListener("click",async()=>{
  clearTimeout(PRES.timer); await savePresentation(false);
  $("#presentation-editor").classList.add("hidden"); PRES.id=null;
});

$("#pres-export-pptx")&&$("#pres-export-pptx").addEventListener("click",async()=>{
  clearTimeout(PRES.timer); await savePresentation(false);
  if(!PRES.id||PRES.dirty)return;
  try{
    const r=await fetch(`/api/presentations/${PRES.id}/export.pptx`,{headers:{"X-Workspace-Key":state.key}});
    if(!r.ok)throw new Error("Не удалось подготовить PPTX");
    const url=URL.createObjectURL(await r.blob()),a=document.createElement("a");
    a.href=url; a.download=($("#pres-title").value||"Presentation")+".pptx"; a.click();
    URL.revokeObjectURL(url); toast("PPTX готов");
  }catch(e){toast(e.message)}
});

function renderPresPreviewHtml(){
  syncSlidesFromDom();
  const meta={title:$("#pres-title").value,subject:$("#pres-subject").value,grade:$("#pres-grade").value,topic:$("#pres-topic").value};
  const slides=PRES.doc.slides||[];
  return slides.map((s,i)=>{
    const bullets=(s.bullets||[]).map(b=>`<li>${esc(b)}</li>`).join("");
    let body="";
    if(s.layout==="two_col"){
      body=`<div class="pres-two"><div>${esc(s.left||"").replace(/\n/g,"<br>")}</div><div>${esc(s.right||"").replace(/\n/g,"<br>")}</div></div>`;
    }else if(bullets){
      body=`<ul>${bullets}</ul>`;
    }else{
      body=`<p>${esc(s.body||"").replace(/\n/g,"<br>")}</p>`;
    }
    return `<section class="pres-print-slide layout-${esc(s.layout||"content")}">
      <div class="pres-print-num">${i+1}/${slides.length}</div>
      <h2>${esc(s.title||"")}</h2>
      ${s.subtitle?`<p class="sub">${esc(s.subtitle)}</p>`:""}
      ${body}
      ${s.accent?`<p class="accent">${esc(s.accent)}</p>`:""}
      <div class="pres-print-foot">${esc([meta.subject,meta.grade,meta.topic].filter(Boolean).join(" · "))}</div>
    </section>`;
  }).join("");
}

$("#pres-preview")&&$("#pres-preview").addEventListener("click",()=>{
  if(!PRES.doc)return;
  $("#print-paper").className="paper landscape pres-print";
  $("#print-paper").innerHTML=renderPresPreviewHtml();
  $("#page-style").textContent="@page{size:A4 landscape;margin:10mm}";
  $("#print-overlay").classList.remove("hidden");
  document.body.classList.add("previewing");
});

// Open presentation from lesson list if doc_type=presentation
window.openPresentationEditor=openPresentation;

$("#pres-export-xlsx")&&$("#pres-export-xlsx").addEventListener("click",async()=>{
  clearTimeout(PRES.timer);await savePresentation(false);if(!PRES.id||PRES.dirty)return;
  try{
    const r=await fetch(`/api/presentations/${PRES.id}/export.xlsx`,{headers:{"X-Workspace-Key":state.key}});
    if(!r.ok)throw new Error("Не удалось подготовить XLSX");
    const url=URL.createObjectURL(await r.blob()),a=document.createElement("a");
    a.href=url;a.download=($("#pres-title").value||"presentation")+".xlsx";a.click();URL.revokeObjectURL(url);toast("XLSX готов");
  }catch(e){toast(e.message)}
});
