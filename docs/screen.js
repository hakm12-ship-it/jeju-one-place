"use strict";
const $ = id => document.getElementById(id);
const fmt = n => n.toLocaleString("ko-KR", {maximumFractionDigits: 1});
const km = n => (n / 1000).toLocaleString("ko-KR", {maximumFractionDigits: 2});
const option = (value, label) => new Option(label, value);
let catalog, result, shown, revision = 0;
const request = async (path, body) => {
  if (window.publicComparison) return window.publicComparison(path, body);
  const response = await fetch(path, body ? {
    method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)
  } : {});
  const data = await response.json();
  if (!response.ok) throw Error(data.error || "자료를 열 수 없습니다.");
  return data;
};
function element(tag, value, cls) {
  const e = document.createElement(tag);
  if (value !== undefined) e.textContent = value;
  if (cls) e.className = cls;
  return e;
}
function setHomes(checked = [], extra = {}) {
  $("centerAddress").textContent = catalog[$("village").value].center_address;
  const box = $("onsite");
  box.replaceChildren();
  $("extra").replaceChildren();
  for (const h of catalog[$("village").value].homes) {
    const label = element("label", undefined, "check");
    const input = document.createElement("input");
    input.type = "checkbox"; input.value = h.id; input.checked = checked.includes(h.id);
    label.append(input, document.createTextNode(h.name), element("span", fmt(h.units) + "세대"));
    input.onchange = reload;
    box.append(label);
    const meters = document.createElement("input");
    meters.type = "number"; meters.min = 0; meters.max = 20000;
    meters.dataset.home = h.id; meters.value = extra[h.id] ?? ""; meters.placeholder = "m";
    meters.onchange = reload;
    const field = element("label", h.name);
    field.append(meters); $("extra").append(field);
  }
}
function state() {
  return {village: $("village").value, goal: document.querySelector('[name="goal"]:checked').value,
    center: $("center").checked, threshold: +$("threshold").value, onsite: [...$("onsite").querySelectorAll("input:checked")].map(e => e.value),
    extra: Object.fromEntries([...$("extra").querySelectorAll("input")].filter(e=>e.value!=="").map(e=>[e.dataset.home,+e.value]))};
}
function setForm(r) {
  $("village").value = r.village;
  document.querySelector('[name="goal"][value="' + r.goal + '"]').checked = true;
  if (![...$("threshold").options].some(o => +o.value === r.threshold))
    $("threshold").add(option(r.threshold, fmt(r.threshold) + "m 이상"));
  $("threshold").value = r.threshold;
  $("center").checked = r.center;
  setHomes(r.onsite, r.extra);
}
function fail(error) { $("error").hidden = false; $("error").textContent = error.message; }
async function reload() {
  const seq = ++revision;
  $("csv").disabled = true;
  $("print").disabled = true;
  $("answer").hidden = true; $("error").hidden = true;
  try {
    const r = await request("/api/compare", state());
    if (seq === revision) display(r);
  } catch (e) { if (seq === revision) fail(e); }
}
function display(r) {
  result = r; shown = r.candidates[0].id;
  $("csv").disabled = false;
  $("print").disabled = false;
  const tops = r.candidates.filter(c => r.winners.includes(c.id));
  const t = tops[0];
  $("area").textContent = r.district + " " + r.village + "  /  " + (r.goal === "reach" ? "혜택 세대 수 기준" : "전체 단축 거리 기준");
  $("winner").textContent = tops.length > 1 ? tops.length + "곳 공동 1위" : t ? t.name : "기준을 충족한 후보가 없습니다";
  $("verdict").textContent = !t ? (r.candidates.every(c => c.reduced === 0) ?
    "현재 조건에서는 어느 후보를 추가해도 등록 " + fmt(r.units) + "세대의 배출길이 더 짧아지지 않습니다." :
    "선택한 거리 문턱을 넘는 세대가 없습니다. 더 낮은 문턱에서 비교할 수 있습니다.") :
    (tops.length > 1 ? "공동 1위 · " : "") + (r.goal === "reach" ? "등록 " + fmt(r.units) + "세대 중 " + fmt(t.reach) + "세대의 편도 배출길이 짧아집니다." :
      "등록 세대가 한 번씩 배출할 때 편도 거리가 합계 " + km(t.total) + "km 줄어듭니다.");
  const assumptions = catalog[r.village].homes.filter(h => r.onsite.includes(h.id)).map(h => h.name);
  $("scope").textContent = "공동주택 " + r.homes + "개 주소 · 등록 " + r.units + "세대 · 과거 후보 " + r.candidates.length +
    "곳 · 기준 클린하우스 " + r.present + "곳 · 마을 도움센터 " + (r.center ? "포함" : "제외") + "  |  " + (assumptions.length ? "자체 수거함 가정: " + assumptions.join(", ") : "자체 수거함 가정 없음") +
    Object.entries(r.extra).map(([id,m])=>" · 추가 배출장 " + catalog[r.village].homes.find(h=>h.id===id).name + "에서 " + m + "m").join("") +
    " · 혜택 집계: " + (r.threshold ? r.threshold + "m 이상" : "0m 초과");
  drawTable();
  details();
  const scenarios = $("centerResults");
  scenarios.replaceChildren();
  for (const s of r.center_comparison) {
    const row = element("div", undefined, "scenario" + (s.included === r.center ? " active" : ""));
    row.append(element("b", s.included ? "센터 이용 가능" : "센터 제외"),
      element("span", s.names.length ? s.names.join(" · ") : "추가 효과가 있는 후보 없음"),
      element("strong", r.goal === "reach" ? fmt(s.value) + "세대" : km(s.value) + " km"));
    scenarios.append(row);
  }
  const field = $("field");
  field.replaceChildren();
  for (const f of r.field_checks || []) {
    const p = element("p", f.name + "에 자체 수거함이 있다고 가정했습니다. " +
      (f.winners.length ? "이때 1위는 ‘" + f.winners.join(" · ") + "’입니다." : "이때 개선 효과가 있는 후보가 사라집니다."));
    if (f.same_through_m > 0)
      p.append(" 다른 배출장까지 편도가 " + fmt(f.same_through_m) + "m 이내여도 같은 결과입니다.");
    const b = element("button", "이 가정 적용", "sub");
    b.onclick = () => { setHomes([...r.onsite, f.id], r.extra); reload(); };
    p.append(" ", b); field.append(p);
  }
  if (!field.childElementCount)
    field.textContent = r.onsite.length === r.homes ? "모든 주소에 자체 수거함이 있다는 가정입니다." : "나머지 주소에 한 곳씩 자체 수거함을 가정해도 현재 1위 집합은 같습니다.";
}
function drawTable() {
  const box = $("rank"); box.replaceChildren();
  const head = element("div", undefined, "rankitem rankhead");
  for (const [i,name] of ["후보 위치", "혜택 세대", "단축 합계¹"].entries()) head.append(element("span", name, i ? "ranknum" : ""));
  box.append(head);
  const metric = result.goal === "reach" ? "reach" : "total";
  for (const c of result.candidates) {
    const b = element("button", undefined, "rankitem" + (c.id === shown ? " sel" : ""));
    b.setAttribute("aria-pressed", String(c.id === shown));
    const name = element("strong", c.name);
    if (result.winners.includes(c.id)) name.append(element("span", result.winners.length > 1 ? "공동 1위" : "1위", "rank-tag"));
    const bar = element("span", undefined, "rankbar");
    bar.style.width = (100*c[metric] / (result.candidates[0][metric] || 1)) + "%"; name.append(bar);
    b.append(name, element("span", fmt(c.reach) + "세대", "ranknum"), element("span", km(c.total) + " km", "ranknum"));
    b.onclick = () => { shown = c.id; drawTable(); details(); };
    box.append(b);
  }
  box.append(element("small","¹ 단축 거리 × 등록 세대 수의 합. 각 세대가 한 번씩 배출하는 경우입니다.","note"));
}
function details() {
  const c = result.candidates.find(c => c.id === shown);
  $("detailname").textContent = c.name;
  $("detailrows").replaceChildren();
  c.details.forEach((d,i) => {
    const tr = document.createElement("tr");
    const values = [(i+1) + "  " + d.name, d.units, fmt(d.center_m) + "m", fmt(d.baseline) + "m", fmt(d.after) + "m", fmt(d.saved) + "m"];
    for (const v of values) tr.append(element("td", v));
    $("detailrows").append(tr);
  });
  $("detailnote").textContent = "짧아진 " + c.reduced + "세대의 평균 단축 거리 " + fmt(c.mean) + "m. 기준 거리와 후보까지의 거리 중 짧은 값을 적용했습니다. 위치도는 실제 경·위도를 단순화한 그림입니다. CSV에서 각 경로의 거리를 확인할 수 있습니다.";
  const svg = $("map"); svg.replaceChildren();
  const points = [...c.details.map(d => d.xy), c.xy, ...c.details.map(d => d.facility.xy).filter(Boolean)];
  const xs=points.map(p=>p[0]*Math.cos(points[0][1]*Math.PI/180)), ys=points.map(p=>p[1]);
  const xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(...ys), ymax=Math.max(...ys);
  const s=Math.min(300/(xmax-xmin || .00001),133/(ymax-ymin || .00001));
  const positions=points.map((_,i)=>[190+(xs[i]-(xmin+xmax)/2)*s,95-(ys[i]-(ymin+ymax)/2)*s]);
  function shape(tag,attrs,txt) {
    const n=document.createElementNS("http://www.w3.org/2000/svg",tag);
    for(const [key,val] of Object.entries(attrs)) n.setAttribute(key,val);
    if(txt !== undefined)n.textContent=txt;
    svg.append(n); return n;
  }
  for(let x=0;x<=380;x+=34)shape("line",{x1:x,x2:x,y1:0,y2:190,stroke:"#dce4d7"});
  for(let y=0;y<=190;y+=34)shape("line",{x1:0,x2:380,y1:y,y2:y,stroke:"#dce4d7"});
  shape("text",{x:12,y:20,fill:"#5c7165","font-size":12},"↑ 북");
  for(let i=c.details.length+1;i<positions.length;i++){const [x,y]=positions[i];shape("rect",{x:x-5,y:y-5,width:10,height:10,fill:"#596774"});}
  c.details.forEach((d,i)=>{const [x,y]=positions[i];shape("circle",{cx:x,cy:y,r:9,fill:"#287252",stroke:"white"});shape("text",{x,y:y+4,fill:"white","font-size":11,"text-anchor":"middle"},String(i+1));});
  const [x,y]=positions[c.details.length];
  shape("path",{d:"M "+x+" "+(y-10)+" l 9 10 -9 10 -9 -10 z",fill:"#be542d",stroke:"white"});
}
if ($("askform")) $("askform").onsubmit = async e => {
  e.preventDefault(); const seq = ++revision;
  $("askbtn").disabled = true; $("answer").hidden = false; $("error").hidden = true;
  $("answer").textContent = "Claude가 질문을 읽고 비교 조건을 선택하고 있습니다…";
  try {
    const response = await request("/api/ask", {question:$("question").value, state:state()});
    if (seq !== revision) return;
    if(response.result){ setForm(response.result); display(response.result); }
    $("answer").replaceChildren(element("b",response.message));
    if(response.steps) $("answer").append(element("small",response.model + " · " + response.steps.join(" → ")));
  } catch (err) { if(seq === revision) $("answer").textContent = err.message; }
  finally { $("askbtn").disabled = false; }
};
$("csv").onclick=()=>{
  if(!result)return;
  const rows=[["마을","후보 코드","후보","주소","등록 세대","공개 클린하우스","공개 클린하우스 m","마을 도움센터 주소","도움센터까지 m","도움센터 이용 가정","단지 내 배출 가정","추가 배출장 m","적용 기준 배출장","적용 기준 m","후보까지 m","추가 후 m","단축 m","혜택 집계 문턱 m","혜택 해당"]];
  for(const c of result.candidates) for(const d of c.details)rows.push([result.village,c.id,c.name,d.name,d.units,d.clean_name,d.reference,result.center_address,d.center_m,result.center?"예":"아니오",result.onsite.includes(d.id)?"예":"아니오",result.extra[d.id]??"",d.facility.name,d.baseline,d.route,d.after,d.saved,result.threshold,d.qualifies?"예":"아니오"]);
  const csv=rows.map(row=>row.map(v=>'"'+String(v).replaceAll('"','""')+'"').join(",")).join("\r\n");
  const link=element("a");link.href=URL.createObjectURL(new Blob(["\ufeff",csv],{type:"text/csv;charset=utf-8"}));
  link.download=result.village+"-후보별-보행거리.csv";link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000);
};
$("print").onclick=()=>window.print();
$("reset").onclick=()=>{setForm({village:$("village").value,goal:"reach",threshold:0,onsite:[],center:true});reload();};
$("center").onchange=reload;
$("village").onchange=()=>{setHomes();reload();};
$("threshold").onchange=reload;
for(const r of document.querySelectorAll('[name="goal"]'))r.onchange=reload;
(async()=>{try{catalog=await request("/api/catalog");for(const [name,d] of Object.entries(catalog))$("village").add(option(name,d.district+" "+name));setHomes();await reload();}catch(e){fail(e);}})();

