"""원본에서 결과를 다시 만들고, 점수 계산과 유수암리 대조값을 확인한다."""
import hashlib
import itertools
import json
from pathlib import Path

import prepare
from engine import VILLAGES, compare, field_checks, center_comparison

HASHES = {
    "center-locations.json": "6a716e97db98dd572062a64a03276206c4640c112f8ce35a291bdfb99c4181e9",
    "clean-2025.csv": "1ae1ab16de1274580791f6f67c99e614ee0b0291af858172da5617e75ba9693c",
    "homes-2025.csv": "d6006e4c194897802d74d2c82b6f90150faa97a6ef17f9775138b43a9b00209b",
    "hub-1335.csv": "72a860d0507164198e9eec797c8f616db7dffa6d5c8cff721d7f3668a2fbdd1d",
}


def verify():
    for filename, digest in HASHES.items():
        assert hashlib.sha256((prepare.DATA / "sources" / filename).read_bytes()).hexdigest() == digest
    prepare.build(False)
    assert VILLAGES == json.loads((prepare.DATA / "villages.json").read_text(encoding="utf-8"))
    reference = {"거문덕이": (40, 4270.4), "경로당옆": (28, 7523.2),
                 "광상로 310 동측도로": (28, 51920.4), "보건소(유수암평화길14-2)맞은편": (28, 40532.8)}
    for c in compare()["candidates"]:
        assert (c["reach"], c["total"]) == reference[c["name"]]
    case = compare("유수암리", "distance")
    assert case["candidates"][0]["details"][-1]["after"] == 369.5
    assert next(f for f in field_checks(case) if f["name"] == "광상로 344")["winners"] == ["경로당옆"]
    assert len(compare("봉성리")["winners"]) == 2
    included = compare("유수암리", "distance", center=True)
    assert [s["value"] for s in center_comparison(included)] == [51920.4, 30618.0]
    assert len(compare("유수암리", "reach", center=True)["winners"]) == 3
    assert included["candidates"][0]["details"][-1]["baseline"] == 1463
    assert field_checks(included)[-1]["winners"] == ["경로당옆"]
    assert field_checks(included)[-1]["same_through_m"] == 638
    assert compare("유수암리", "distance", extra={"h2": 638}, center=True)["candidates"][0]["name"] == "경로당옆"
    assert compare("유수암리", "distance", extra={"h2": 639}, center=True)["candidates"][0]["name"] == "광상로 310 동측도로"
    for town in ("금능리", "봉성리"):
        assert not compare(town, "distance", center=True)["winners"]
    overridden = compare("유수암리", "distance", extra={"h2": 500}, center=True)
    assert overridden["candidates"][0]["details"][-1]["baseline"] == 500
    count = 0
    for name, d in VILLAGES.items():
        ids = [h["id"] for h in d["homes"]]
        for n in range(len(ids)+1):
            for group in itertools.combinations(ids, n):
                for goal, threshold, center in itertools.product(("reach", "distance"), (0, 100, 300, 500, 5000), (False, True)):
                    r = compare(name, goal, threshold, list(group), center=center)
                    for c in r["candidates"]:
                        assert 0 <= c["reach"] <= c["reduced"] <= r["units"]
                        assert all(0 <= row["after"] <= row["baseline"] for row in c["details"])
                        assert c["reach"] == sum(row["units"] for row in c["details"]
                                                 if row["saved"] > 0 and row["saved"] >= threshold)
                    metric = "total" if goal == "distance" else "reach"
                    scores = [c[metric] for c in r["candidates"]]
                    assert scores == sorted(scores, reverse=True)
                    assert set(r["winners"]) == {c["id"] for c in r["candidates"] if c[metric] == max(scores) and c[metric] > 0}
                    if n == len(ids):
                        assert not r["winners"]
                    count += 1
    print(f"통과 · 입력 파일 4개, 센터 이용 비교, 유수암리 후보 대조, 현장 가정 순위 역전, 봉성리 공동 1위, {count}개 조건 조합")


if __name__ == "__main__":
    verify()

