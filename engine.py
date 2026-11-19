"""모든 점수와 설명 수치는 동일한 보행거리 스냅샷에서 산출한다."""
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VILLAGES = json.loads((ROOT / "data/villages.json").read_text(encoding="utf-8"))
GOALS = {"reach": "더 많은 세대", "distance": "모두의 거리 합계"}


def catalog():
    return {name: {"district": d["district"], "center_address": d["center"]["address"], "homes": [
        {"id": h["id"], "name": h["name"], "units": h["units"]} for h in d["homes"]
    ]} for name, d in VILLAGES.items()}


def compare(village="유수암리", goal="reach", threshold=0, onsite=None, extra=None, center=False):
    if not isinstance(village, str) or village not in VILLAGES or goal not in GOALS:
        raise ValueError("목록에 있는 마을과 비교 기준을 선택하세요.")
    if type(threshold) is not int or not 0 <= threshold <= 5000:
        raise ValueError("단축 기준은 0~5,000m 사이의 정수로 입력하세요.")
    if type(center) is not bool:
        raise ValueError("마을 도움센터 이용 조건을 확인하세요.")
    d = VILLAGES[village]
    homes = d["homes"]
    if onsite is None:
        onsite = []
    if not isinstance(onsite, list) or any(i not in [h["id"] for h in homes] for i in onsite):
        raise ValueError("선택한 마을의 공동주택 주소를 확인하세요.")
    onsite = sorted(set(onsite))
    if extra is None:
        extra = {}
    if not isinstance(extra, dict) or any(
        k not in {h["id"] for h in homes} or type(v) is not int or not 0 <= v <= 20000
        for k, v in extra.items()
    ):
        raise ValueError("추가 배출장 거리는 주소별 0~20,000m 사이의 정수로 입력하세요.")
    candidates = []
    for j, place in enumerate(d["candidates"]):
        details = []
        for h in homes:
            base, facility = h["base"], h["facility"]
            if center and h["center_m"] < base:
                base, facility = h["center_m"], d["center"]
            if h["id"] in extra and extra[h["id"]] < base:
                base, facility = extra[h["id"]], {"name": "직접 입력한 다른 배출장", "xy": None}
            if h["id"] in onsite:
                base, facility = 0, {"name": "단지 내 수거함 가정", "xy": h["xy"]}
            distance = h["candidate_m"][j]
            after = min(base, distance)
            saved = round(base - after, 1)
            details.append(dict(id=h["id"], name=h["name"], xy=h["xy"], units=h["units"],
                                baseline=base, reference=h["base"], clean_name=h["facility"]["name"],
                                facility=facility, center_m=h["center_m"], route=distance,
                                after=after, saved=saved, qualifies=saved > 0 and saved >= threshold))
        reduced = sum(r["units"] for r in details if r["saved"] > 0)
        reach = sum(r["units"] for r in details if r["qualifies"])
        total = round(sum(r["saved"] * r["units"] for r in details), 1)
        candidates.append(dict(**place, reach=reach, total=total, reduced=reduced,
                               mean=round(total/reduced, 1) if reduced else 0, details=details))
    metric = "reach" if goal == "reach" else "total"
    candidates.sort(key=lambda x: -x[metric])
    best = candidates[0][metric]
    winners = [c["id"] for c in candidates if c[metric] == best and best > 0]
    return dict(village=village, district=d["district"], goal=goal, threshold=threshold, onsite=onsite, extra=extra,
                center=center, center_address=d["center"]["address"],
                homes=len(homes), units=sum(h["units"] for h in homes), present=d["present_count"],
                obtained=d["obtained"], max_snap=d["max_snap"], candidates=candidates, winners=winners)


def field_checks(result):
    """한 번에 한 주소의 단지 내 배출 가정만 바꿔 1위 집합의 변화를 검증한다."""
    findings = []
    for addr in VILLAGES[result["village"]]["homes"]:
        if addr["id"] in result["onsite"]:
            continue
        variant = compare(result["village"], result["goal"], result["threshold"], result["onsite"] + [addr["id"]], result["extra"], result["center"])
        if set(result["winners"]) != set(variant["winners"]):
            names = [c["name"] for c in variant["candidates"] if c["id"] in variant["winners"]]
            # 정수 m 입력에서 0m와 같은 1위 집합이 유지되는 첫 연속 구간만 제시한다.
            row = next(d for d in result["candidates"][0]["details"] if d["id"] == addr["id"])
            same_through = 0
            for meters in range(1, math.ceil(row["baseline"]) + 1):
                extra = {**result["extra"], addr["id"]: meters}
                scenario = compare(result["village"], result["goal"], result["threshold"],
                                   result["onsite"], extra, result["center"])
                if set(scenario["winners"]) != set(variant["winners"]):
                    break
                same_through = meters
            findings.append({"id": addr["id"], "name": addr["name"], "winners": names,
                             "same_through_m": same_through})
    return findings


def center_comparison(result):
    """다른 조건을 고정하고 마을 도움센터의 이용 가능 조건만 바꾼다."""
    inputs = {k: result[k] for k in ("village", "goal", "threshold", "onsite", "extra")}
    other = compare(**inputs, center=not result["center"])
    def summary(run):
        best = run["candidates"][0]
        return {"included": run["center"],
                "names": [c["name"] for c in run["candidates"] if c["id"] in run["winners"]],
                "value": best["reach"] if run["goal"] == "reach" else best["total"]}
    return sorted([summary(result), summary(other)], key=lambda s: s["included"])

