#!/usr/bin/env python3
"""
GOLF STUDIO SHADOW 空き状況取得 v2 (1ヶ月分対応)

仕組み:
- STARTAPP の公開「空き候補ページ」は通常GETだと直近5日分しか返さない。
- しかし同ページの「曜日フィルタ (再表示)」を使うと、指定曜日の
  次の5回分 (約5週間先まで) が返ってくる。
- フィルタなし1回 + 曜日フィルタ6回 (日・火・水・木・金・土) を
  マージすることで、約1ヶ月分の空きを再構成できる。
  (月曜は定休日のためフィルタ選択肢に無く、取得対象外)
- 「次の候補」のページ送りはベンダー側の不具合で使えない (1970年になる)。

- ログイン不要・公開ページのみを使用
- 予約確定は公式フォーム側で行う前提 (このスクリプトは表示用データのみ)

使い方: python3 fetch_availability.py [出力先json] [取得日数=30]
"""
import json
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from http.cookiejar import CookieJar

JST = timezone(timedelta(hours=9))
SHOP = "12299"
BASE = "https://golfstudio-shadow.jp/shop/myreserve/available/index/AD:/SI:/DM:/DI:"
FORM_ACTION = "https://golfstudio-shadow.jp/shop/myreserve/available/index/AD:/SI:/DM:/DI:"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

MENUS = {
    "vip": {"label": "VIPルーム", "menu": 7, "staff": "s8"},
    "trial": {"label": "体験レッスン", "menu": 3, "staff": "s1"},
    "simulation": {"label": "シミュレーション打席", "menu": 6, "staff": "s7"},
    "lesson": {"label": "レッスン", "menu": 2, "staff": "s1"},
}

# 曜日フィルタ (sel_date2): 日=2, 火=4, 水=5, 木=6, 金=7, 土=8 (月曜は定休日で選択肢なし)
WEEKDAY_FILTERS = [2, 4, 5, 6, 7, 8]


def avail_url(menu: int, staff: str, y: int, m: int, d: int) -> str:
    return (
        f"{BASE}/year:{y}/month:{m}/day:{d}/menu:{menu}/hour:10/minute:0"
        f"/staff:{staff}/shop:{SHOP}/shop_select:/online:1/target_page:selectdate"
    )


def parse_days(html: str) -> dict:
    """{ 'YYYY/MM/DD': {'weekday': '日', 'times': [...], 'status': ''} } を返す。

    空きゼロの日は <select> が無く <dd>店舗休日</dd> のような理由テキストが
    入るため、そちらも status として拾う (無い日と区別するため)。
    """
    out = {}
    for m in re.finditer(
        r"<dt>(\d{4}/\d{2}/\d{2})\(([^)]*)\)</dt>\s*<dd>(.*?)</dd>", html, re.S
    ):
        date_label, wd, dd = m.group(1), m.group(2), m.group(3)
        sel = re.search(r"<select[^>]*>(.*?)</select>", dd, re.S)
        if sel:
            times = re.findall(r"<option value='[^']*'>(\d{2}:\d{2})</option>", sel.group(1))
            out[date_label] = {"weekday": wd, "times": times, "status": ""}
        else:
            status = re.sub(r"<[^>]+>", "", dd).strip()
            out[date_label] = {"weekday": wd, "times": [], "status": status}
    return out


def extract_form_fields(html: str) -> list:
    """selectdate フォームの送信フィールドを再現する (submitボタン類は除外)"""
    m = re.search(r'<form[^>]*name="selectdate"[^>]*>(.*?)</form>', html, re.S)
    form = m.group(1)
    fields = []
    for tag in re.finditer(r"<input[^>]*>", form):
        t = tag.group(0)
        typ = re.search(r'type="([^"]*)"', t)
        if typ and typ.group(1).lower() in ("submit", "button", "image", "reset"):
            continue
        name = re.search(r'name="([^"]*)"', t)
        if not name:
            continue
        val = re.search(r'value="([^"]*)"', t)
        fields.append((name.group(1), val.group(1) if val else ""))
    for sel in re.finditer(r'<select[^>]*name="([^"]*)"[^>]*>(.*?)</select>', form, re.S):
        name, body = sel.group(1), sel.group(2)
        selm = re.search(r"<option value='([^']*)' selected", body)
        if selm:
            v = selm.group(1)
        else:
            fm = re.search(r"<option value='([^']*)'", body)
            v = fm.group(1) if fm else ""
        fields.append((name, v))
    return fields


def fetch_menu(opener, cfg: dict, now: datetime, horizon_days: int) -> dict:
    url = avail_url(cfg["menu"], cfg["staff"], now.year, now.month, now.day)
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    html = opener.open(req, timeout=30).read().decode("utf-8", "replace")
    merged = parse_days(html)
    base_fields = extract_form_fields(html)

    for wd_code in WEEKDAY_FILTERS:
        fields = [
            (k, str(wd_code) if k == "sel_date2" else v) for k, v in base_fields
        ]
        fields.append(("selectdate2", "再表示"))
        data = urllib.parse.urlencode(fields).encode("utf-8")
        req = urllib.request.Request(
            FORM_ACTION, data=data, headers={"User-Agent": UA}
        )
        page = opener.open(req, timeout=30).read().decode("utf-8", "replace")
        for date_label, info in parse_days(page).items():
            if date_label in merged:
                # 同日が複数ソースに現れたら空き時刻の和集合 (どちらも実データ)
                merged[date_label]["times"] = sorted(
                    set(merged[date_label]["times"]) | set(info["times"])
                )
                if merged[date_label]["times"]:
                    merged[date_label]["status"] = ""
                elif info.get("status"):
                    merged[date_label]["status"] = info["status"]
            else:
                merged[date_label] = info

    last_day = now.date() + timedelta(days=horizon_days)
    days = []
    for date_label in sorted(merged):
        day_dt = datetime.strptime(date_label, "%Y/%m/%d").replace(tzinfo=JST)
        if day_dt.date() < now.date() or day_dt.date() > last_day:
            continue
        times = merged[date_label]["times"]
        if day_dt.date() == now.date():
            times = [t for t in times if t > now.strftime("%H:%M")]
        entry = {"date": date_label, "weekday": merged[date_label]["weekday"], "times": times}
        if not times and merged[date_label].get("status"):
            entry["status"] = merged[date_label]["status"]
        days.append(entry)
    return {"label": cfg["label"], "source_url": url, "days": days}


def main() -> None:
    dest = sys.argv[1] if len(sys.argv) > 1 else "availability.json"
    horizon = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    now = datetime.now(JST)
    jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    out = {"fetched_at": now.strftime("%Y-%m-%d %H:%M JST"), "menus": {}}
    for key in ("trial", "simulation", "vip"):
        out["menus"][key] = fetch_menu(opener, MENUS[key], now, horizon)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"wrote {dest} at {out['fetched_at']}")
    for key, data in out["menus"].items():
        print(f"--- {key}: {len(data['days'])} days")
        for d in data["days"]:
            print(" ", d["date"], f"({d['weekday']})", len(d["times"]), "slots")


if __name__ == "__main__":
    main()
