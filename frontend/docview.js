// Отображение документа КСП/КМЖ (v2) и вспомогательные функции. Не зависит от DOM и app.js.
function dvEsc(s){return String(s??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]))}
function dvInline(s){return dvEsc(s).replace(/\*\*(.+?)\*\*/g,"<b>$1</b>")}
function dvText(text){
  const out=[];let list=false,code=false;
  const closeList=()=>{if(list){out.push("</ul>");list=false}};
  for(const line of String(text||"").split("\n")){
    if(line.trim().startsWith("```")){closeList();out.push(code?"</pre>":'<pre class="doc-code">');code=!code;continue}
    if(code){out.push(dvEsc(line)+"\n");continue}
    if(!line.trim()){closeList();continue}
    let m;
    if((m=line.match(/^\s*[-*•]\s+(.*)$/))){if(!list){out.push("<ul>");list=true}out.push("<li>"+dvInline(m[1])+"</li>");continue}
    closeList();
    if((m=line.match(/^\s*#{1,6}\s*(.*)$/))){out.push("<h4>"+dvInline(m[1])+"</h4>");continue}
    out.push("<p>"+dvInline(line)+"</p>");
  }
  closeList();if(code)out.push("</pre>");
  return out.join("");
}
function dvTable(p){
  const cell=v=>dvInline(v).replace(/\n/g,"<br>");
  return `<table class="doc-table"><thead><tr>${p.header.map(h=>`<th>${cell(h)}</th>`).join("")}</tr></thead><tbody>${
    p.rows.map(r=>`<tr>${p.header.map((_,i)=>`<td>${cell(r[i]??"")}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
}
function renderDocHtml(meta,doc){
  const head=`<h1>${dvEsc(meta.title||"КСП / КМЖ")}</h1><p class="doc-meta">${dvEsc([meta.subject,meta.grade,meta.topic].filter(Boolean).join(" · "))}</p>`;
  const body=(doc.blocks||[]).map(b=>`<h2>${dvEsc(b.heading||"—")}</h2>`+(b.parts||[]).map(p=>p.type==="table"?dvTable(p):dvText(p.text)).join("")).join("");
  return head+body;
}
function docNeedsLandscape(doc){return (doc.blocks||[]).some(b=>(b.parts||[]).some(p=>p.type==="table"&&p.header.length>=5))}
function dvTimeCol(header){
  let i=header.findIndex(h=>/(врем|time|уақыт|вақт)/i.test(h));
  return i>=0?i:header.findIndex(h=>/\((мин|min|дақ)/i.test(h));
}
function dvSumMinutes(p){
  const i=dvTimeCol(p.header);if(i<0)return null;
  let total=0;
  for(const r of p.rows){if(/(итого|всего|total|барлығы|жами)/i.test(r[0]||""))continue;const m=String(r[i]||"").match(/\d+/);if(m)total+=+m[0]}
  return total;
}
if(typeof module!=="undefined")module.exports={renderDocHtml,dvSumMinutes,dvTimeCol,docNeedsLandscape};
