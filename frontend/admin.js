// Этап 9: полноценная админ-панель
function adminHeaders(){
  return {Authorization: "Bearer " + ($("#admin-secret").value || ""), "Content-Type": "application/json"};
}
async function adminFetch(path, opts={}){
  const r = await fetch(path, {...opts, headers: {...adminHeaders(), ...(opts.headers||{})}});
  const data = await r.json().catch(()=>({}));
  if(!r.ok) throw new Error(data.detail || (typeof data.detail==="string"?data.detail:"Ошибка доступа"));
  return data;
}

async function openAdminPanel(){
  const box=$("#admin-dashboard");
  const msg=$("#admin-message");
  try{
    const [overview, workspaces, lessons, events, publications, aiCfg, prompts, usage, stats] = await Promise.all([
      adminFetch("/api/admin/overview"),
      adminFetch("/api/admin/workspaces"),
      adminFetch("/api/admin/lessons"),
      adminFetch("/api/admin/events"),
      adminFetch("/api/admin/publications"),
      adminFetch("/api/admin/ai-config"),
      adminFetch("/api/admin/prompts"),
      adminFetch("/api/admin/ai-usage?limit=50"),
      adminFetch("/api/admin/stats"),
    ]);
    box.classList.remove("hidden");
    const keysHtml = Object.entries(aiCfg.keys||{}).map(([k,v])=>
      `<span class="key-pill ${v?"ok":"bad"}">${esc(k)}: ${v?"задан":"нет"}</span>`).join(" ");
    const subjects = prompts.subjects||{};
    const subjRows = Object.entries(subjects).map(([k,v])=>
      `<label class="full"><b>${esc(k)}</b><textarea data-subj="${esc(k)}" rows="2">${esc(v)}</textarea></label>`).join("");

    box.innerHTML = `
<div class="stats">${Object.entries(overview).map(([k,v])=>`<article class="stat"><small>${esc(k)}</small><b>${v}</b></article>`).join("")}</div>

<article class="item admin-section">
  <h3>AI-провайдер и модель</h3>
  <p class="hint">Ключи API задаются только в переменных окружения сервера. Здесь — выбор провайдера/модели и вкл/выкл.</p>
  <div class="form-grid">
    <label>Провайдер
      <select id="adm-provider">${(aiCfg.providers||[]).map(p=>`<option value="${p}" ${aiCfg.config.provider===p?"selected":""}>${p}</option>`).join("")}</select>
    </label>
    <label>Модель<input id="adm-model" value="${esc(aiCfg.config.model||"")}" placeholder="пусто = модель по умолчанию"></label>
    <label>Таймаут (сек)<input id="adm-timeout" type="number" min="15" max="300" value="${esc(aiCfg.config.timeout_seconds||90)}"></label>
    <label>AI включён
      <select id="adm-enabled"><option value="1" ${aiCfg.config.enabled!==false?"selected":""}>Да</option><option value="0" ${aiCfg.config.enabled===false?"selected":""}>Нет</option></select>
    </label>
    <div class="full"><div class="key-row">${keysHtml}</div></div>
    <div class="full actions"><button class="primary" id="adm-save-ai">Сохранить AI-настройки</button></div>
  </div>
</article>

<article class="item admin-section">
  <h3>Базовый системный промпт</h3>
  <textarea id="adm-base-prompt" rows="8">${esc(prompts.base||"")}</textarea>
  <div class="actions" style="margin-top:10px"><button class="primary" id="adm-save-base">Сохранить базовый промпт</button></div>
</article>

<article class="item admin-section">
  <h3>Предметные профили</h3>
  <div class="form-grid" id="adm-subjects">${subjRows||"<p>Нет профилей</p>"}</div>
  <div class="actions"><button class="primary" id="adm-save-subjects">Сохранить предметные промпты</button></div>
</article>

<article class="item admin-section">
  <h3>Статистика</h3>
  <p><b>По типам документов:</b> ${Object.entries(stats.by_doc_type||{}).map(([k,v])=>`${esc(k)}: ${v}`).join(" · ")||"—"}</p>
  <p><b>По предметам:</b> ${Object.entries(stats.by_subject||{}).slice(0,12).map(([k,v])=>`${esc(k)}: ${v}`).join(" · ")||"—"}</p>
  <p>Средняя задержка AI: <b>${stats.ai_avg_latency_ms||0} мс</b> · Шаблоны: ${stats.templates||0} · Версии: ${stats.versions||0} · Избранное: ${stats.favorites||0}</p>
</article>

<article class="item admin-section">
  <h3>Ошибки и вызовы AI (последние)</h3>
  <div class="admin-table-wrap"><table class="admin-table"><thead><tr><th>Время</th><th>Провайдер</th><th>Модель</th><th>Статус</th><th>мс</th><th>Ошибка</th></tr></thead>
  <tbody>${(usage||[]).map(u=>`<tr class="${u.status==="error"?"err":""}">
    <td>${esc(u.created_at)}</td><td>${esc(u.provider)}</td><td>${esc(u.model)}</td>
    <td>${esc(u.status)}</td><td>${esc(u.latency_ms)}</td><td>${esc(u.error_message||"")}</td>
  </tr>`).join("")||"<tr><td colspan='6'>Пока нет записей</td></tr>"}</tbody></table></div>
</article>

<article class="item admin-section">
  <h3>Рабочие пространства (учителя)</h3>
  ${(workspaces||[]).map(w=>`<p><b>${esc(w.teacher_name)}</b> · ${esc(w.school_name)} · ${esc(w.locality)} · ${esc((w.subjects||[]).join(", "))} <small>${esc(w.id)}</small></p>`).join("")||"<p>Нет</p>"}
</article>

<article class="item admin-section">
  <h3>Все материалы (оригиналы)</h3>
  <div class="admin-table-wrap"><table class="admin-table"><thead><tr><th>Название</th><th>Предмет</th><th>Класс</th><th>Workspace</th><th></th></tr></thead>
  <tbody>${(lessons||[]).slice(0,80).map(l=>`<tr>
    <td>${esc(l.title)}</td><td>${esc(l.subject)}</td><td>${esc(l.grade)}</td>
    <td><small>${esc(l.workspace_id)}</small></td>
    <td><button class="secondary sm" data-adm-lesson="${l.id}">Смотреть</button></td>
  </tr>`).join("")||"<tr><td colspan='5'>Нет</td></tr>"}</tbody></table></div>
  <pre id="adm-lesson-preview" class="generated hidden"></pre>
</article>

<article class="item admin-section">
  <h3>Модерация публикаций</h3>
  ${(publications||[]).map(p=>`<div class="moderation-row">
    <div><b>${esc(p.title)}</b><p>${esc(p.subject)} · ${esc(p.grade)} · ${esc(p.topic)} · <b>${esc(p.status)}</b></p></div>
    ${p.status==="pending_review"?`<div class="actions"><button class="primary sm" data-approve="${p.id}">Одобрить</button><button class="secondary sm" data-reject="${p.id}">Отклонить</button></div>`:""}
  </div>`).join("")||"<p>Нет публикаций</p>"}
</article>

<article class="item admin-section">
  <h3>Аудит действий (журнал)</h3>
  <div class="admin-table-wrap"><table class="admin-table"><thead><tr><th>Тип</th><th>Workspace</th><th>Время</th><th>Детали</th></tr></thead>
  <tbody>${(events||[]).slice(0,80).map(e=>`<tr>
    <td>${esc(e.event_type)}</td><td><small>${esc(e.workspace_id||"system")}</small></td>
    <td>${esc(e.created_at)}</td><td><small>${esc(JSON.stringify(e.details||{}))}</small></td>
  </tr>`).join("")}</tbody></table></div>
</article>`;

    // bind
    $("#adm-save-ai").onclick = async ()=>{
      try{
        await adminFetch("/api/admin/ai-config",{method:"PUT",body:JSON.stringify({
          provider: $("#adm-provider").value,
          model: $("#adm-model").value,
          timeout_seconds: +$("#adm-timeout").value,
          enabled: $("#adm-enabled").value==="1",
        })});
        toast("AI-настройки сохранены");
      }catch(e){toast(e.message)}
    };
    $("#adm-save-base").onclick = async ()=>{
      try{
        await adminFetch("/api/admin/prompts",{method:"PUT",body:JSON.stringify({base: $("#adm-base-prompt").value})});
        toast("Базовый промпт сохранён");
      }catch(e){toast(e.message)}
    };
    $("#adm-save-subjects").onclick = async ()=>{
      try{
        const subjects={};
        document.querySelectorAll("#adm-subjects [data-subj]").forEach(el=>{subjects[el.dataset.subj]=el.value});
        await adminFetch("/api/admin/prompts",{method:"PUT",body:JSON.stringify({subjects})});
        toast("Предметные промпты сохранены");
      }catch(e){toast(e.message)}
    };
    document.querySelectorAll("[data-approve],[data-reject]").forEach(b=>b.addEventListener("click",async()=>{
      const action=b.dataset.approve?"approve":"reject";
      const id=b.dataset.approve||b.dataset.reject;
      try{
        await adminFetch(`/api/admin/publications/${id}/${action}`,{method:"POST"});
        toast(action==="approve"?"Одобрено":"Отклонено");
        openAdminPanel();
      }catch(err){toast(err.message)}
    }));
    document.querySelectorAll("[data-adm-lesson]").forEach(b=>b.addEventListener("click",async()=>{
      try{
        const d=await adminFetch("/api/admin/lessons/"+b.dataset.admLesson);
        const pre=$("#adm-lesson-preview");
        pre.classList.remove("hidden");
        pre.textContent=JSON.stringify(d,null,2);
        pre.scrollIntoView({behavior:"smooth"});
      }catch(e){toast(e.message)}
    }));
    msg.textContent="Панель загружена.";
  }catch(e){
    box.classList.add("hidden");
    msg.textContent=e.message;
  }
}

$("#admin-open")&&$("#admin-open").addEventListener("click", openAdminPanel);
