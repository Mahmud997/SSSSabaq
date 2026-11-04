// Редактор КСП/КМЖ: таблицы, строки/столбцы, пять модулей, AI-перегенерация блока, просмотр и печать.
const ED={id:null,doc:null,dirty:false,saving:false,timer:null,undo:{}};
const rid=()=>(Math.random().toString(36)+"00000000").slice(2,10);
const LANGS={ru:"Русский",kk:"Қазақша",en:"English",uz:"Ўзбекча (кириллица)"};
const KSP_COLS=["Этап урока","Время (мин)","Деятельность учителя","Деятельность учащихся","Ресурсы","ФО и дескрипторы","Использование ИКТ / ИИ"];

function setSaveState(t,c=""){const el=$("#save-indicator");if(el){el.textContent=t;el.className="save-indicator "+c}}
function renderWarnings(list){
  const box=$("#editor-warnings");
  const dt=(ED.doc&&ED.doc.doc_type)||"ksp";
  const ok=dt==="ksp"
    ?"Проверка пройдена: пять модулей, таблица КСП, 45 минут."
    :(dt==="presentation"?"Структура презентации в порядке."
      :"Проверка пройдена: структура документа в порядке.");
  box.innerHTML=list&&list.length
    ?list.map(w=>`<li class="${w.level}">${esc(w.message)}</li>`).join("")
    :`<li class="ok">${ok}</li>`;
}
async function openEditor(id){
  try{
    const l=await api("/api/lessons/"+id);
    ED.id=id;ED.doc=l.content;ED.undo={};ED.dirty=false;
    $("#editor-title").value=l.title||"";$("#editor-subject").value=l.subject||"";
    $("#editor-grade").value=l.grade||"";$("#editor-topic").value=l.topic||"";
    $("#editor-language").value=ED.doc.language||"";$("#editor-room").value=ED.doc.room_conditions||"";
    const dt=ED.doc.doc_type||"ksp";
    $("#editor-kind").textContent=DOC_LABELS[dt]||"";$("#variants-box").classList.toggle("hidden",dt==="ksp"||dt==="presentation"||["ktp","sor","soch","diagnostic","year_plan","theme_plan"].includes(dt));
    $("#variants-panel").classList.add("hidden");
    const hint=$("#editor-hint");
    if(hint)hint.textContent=dt==="ksp"
      ?"Пять обязательных модулей редактируются отдельно. Доп. разделы можно добавлять и удалять."
      :"Разделы материала редактируются свободно. Можно добавить варианты через AI.";
    renderEditor();renderWarnings(l.warnings);
    $("#document-editor").classList.remove("hidden");
    $("#document-editor").scrollIntoView({behavior:"smooth",block:"start"});
    setSaveState("Сохранено","saved");
  }catch(e){toast(e.message)}
}
function partHtml(p,pi){
  if(p.type==="table"){
    return `<div class="part part-table" data-p="${pi}"><div class="part-bar"><b>Таблица</b><span class="sum" data-sum></span><button type="button" class="text-danger" data-act="del-part">Удалить таблицу</button></div>
    <div class="tbl-scroll"><table class="ed-table"><thead><tr><th class="ctl"></th>${p.header.map((h,ci)=>`<th><textarea data-f="hcell" data-c="${ci}" rows="2">${esc(h)}</textarea><button type="button" class="x" data-act="del-col" data-c="${ci}" title="Удалить столбец">×</button></th>`).join("")}</tr></thead>
    <tbody>${p.rows.map((r,ri)=>`<tr data-r="${ri}"><td class="ctl"><button type="button" data-act="row-up" title="Выше">↑</button><button type="button" data-act="row-down" title="Ниже">↓</button><button type="button" data-act="del-row" title="Удалить строку">×</button></td>${p.header.map((_,ci)=>`<td><textarea data-f="cell" data-c="${ci}" rows="2">${esc(r[ci]??"")}</textarea></td>`).join("")}</tr>`).join("")}</tbody></table></div>
    <div class="part-add"><button type="button" class="secondary sm" data-act="add-row">+ Строка</button><button type="button" class="secondary sm" data-act="add-col">+ Столбец</button></div></div>`;
  }
  return `<div class="part" data-p="${pi}"><div class="part-bar"><b>Текст</b><button type="button" class="text-danger" data-act="del-part">Удалить фрагмент</button></div><textarea data-f="text" rows="6" placeholder="Текст (поддерживается **жирный**, списки «- »)">${esc(p.text)}</textarea></div>`;
}
function blockHtml(b,bi){
  const mod=!!b.module,ksp=(ED.doc.doc_type||"ksp")==="ksp";
  return `<article class="editor-block" data-b="${bi}"><div class="block-top"><span class="mod-badge ${mod?"":"extra"}">${mod?"Модуль "+b.module:(ksp?"Доп. раздел":"Раздел")}</span>
    <label class="grow">Название<input data-f="heading" value="${esc(b.heading)}"></label>
    ${(mod||!ksp)?'<button type="button" class="secondary sm" data-act="regen-toggle">AI: перегенерировать</button>':''}${mod?'':'<button type="button" class="text-danger" data-act="del-block">Удалить раздел</button>'}</div>
    <div class="regen-panel hidden"><textarea data-f="instr" rows="2" placeholder="Что изменить? (необязательно). Например: сделать задания проще, добавить работу в парах"></textarea><button type="button" class="primary sm" data-act="regen-run">Перегенерировать только этот блок</button></div>
    <div class="undo-row ${ED.undo[b.id]?"":"hidden"}"><button type="button" class="secondary sm" data-act="regen-undo">↶ Вернуть прежний текст блока</button></div>
    ${b.parts.map(partHtml).join("")}
    <div class="part-add"><button type="button" class="secondary sm" data-act="add-text">+ Текст</button><button type="button" class="secondary sm" data-act="add-table">+ Таблица</button></div></article>`;
}
function renderEditor(){
  $("#editor-blocks").innerHTML=ED.doc.blocks.map(blockHtml).join("");
  document.querySelectorAll("#editor-blocks textarea[data-f]").forEach(autosize);
  document.querySelectorAll("#editor-blocks .part-table").forEach(updateSum);
}
function autosize(t){if(t.dataset.f==="instr")return;t.style.height="auto";t.style.height=Math.min(t.scrollHeight+2,420)+"px"}
function updateSum(partEl){
  const bi=+partEl.closest("[data-b]").dataset.b,p=ED.doc.blocks[bi].parts[+partEl.dataset.p];
  const badge=partEl.querySelector("[data-sum]"),sum=dvSumMinutes(p);
  if(sum===null){badge.textContent="";return}
  badge.textContent=`Σ время: ${sum} / 45 мин`;badge.className="sum "+(sum===45?"ok":"bad");
}
function markDirty(){
  ED.dirty=true;setSaveState("Есть изменения","pending");
  clearTimeout(ED.timer);ED.timer=setTimeout(()=>saveEditor(false),1100);
}
function ctx(el){
  const b=el.closest("[data-b]"),p=el.closest("[data-p]");
  const bi=b?+b.dataset.b:-1,pi=p?+p.dataset.p:-1;
  return{bi,pi,block:ED.doc.blocks[bi],part:pi>=0?ED.doc.blocks[bi].parts[pi]:null,partEl:p,blockEl:b};
}
$("#editor-blocks").addEventListener("input",e=>{
  const t=e.target,f=t.dataset.f;if(!f||f==="instr")return;
  const c=ctx(t);
  if(f==="heading")c.block.heading=t.value;
  else if(f==="text")c.part.text=t.value;
  else if(f==="hcell")c.part.header[+t.dataset.c]=t.value;
  else if(f==="cell")c.part.rows[+t.closest("tr").dataset.r][+t.dataset.c]=t.value;
  autosize(t);if(c.part&&c.part.type==="table")updateSum(c.partEl);
  markDirty();
});
function focusCell(bi,pi,ri,ci){
  const sel=`[data-b="${bi}"] [data-p="${pi}"] tbody tr[data-r="${ri}"] textarea[data-c="${ci}"]`;
  const el=document.querySelector(sel);if(el)el.focus();
}
$("#editor-blocks").addEventListener("click",async e=>{
  const btn=e.target.closest("[data-act]");if(!btn)return;
  const act=btn.dataset.act,c=ctx(btn),parts=c.block.parts,p=c.part;
  const rowEl=btn.closest("tr"),ri=rowEl?+rowEl.dataset.r:-1;
  if(act==="regen-toggle"){c.blockEl.querySelector(".regen-panel").classList.toggle("hidden");return}
  if(act==="regen-run"){return regen(c.bi,btn)}
  if(act==="regen-undo"){c.block.parts=ED.undo[c.block.id];delete ED.undo[c.block.id];renderEditor();markDirty();return}
  if(act==="del-block"){if(!confirm("Удалить раздел?"))return;if(ED.doc.blocks.length<=1)return toast("Нужен хотя бы один раздел");ED.doc.blocks.splice(c.bi,1)}
  else if(act==="del-part"){if(!confirm("Удалить этот фрагмент?"))return;parts.splice(c.pi,1)}
  else if(act==="add-text")parts.push({type:"text",text:""});
  else if(act==="add-table"){const n=c.block.module===2?KSP_COLS:["Колонка 1","Колонка 2","Колонка 3"];parts.push({type:"table",header:[...n],rows:[n.map(()=>"")]})}
  else if(act==="add-row"){p.rows.push(p.header.map(()=>""));renderEditor();markDirty();return focusCell(c.bi,c.pi,p.rows.length-1,0)}
  else if(act==="add-col"){p.header.push("Новый столбец");p.rows.forEach(r=>r.push(""))}
  else if(act==="del-col"){if(p.header.length<=1)return toast("В таблице должен остаться хотя бы один столбец");const ci=+btn.dataset.c;p.header.splice(ci,1);p.rows.forEach(r=>r.splice(ci,1))}
  else if(act==="del-row"){p.rows.splice(ri,1)}
  else if(act==="row-up"&&ri>0){[p.rows[ri-1],p.rows[ri]]=[p.rows[ri],p.rows[ri-1]]}
  else if(act==="row-down"&&ri<p.rows.length-1){[p.rows[ri+1],p.rows[ri]]=[p.rows[ri],p.rows[ri+1]]}
  else return;
  renderEditor();markDirty();
});
async function regen(bi,btn){
  const block=ED.doc.blocks[bi];
  if(!ED.doc.language)return toast("Сначала выберите язык документа в реквизитах");
  const instr=btn.closest(".regen-panel").querySelector("[data-f=instr]").value;
  clearTimeout(ED.timer);await saveEditor(false);
  if(ED.dirty)return toast("Не удалось сохранить документ перед перегенерацией");
  const old=btn.textContent;btn.disabled=true;btn.textContent="Генерация…";
  try{
    const d=await api(`/api/lessons/${ED.id}/blocks/${block.id}/regenerate`,{method:"POST",body:JSON.stringify({instruction:instr})});
    ED.undo[block.id]=block.parts;block.parts=d.parts;
    renderEditor();renderWarnings(d.warnings);markDirty();toast("Блок перегенерирован. Его можно вернуть кнопкой «Вернуть прежний текст»");
  }catch(err){toast(err.message);btn.disabled=false;btn.textContent=old}
}
function editorMeta(){return{title:$("#editor-title").value.trim(),subject:$("#editor-subject").value.trim(),grade:$("#editor-grade").value.trim(),topic:$("#editor-topic").value.trim()}}
function editorPayload(){
  ED.doc.language=$("#editor-language").value;ED.doc.room_conditions=$("#editor-room").value.trim();
  return{...editorMeta(),content:ED.doc};
}
async function saveEditor(showToast=true){
  if(!ED.id||!ED.dirty||ED.saving)return;
  const payload=editorPayload();
  if(!payload.title||!payload.subject||!payload.grade||!payload.topic){setSaveState("Заполните реквизиты","error");return}
  ED.saving=true;setSaveState("Сохранение…","pending");
  try{
    const d=await api(`/api/lessons/${ED.id}`,{method:"PUT",body:JSON.stringify(payload)});
    ED.dirty=false;setSaveState("Все изменения сохранены","saved");renderWarnings(d.warnings);
    if(showToast)toast("Документ сохранён");
    loadLessons();
  }catch(e){setSaveState("Ошибка сохранения","error");if(showToast)toast(e.message)}
  finally{ED.saving=false}
}
["editor-title","editor-subject","editor-grade","editor-topic","editor-language","editor-room"].forEach(id=>{
  $("#"+id).addEventListener("input",markDirty);$("#"+id).addEventListener("change",markDirty);
});
$("#add-block").addEventListener("click",()=>{ED.doc.blocks.push({id:rid(),module:null,heading:"Новый раздел",parts:[{type:"text",text:""}]});renderEditor();markDirty()});
$("#save-document").addEventListener("click",()=>saveEditor(true));
$("#close-editor").addEventListener("click",async()=>{clearTimeout(ED.timer);await saveEditor(false);$("#document-editor").classList.add("hidden");ED.id=null});
$("#export-docx").addEventListener("click",async()=>{
  clearTimeout(ED.timer);await saveEditor(false);if(!ED.id||ED.dirty)return;
  try{
    const r=await fetch(`/api/lessons/${ED.id}/export.docx`,{headers:{"X-Workspace-Key":state.key}});
    if(!r.ok)throw new Error("Не удалось подготовить DOCX");
    const url=URL.createObjectURL(await r.blob()),a=document.createElement("a");
    a.href=url;a.download=($("#editor-title").value||"KSP")+".docx";a.click();URL.revokeObjectURL(url);toast("DOCX подготовлен");
  }catch(e){toast(e.message)}
});
// Просмотр перед печатью
function openPreview(){
  const land=docNeedsLandscape(ED.doc);
  $("#print-paper").className="paper "+(land?"landscape":"portrait");
  $("#print-paper").innerHTML=renderDocHtml(editorMeta(),ED.doc);
  $("#page-style").textContent=`@page{size:A4 ${land?"landscape":"portrait"};margin:12mm}`;
  $("#print-overlay").classList.remove("hidden");document.body.classList.add("previewing");
}
$("#preview-doc").addEventListener("click",openPreview);
$("#print-now").addEventListener("click",()=>window.print());
$("#print-close").addEventListener("click",()=>{$("#print-overlay").classList.add("hidden");document.body.classList.remove("previewing")});

$("#variants-toggle").addEventListener("click",()=>$("#variants-panel").classList.toggle("hidden"));
$("#variants-run").addEventListener("click",async()=>{
  if(!ED.doc.language)return toast("Сначала выберите язык документа в реквизитах");
  const btn=$("#variants-run"),old=btn.textContent;
  clearTimeout(ED.timer);await saveEditor(false);if(ED.dirty)return toast("Не удалось сохранить документ");
  btn.disabled=true;btn.textContent="Генерация…";
  try{
    const d=await api(`/api/lessons/${ED.id}/variants`,{method:"POST",body:JSON.stringify({count:+$("#variants-count").value,instruction:$("#variants-instr").value})});
    ED.doc.blocks.push(...d.blocks);renderEditor();markDirty();toast("Варианты добавлены в конец документа");
  }catch(e){toast(e.message)}finally{btn.disabled=false;btn.textContent=old}
});

$("#export-xlsx")&&$("#export-xlsx").addEventListener("click",async()=>{
  clearTimeout(ED.timer);await saveEditor(false);if(!ED.id||ED.dirty)return;
  try{
    const r=await fetch(`/api/lessons/${ED.id}/export.xlsx`,{headers:{"X-Workspace-Key":state.key}});
    if(!r.ok)throw new Error("Не удалось подготовить XLSX");
    const url=URL.createObjectURL(await r.blob()),a=document.createElement("a");
    a.href=url;a.download=($("#editor-title").value||"export")+".xlsx";a.click();URL.revokeObjectURL(url);toast("XLSX готов");
  }catch(e){toast(e.message)}
});
