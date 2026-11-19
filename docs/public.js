"use strict";
const demoFiles = new Map();
async function loadDemoFile(name) {
  if (!demoFiles.has(name)) {
    const loading = fetch("./data/" + name + ".json").then(response => {
      if (!response.ok) throw Error("분석 자료를 불러오지 못했습니다. 잠시 후 다시 시도하세요.");
      return response.json();
    }).catch(error => {
      demoFiles.delete(name);
      throw error;
    });
    demoFiles.set(name, loading);
  }
  return demoFiles.get(name);
}

window.publicComparison = async function(path, state) {
  const registry = await loadDemoFile("catalog");
  if (path === "/api/catalog") return registry;
  if (path !== "/api/compare") throw Error("자유 질문은 센터 실행판에서 이용하세요.");
  const entry = registry[state.village];
  const mask = entry.homes.reduce((value, home, index) =>
    state.onsite.includes(home.id) ? value | (1 << index) : value, 0);
  const group = await loadDemoFile(entry.file + "-" + mask);
  const run = group[[state.goal, state.threshold, Number(state.center)].join("-")];
  if (!run) throw Error("비교 조건을 다시 선택하세요.");
  return run;
};

function openExample(village, goal, scroll) {
  if (!document.getElementById("village").value) return;
  setForm({village, goal, threshold: 0, onsite: [], extra: {}, center: true});
  reload().then(() => {
    if (scroll || window.matchMedia("(max-width: 800px)").matches)
      document.getElementById("area").scrollIntoView({block: "center"});
  });
}
document.getElementById("case-geum").onclick = () => openExample("금능리", "reach", false);
document.getElementById("case-yusu").onclick = () => openExample("유수암리", "distance", false);
document.getElementById("replay").onclick = () => openExample("금능리", "reach", true);
