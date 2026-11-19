"""공개 원본 CSV에서 세 마을의 후보와 보행거리 분석 자료를 만든다."""
import argparse
import csv
import hashlib
import json
import math
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
TOWNS = {"유수암리": "애월읍", "금능리": "한림읍", "봉성리": "애월읍"}
RADIUS = 3800
ENDPOINT = "https://routing.openstreetmap.de/routed-foot/table/v1/driving/"


def read_rows(filename):
    with (DATA / "sources" / filename).open(encoding="cp949", newline="") as src:
        return list(csv.DictReader(src))


def coord(row, housing=False):
    suffix = "" if housing else " 좌표"
    return (float(row["경도" + suffix]), float(row["위도" + suffix]))


def meters(a, b):
    x1, y1, x2, y2 = map(math.radians, (*a, *b))
    h = math.sin((y2-y1)/2)**2 + math.cos(y1)*math.cos(y2)*math.sin((x2-x1)/2)**2
    return 12742000 * math.asin(math.sqrt(h))


def village_inputs(village, old, new, housing):
    district = TOWNS[village]
    address_prefix = f"제주특별자치도 제주시 {district} "
    area = district + " " + village + " "
    homes = defaultdict(int)
    for r in housing:
        if area in r["지번주소"] and r["위도"].strip() and r["경도"].strip():
            homes[(coord(r, True), r["도로명주소"].removeprefix(address_prefix))] += int(r["세대수"])
    starts = [dict(id=f"h{i}", xy=xy, name=name, units=n)
              for i, ((xy, name), n) in enumerate(homes.items()) if n > 0]
    present = []
    for r in new:
        if int(r["종량제 수거함 수"] or 0) <= 0:
            continue
        xy = coord(r)
        if min(meters(h["xy"], xy) for h in starts) <= RADIUS:
            name = r["도로명 주소"].strip().removeprefix("제주특별자치도 제주시 ")
            if not name:
                name = r["단지 명"]
            present.append(dict(xy=xy, name=name))
    candidates = []
    for r in old:
        if (area not in r["지번 주소"] or r["구분 명"] != "클린하우스"
                or int(r["종량제 수거함 수"] or 0) <= 0):
            continue
        xy = coord(r)
        if any(meters(xy, s["xy"]) <= 40 for s in present):
            continue
        candidates.append(dict(id=r["데이터 코드"], xy=xy, name=r["단지 명"]))
    return starts, candidates, present


def get_distances(village, starts, targets, refresh):
    """캐시의 입력 좌표까지 대조한다. 서버의 경로 갱신은 명시적으로 요청한다."""
    directory = DATA / "routes"
    directory.mkdir(exist_ok=True)
    path = directory / (village + ".json")
    coordinates = [list(r["xy"]) for r in starts + targets]
    if path.exists() and not refresh:
        cache = json.loads(path.read_text(encoding="utf-8"))
        if cache["coordinates"] != coordinates or cache["start_count"] != len(starts):
            raise ValueError(f"{village} 보행거리 캐시와 원본 좌표가 다릅니다.")
        return cache
    rows = [[] for _ in starts]
    snaps = []
    for i in range(0, len(targets), 70):
        group = targets[i:i+70]
        pts = [r["xy"] for r in starts + group]
        loc = ";".join(f"{x},{y}" for x, y in pts)
        srcs = ";".join(map(str, range(len(starts))))
        dsts = ";".join(map(str, range(len(starts), len(pts))))
        url = ENDPOINT + loc + f"?sources={srcs}&destinations={dsts}&annotations=distance"
        req = urllib.request.Request(url, headers={"User-Agent": "Jeju-OnePlace-Research/1.0 (local civic planning prototype)"})
        time.sleep(1.1)
        with urllib.request.urlopen(req, timeout=40) as response:
            matrix = json.load(response)
        if matrix["code"] != "Ok":
            raise RuntimeError(matrix["code"])
        for row, part in zip(rows, matrix["distances"], strict=True):
            row.extend(part)
        source_snaps = [p["distance"] for p in matrix["sources"]]
        snaps.extend(p["distance"] for p in matrix["destinations"])
    from datetime import datetime, timezone
    cache = dict(coordinates=coordinates, start_count=len(starts), distances=rows,
                 source_snaps=source_snaps, target_snaps=snaps,
                 obtained=datetime.now(timezone.utc).date().isoformat())
    path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    return cache


def build(refresh):
    old, new, homes = map(read_rows, ("hub-1335.csv", "clean-2025.csv", "homes-2025.csv"))
    centers = json.loads((DATA / "sources/center-locations.json").read_text(encoding="utf-8"))
    data = {}
    for village, district in TOWNS.items():
        starts, candidates, present = village_inputs(village, old, new, homes)
        cache = get_distances(village, starts, candidates + present, refresh)
        center = centers[village]
        center_routes = get_distances(village + "-도움센터", starts, [center], refresh)
        n = len(candidates)
        for i, home in enumerate(starts):
            row = cache["distances"][i]
            if len(row) != n + len(present) or any(v is None for v in row):
                raise ValueError(f"{village} 경로 누락. 연결 상태를 점검하세요.")
            j = min(range(len(present)), key=lambda j: row[n+j])
            home.update(base=row[n+j], facility=present[j], candidate_m=row[:n])
            distance = center_routes["distances"][i][0]
            if distance is None or distance < 0:
                raise ValueError(f"{village} 도움센터 보행경로를 확인하세요.")
            home["center_m"] = distance
            if home["base"] >= RADIUS - cache["source_snaps"][i] - max(cache["target_snaps"]):
                raise ValueError("기준 지점 탐색 반경을 확장해야 합니다.")
        data[village] = dict(district=district, homes=starts, candidates=candidates, center=center,
                             present_count=len(present), max_snap=round(max(cache["target_snaps"] + cache["source_snaps"]), 1),
                             obtained=cache["obtained"])
    out = DATA / "villages.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    for p in sorted((DATA / "sources").glob("*.csv")):
        print(p.name, hashlib.sha256(p.read_bytes()).hexdigest())
    for name, d in data.items():
        print(name, len(d["homes"]), sum(h["units"] for h in d["homes"]), len(d["candidates"]), d["present_count"], d["max_snap"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true", help="온라인 보행거리 갱신")
    build(parser.parse_args().refresh)
