"""
公開データを定期取得して蓄積するサンプル。

このデモが示していること:
  1. 決まった時刻に無人で動く（GitHub Actions）
  2. 想定と違う形のデータが来たら「黙って続けず落とす」
  3. 取得した値の品質を数値で記録する（欠損率）
  4. 全レコードに取得元と取得時刻を残す（あとから監査できる）

3 が最重要。エラーを出さずに壊れる不具合は、
「正しい出力とは何か」を先に決めておかないと検出できない。
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

# ── 設定 ──────────────────────────────────────────────
# 気象庁の公開JSON（認証不要）。東京地方の予報。
SOURCE_URL = "https://www.jma.go.jp/bosai/forecast/data/forecast/130000.json"
SOURCE_NAME = "気象庁 予報データ"

JST = timezone(timedelta(hours=9))
ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA_PATH = ROOT / "docs" / "data.json"
REPORT_PATH = ROOT / "docs" / "quality_report.md"

MAX_RECORDS = 180  # 保持する日数の上限

# 必須項目。ここが欠けたら「取れた」と見なさない。
REQUIRED_FIELDS = ("date", "weather", "temp_max", "temp_min")

USER_AGENT = "auto-collect-demo/1.0 (portfolio sample; contact via GitHub issues)"


class SchemaChangedError(RuntimeError):
    """取得元の構造が想定と変わったときに送出する。

    近い名前のキーで処理を続けると、間違ったデータが
    正しい顔をして保存される。それが一番まずいので明示的に落とす。
    """


# ── 取得 ──────────────────────────────────────────────
def fetch(url: str) -> list:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as res:
        if res.status != 200:
            raise RuntimeError(f"想定外のHTTPステータス: {res.status}")
        return json.loads(res.read().decode("utf-8"))


# ── 抽出 ──────────────────────────────────────────────
def extract(raw: list) -> dict:
    """必要な値だけを取り出す。構造が違えば SchemaChangedError。"""
    try:
        series = raw[0]["timeSeries"]
        weather_block = series[0]
        dates = weather_block["timeDefines"]
        weathers = weather_block["areas"][0]["weathers"]
    except (KeyError, IndexError, TypeError) as e:
        raise SchemaChangedError(f"天気ブロックの構造が想定と違います: {e}") from e

    if not dates or not weathers:
        raise SchemaChangedError("天気ブロックが空です")

    temp_max = temp_min = None
    # 気温は別のtimeSeriesに入っている。無い日もあるので必須にはしない。
    for block in series:
        areas = block.get("areas", [])
        if not areas:
            continue
        area = areas[0]
        if "tempsMax" in area or "temps" in area:
            temps = area.get("tempsMax") or area.get("temps") or []
            nums = [t for t in temps if t not in ("", None)]
            if nums:
                temp_max = nums[0]
        if "tempsMin" in area:
            nums = [t for t in area["tempsMin"] if t not in ("", None)]
            if nums:
                temp_min = nums[0]

    return {
        "date": dates[0][:10],
        "weather": weathers[0],
        "temp_max": temp_max,
        "temp_min": temp_min,
        "source": SOURCE_NAME,
        "source_url": SOURCE_URL,
        "fetched_at": datetime.now(JST).isoformat(timespec="seconds"),
    }


# ── 蓄積 ──────────────────────────────────────────────
def load_existing() -> list:
    if not DATA_PATH.exists():
        return []
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # 壊れたファイルを黙って上書きしない
        raise RuntimeError(f"{DATA_PATH} が壊れています。手動で確認してください。")


def upsert(records: list, new: dict) -> list:
    """同じ日付があれば置き換える。無ければ足す。"""
    merged = [r for r in records if r.get("date") != new["date"]]
    merged.append(new)
    merged.sort(key=lambda r: r.get("date", ""))
    return merged[-MAX_RECORDS:]


# ── 品質チェック ───────────────────────────────────────
def build_quality_report(records: list) -> str:
    total = len(records)
    lines = [
        "# 品質レポート",
        "",
        f"最終更新: {datetime.now(JST).isoformat(timespec='seconds')}",
        f"取得元: [{SOURCE_NAME}]({SOURCE_URL})",
        "",
        f"- 保持レコード数: **{total}**",
        "",
        "## 必須項目の充足率",
        "",
        "| 項目 | 非null件数 | 充足率 |",
        "|---|---|---|",
    ]
    for field in REQUIRED_FIELDS:
        filled = sum(1 for r in records if r.get(field) not in (None, ""))
        rate = (filled / total * 100) if total else 0.0
        lines.append(f"| `{field}` | {filled} / {total} | {rate:.1f}% |")

    lines += [
        "",
        "## 既知の制約",
        "",
        "- 気温は予報に含まれない日があり、その場合 `temp_max` / `temp_min` は空になります。",
        "- 保持件数の上限は直近 %d 件です。" % MAX_RECORDS,
        "",
        "この数値が下がっていたら、取得元の仕様が変わった可能性があります。",
    ]
    return "\n".join(lines) + "\n"


# ── 実行 ──────────────────────────────────────────────
def main() -> int:
    print(f"取得開始: {SOURCE_URL}")
    raw = fetch(SOURCE_URL)

    new = extract(raw)
    print(f"取得: {new['date']} / {new['weather']}")

    missing = [f for f in ("date", "weather") if not new.get(f)]
    if missing:
        raise SchemaChangedError(f"必須項目が空です: {missing}")

    records = upsert(load_existing(), new)

    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    DATA_PATH.write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    REPORT_PATH.write_text(build_quality_report(records), encoding="utf-8")

    print(f"保存: {DATA_PATH.name} ({len(records)}件) / {REPORT_PATH.name}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SchemaChangedError as e:
        print(f"[構造の変化を検出] {e}", file=sys.stderr)
        print("近い名前のキーで処理を続けると、誤ったデータが保存されます。"
              "ここで停止します。", file=sys.stderr)
        sys.exit(2)
