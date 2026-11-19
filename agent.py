"""Claude가 비교 조건을 계획한다. 서버가 검증 후 거리 비교 도구를 실행한다."""
import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request

from engine import catalog, compare

SYSTEM = """당신은 제주 주민의 클린하우스 비교 질문을 구조화하는 도구 호출 계획기다. 사용자 질문에는 직접 답하지 않는다.
백엔드 compare 도구에는 모든 지원 마을의 기준 거리, 후보까지의 보행거리, 세대수가 이미 있다.
도구 실행 전 입력에 거리표가 보이지 않아도 계산할 수 있다. '어디', '왜 달라', '왜 1위'는 정상 비교 요청이다.
예: '유수암리에서 두 기준의 1위가 왜 달라?' → village=유수암리, goal=both, clarification="".
예: '광상로 344에 자체 수거함이 있다면 전체 거리가 가장 줄어드는 곳은?' → 유수암리의 해당 주소 id를 onsite에 담고 goal=distance.
제공한 마을·주소·목표만 쓴다.
현재 화면의 조건을 유지하되 질문에서 변경한 항목을 반영한다. 마을을 변경하면 현장 조건은 초기화한다.
center는 마을 도움센터를 사용할 수 있다는 가정이면 include, 제외이면 exclude다. 이용 전후·여부에 따라
결과가 어떻게 달라지는지 묻거나 '도움센터를 포함하면 어떻게 달라져?'라면 compare를 선택한다.
세 곳의 마을 도움센터까지의 보행거리가 이미 있다. 도움센터를 묻는 질문에는 수동 입력을 요구하지 않는다.
reach는 기준 이상 편도가 짧아지는 세대 수, distance는 등록 세대수로 가중한 편도 단축 거리 합계다.
질문이 두 기준을 비교하면 both를 고른다. 현장에 단지 자체 종량제 수거함이 있다고 명시한 주소만 onsite에 추가한다.
자체 수거함이 없다고 가정하면 그 주소를 onsite에서 뺀다. 미확인 상태는 현재 입력을 유지한다.
onsite 배열에는 지원범위 homes에 있는 id(h0, h1, h2)만 쓴다. 주소 또는 동 이름을 쓰지 않는다.
주소 식별이 애매하거나 범위 밖 지역·실시간 운영·철거 사실·실제 설치 결정·근거 없는 예측을 묻는 경우
clarification에 이유와 가능한 질문을 간단히 쓴다. 정상 질문은 clarification을 빈 문자열로 쓴다.
도움센터 등 추가 배출장까지의 측정 거리 입력을 요청하면 화면의 '다른 배출장 거리' 입력란을 안내한다.
거리를 추정하거나 후보, 수치를 창작하지 않는다. 계획은 지정한 구조로만 제출한다."""
PROPERTIES = {
    "village": {"type": "string", "enum": list(catalog())},
    "goal": {"type": "string", "enum": ["reach", "distance", "both"]},
    "center": {"type": "string", "enum": ["include", "exclude", "compare"]},
    "threshold": {"type": "integer", "minimum": 0, "maximum": 5000},
    "onsite": {"type": "array", "items": {"type": "string", "enum": sorted({
        h["id"] for d in catalog().values() for h in d["homes"]
    })}},
    "clarification": {"type": "string"}
}
SCHEMA = {"type": "object", "properties": PROPERTIES, "required": list(PROPERTIES), "additionalProperties": False}


def plan(prompt):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        model = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
        body = {"model": model, "max_tokens": 550, "system": SYSTEM,
                "messages": [{"role": "user", "content": prompt}],
                "tools": [{"name": "plan_comparison", "description": "마을 비교 조건을 제출", "input_schema": SCHEMA}],
                "tool_choice": {"type": "tool", "name": "plan_comparison"}}
        req = urllib.request.Request("https://api.anthropic.com/v1/messages",
                                     data=json.dumps(body).encode(), headers={"x-api-key": key,
                                     "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=40) as res:
            blocks = json.load(res)["content"]
        return next(b["input"] for b in blocks if b["type"] == "tool_use" and b["name"] == "plan_comparison"), model
    cli = shutil.which("claude")
    if not cli:
        raise RuntimeError("Claude 연결이 없습니다. 아래 마을·기준을 선택하면 같은 계산을 이용할 수 있습니다.")
    with tempfile.TemporaryDirectory() as directory:
        proc = subprocess.run([cli, "-p", "--model", "haiku", "--system-prompt", SYSTEM,
                               "--output-format", "json", "--json-schema", json.dumps(SCHEMA, ensure_ascii=False),
                               "--tools", "", "--strict-mcp-config", "--disable-slash-commands",
                               "--setting-sources", "", "--no-session-persistence"], input=prompt,
                              capture_output=True, encoding="utf-8", cwd=directory, timeout=75)
    if proc.returncode:
        raise RuntimeError("Claude Code 연결을 확인하세요. 화면에서 직접 비교할 수 있습니다.")
    result = json.loads(proc.stdout)
    if result.get("is_error") or not isinstance(result.get("structured_output"), dict):
        raise RuntimeError("분석 조건을 해석하지 못했습니다. 질문을 구체화하거나 화면에서 선택하세요.")
    return result["structured_output"], "Claude Code · Haiku"


def ask(question, state):
    if not isinstance(question, str) or not 1 <= len(question.strip()) <= 600:
        raise ValueError("질문은 1~600자로 입력하세요.")
    current = compare(**state)
    context = {k: current[k] for k in ("village", "goal", "threshold", "onsite")}
    context["center"] = "include" if current["center"] else "exclude"
    # 화면에 제시한 정형 질문의 의미가 모델 응답에 따라 달라지지 않게 한다.
    simple = re.fullmatch(r"(?:(유수암리|금능리|봉성리)에서)?두기준의1위가왜달라(?:요)?[?.!]*",
                          re.sub(r"\s+", "", question))
    example = None
    if simple:
        village = simple.group(1) or current["village"]
        example = {**context, "village": village, "goal": "both", "clarification": "",
                   "onsite": context["onsite"] if village == current["village"] else []}
    try:
        result, model = plan(json.dumps({"질문": question, "현재조건": context, "지원범위": catalog()}, ensure_ascii=False))
    except (OSError, RuntimeError, subprocess.TimeoutExpired, ValueError, KeyError, StopIteration):
        if example is None:
            raise
        result, model = example, "로컬 예문 해석"
    if example is not None and result != example:
        result, model = example, "로컬 예문 해석"
    if set(result) != set(PROPERTIES):
        raise ValueError("질문 해석이 불완전합니다. 조건을 직접 선택하세요.")
    if result["clarification"]:
        return {"message": str(result["clarification"])[:400], "model": model}
    goals = ["reach", "distance"] if result["goal"] == "both" else [result["goal"]]
    extra = current["extra"] if current["village"] == result["village"] else {}
    mode = result["center"]
    if mode not in ("include", "exclude", "compare"):
        raise ValueError("마을 도움센터 조건을 확인하세요.")
    centers = [True, False] if mode == "compare" else [mode == "include"]
    runs = [compare(result["village"], g, result["threshold"], result["onsite"], extra, include)
            for include in centers for g in goals]
    summaries = []
    for r in runs:
        tops = [c for c in r["candidates"] if c["id"] in r["winners"]]
        names = " · ".join(c["name"] for c in tops)
        condition = "도움센터 이용 가능" if r["center"] else "도움센터 제외"
        criterion = "혜택 세대 수" if r["goal"] == "reach" else "전체 단축 거리"
        prefix = f"{condition} · {criterion} 기준"
        if tops and r["goal"] == "reach":
            summaries.append(f"{prefix}은 {names} ({tops[0]['reach']}세대)입니다.")
        elif tops:
            summaries.append(f"{prefix}은 {names} (합계 {tops[0]['total']/1000:,.2f}km)입니다.")
        else:
            summaries.append(f"{prefix}에서 개선되는 후보가 없습니다.")
    if len(centers) == 1 and len(goals) == 2 and runs[0]["winners"] != runs[1]["winners"] and runs[1]["winners"]:
        c = runs[1]["candidates"][0]
        addr = max(c["details"], key=lambda d: d["units"] * d["saved"])
        summaries.append(f"{c['name']}의 거리 단축에 가장 크게 기여한 곳은 {addr['name']}입니다. "
                         f"이 주소의 등록 {addr['units']}세대는 각각 편도 {addr['saved']:,.1f}m가 짧아집니다.")
    return {"message": " ".join(summaries), "model": model, "result": runs[0],
            "steps": ["마을·주소 목록 조회", "질문에서 비교 조건 선택", f"후보별 거리 재계산 × {len(runs)}개 조건", "결과 대조"]}

