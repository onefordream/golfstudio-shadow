#!/usr/bin/env python3
"""availability.json から LP表示サンプル (静的HTML, 1ヶ月分) を生成する。"""
import base64
import json
import os
from datetime import date, datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
# 体験レッスン無料キャンペーン (2026-12-31まで)。期間を過ぎたら特典ブロックは
# 自動で消え、価格表示は通常の1,000円に戻る。
CAMPAIGN_END = date(2026, 12, 31)
CAMPAIGN_ACTIVE = datetime.now(JST).date() <= CAMPAIGN_END
TRIAL_YEN = "無料" if CAMPAIGN_ACTIVE else "1,000円"
TRIAL_PER = "期間限定キャンペーン中" if CAMPAIGN_ACTIVE else "初回限定・カウンセリング付き"
NAV_TRIAL_PRICE = "無料" if CAMPAIGN_ACTIVE else "1,000円"

CAMPAIGN_HTML = (
    """
    <div class="campaign">
      <div class="campaign-head">期間限定キャンペーン<span class="campaign-until">2026年12月31日まで</span></div>
      <ul>
        <li>体験レッスン <strong>無料</strong></li>
        <li>入会金 <strong>無料</strong></li>
        <li>ゼロフィットグローブ <strong>プレゼント</strong></li>
        <li>シミュレーションルーム <strong>1ヶ月無料</strong>（1日1コマ）</li>
      </ul>
      <p class="campaign-note">※特典は体験レッスン当日入会に限ります</p>
    </div>"""
    if CAMPAIGN_ACTIVE
    else ""
)

with open("availability.json", encoding="utf-8") as f:
    data = json.load(f)


def img_datauri(path: str) -> str:
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as f:
        return "data:image/jpeg;base64," + base64.b64encode(f.read()).decode()


if os.environ.get("LP_IMAGE_MODE") == "relative":
    # GitHub Pages 用: 画像は assets/ の相対参照にする
    LOGO_URI = "assets/logo.jpg"
    VIP_URI = "assets/vip.jpg"
    LESSON_URI = "assets/lesson.jpg"
    SIM_URI = "assets/sim.jpg"
else:
    # ローカルプレビュー用: 画像を data URI で埋め込む
    LOGO_URI = img_datauri("assets/logo.jpg")
    VIP_URI = img_datauri("assets/vip.jpg")
    LESSON_URI = img_datauri("assets/lesson.jpg")
    SIM_URI = img_datauri("assets/sim.jpg")

fetched = data["fetched_at"]


def full_days(menu: dict) -> list:
    """取得データを暦の全日程に展開する。欠けている月曜は定休日として補う。"""
    by_date = {d["date"]: d for d in menu["days"]}
    if not by_date:
        return []
    start = datetime.strptime(min(by_date), "%Y/%m/%d")
    end = datetime.strptime(max(by_date), "%Y/%m/%d")
    out = []
    cur = start
    while cur <= end:
        key = cur.strftime("%Y/%m/%d")
        if key in by_date:
            out.append(by_date[key])
        elif cur.weekday() == 0:  # 月曜はフィルタ取得対象外 = 定休日
            out.append(
                {"date": key, "weekday": "月", "times": [], "status": "店舗休日"}
            )
        cur += timedelta(days=1)
    return out


def md(date_str: str) -> str:
    d = datetime.strptime(date_str, "%Y/%m/%d")
    return f"{d.month}/{d.day}"


TIMES = [f"{h}:00" for h in range(10, 21)]


def calendar_html(menu: dict, prefix: str) -> str:
    """ホットペッパー式の○×カレンダー (縦=時間 / 横=日付, 週切り替えはCSSのみ)

    ○は公式予約へのPOST送信ボタン。取得時に保持したフォームフィールド一式と
    reserve_time[2]=「日付<TAB>時刻」+ reserveconfirm[2]=次へ を公式actionへ送ると、
    その日時の「ご予約内容の確認」画面へ直接進む (セッション不要・検証済み)。
    """
    import html as _html

    days = full_days(menu)
    weeks = [days[i : i + 7] for i in range(0, len(days), 7)]
    booking = menu.get("booking") or {}
    action = booking.get("action", "")
    bfields = [list(f) for f in (booking.get("fields") or [])]
    if action and "reserve_time[2]" not in {k for k, _ in bfields}:
        bfields.append(["reserve_time[2]", ""])
    hidden = "".join(
        f'<input type="hidden" name="{_html.escape(k, quote=True)}" value="{_html.escape(v, quote=True)}">'
        for k, v in bfields
    )
    parts = [f'<div class="cal" id="{prefix}-ph">']
    # 週切り替えラジオ + ラベル
    for wi, wk in enumerate(weeks):
        checked = " checked" if wi == 0 else ""
        parts.append(
            f'<input class="cal-r" type="radio" name="cal-{prefix}" id="cal-{prefix}-{wi}"{checked}>'
            f'<label class="cal-l" for="cal-{prefix}-{wi}">{md(wk[0]["date"])}〜</label>'
        )
    if action:
        parts.append(
            f'<form method="post" action="{action}" target="_blank">{hidden}<div class="cal-weeks">'
        )
    else:
        parts.append('<div class="cal-weeks">')
    for wi, wk in enumerate(weeks):
        parts.append(f'<table class="cal-t wk{wi}">')
        # ヘッダー行: 日付
        ths = ['<th class="tm"></th>']
        for day in wk:
            wd_class = " sun" if day["weekday"] == "日" else (" sat" if day["weekday"] == "土" else "")
            closed = " closed" if not day["times"] else ""
            ths.append(
                f'<th class="dt{wd_class}{closed}">{md(day["date"])}<span class="wd{wd_class}">({day["weekday"]})</span></th>'
            )
        parts.append("<tr>" + "".join(ths) + "</tr>")
        # 時間行
        for t in TIMES:
            tds = [f'<td class="tm">{t}</td>']
            for day in wk:
                if t in day["times"]:
                    if action:
                        tds.append(
                            '<td><button type="submit" class="o" name="reserveconfirm[2]" value="次へ" '
                            f"onclick=\"this.form.elements['reserve_time[2]'].value='{day['date']}&#9;{t}'\">○</button></td>"
                        )
                    else:
                        tds.append(
                            '<td><a class="o" href="https://golfstudio-shadow.jp/pcreserve.php" target="_blank" rel="noopener">○</a></td>'
                        )
                else:
                    tds.append('<td><span class="x">×</span></td>')
            parts.append("<tr>" + "".join(tds) + "</tr>")
        parts.append("</table>")
    parts.append("</div>")
    if action:
        parts.append("</form>")
    # 週表示の切り替えCSS (このカレンダー専用)
    mid = "form .cal-weeks" if action else ".cal-weeks"
    rules = []
    for wi in range(len(weeks)):
        rules.append(
            f"#{prefix}-ph input#cal-{prefix}-{wi}:checked ~ {mid} .wk{wi} {{ display:table; }}"
        )
        rules.append(
            f"#{prefix}-ph input#cal-{prefix}-{wi}:checked + .cal-l {{ background:#14402f; color:#fff; }}"
        )
    parts.append("<style>" + "".join(rules) + "</style>")
    parts.append("</div>")
    return "\n".join(parts)


trial = data["menus"]["trial"]
sim = data["menus"]["simulation"]
vip = data["menus"]["vip"]

html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>GOLF STUDIO SHADOW | 空き状況・ご予約</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  html {{ scroll-behavior:smooth; }}
  body {{ font-family:"Hiragino Kaku Gothic ProN","Hiragino Sans",sans-serif; background:#faf9f5; color:#17181a; }}
  .wrap {{ max-width:560px; margin:0 auto; padding:0 18px 40px; }}
  header {{ padding:26px 0 8px; text-align:center; }}
  .logo-badge img {{ height:42px; width:auto; display:inline-block; }}
  .photo {{ width:100%; height:132px; object-fit:cover; border-radius:10px; display:block; margin:10px 0 2px; }}
  .photo.tall {{ height:120px; object-position:center 26%; }}
  h1 {{ font-size:23px; font-weight:700; letter-spacing:.08em; margin-top:10px; color:#17181a; }}
  .sub {{ font-size:12px; color:#6f6c62; margin-top:8px; line-height:1.7; }}
  .live {{ display:inline-block; margin-top:12px; font-size:11px; color:#fff; background:#14402f; border-radius:0; padding:4px 12px; font-weight:700; }}
  .group-note {{ margin-top:14px; font-size:12px; color:#5c4a17; background:#fdf6e0; border:1px solid #c9a86a; border-radius:0; padding:10px 12px; line-height:1.8; }}
  .group-note a {{ color:#14402f; font-weight:700; }}
  .nav {{ display:flex; gap:8px; margin-top:14px; }}
  .nav a {{ flex:1; text-decoration:none; background:#14402f; color:#fff; border-radius:0; padding:11px 4px 9px; text-align:center; }}
  .nav a.gold {{ background:#a5812f; }}
  .nav a.black {{ background:#17181a; }}
  .nav .n-name {{ display:block; font-size:13px; font-weight:700; line-height:1.4; }}
  .nav .n-price {{ display:block; font-size:11px; color:#e6c87a; margin-top:2px; }}
  .nav a.black .n-price {{ color:#c9a86a; }}
  section {{ margin-top:24px; background:#ffffff; border:1px solid #e5e0d2; border-top:3px solid #14402f; border-radius:14px; padding:20px 18px 10px; box-shadow:0 2px 10px rgba(20,64,47,.06); scroll-margin-top:12px; }}
  .menu-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:10px; }}
  h2 {{ font-size:19px; letter-spacing:.05em; color:#14402f; }}
  .price {{ text-align:right; }}
  .price .yen {{ font-size:19px; color:#a5812f; font-weight:700; }}
  .price .per {{ font-size:11px; color:#6f6c62; display:block; }}
  .desc {{ font-size:12.5px; color:#3d3f42; line-height:1.8; margin:10px 0 4px; }}
  .day {{ border-top:1px solid #eceade; padding:11px 0 13px; }}
  .day-head {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:8px; }}
  .date {{ font-size:14.5px; font-weight:700; }}
  .wd {{ font-size:12px; color:#6f6c62; font-weight:400; margin-left:2px; }}
  .wd.sat {{ color:#2f5fb3; }} .wd.sun {{ color:#c23b2e; }}
  .badge {{ font-size:11px; font-weight:700; color:#c23b2e; border:1px solid #c23b2e; border-radius:999px; padding:2px 9px; }}
  .badge.soft {{ color:#a5812f; border-color:#c9a86a; }}
  .chips {{ display:flex; flex-wrap:wrap; gap:7px; }}
  .chip {{ display:inline-block; text-decoration:none; font-size:13.5px; font-weight:600; color:#17181a; border:1px solid #cfc9b8; border-radius:9px; padding:7px 12px; background:#fbfaf7; }}
  .chip:active {{ background:#14402f; color:#fff; border-color:#14402f; }}
  .closed {{ font-size:12.5px; color:#9a968a; }}
  .cal {{ margin-top:12px; }}
  .cal-r {{ display:none; }}
  .cal-l {{ display:inline-block; font-size:12px; font-weight:700; color:#14402f; border:1px solid #14402f; border-radius:0; padding:5px 12px; margin:0 5px 10px 0; cursor:pointer; background:#fff; }}
  .cal-t {{ display:none; width:100%; border-collapse:collapse; table-layout:fixed; }}
  .cal-t th, .cal-t td {{ border:1px solid #e5e0d2; text-align:center; padding:5px 0; font-size:12px; }}
  .cal-t th.dt {{ background:#f4f1e8; font-weight:700; font-size:12px; }}
  .cal-t th.dt .wd {{ display:block; font-size:10px; margin-left:0; }}
  .cal-t th.dt.closed {{ background:#eceae2; color:#9a968a; }}
  .cal-t td.tm, .cal-t th.tm {{ width:46px; background:#faf9f5; color:#6f6c62; font-size:11px; font-weight:700; }}
  .cal-t button.o {{ background:none; border:none; padding:0; font:inherit; color:#14402f; font-weight:700; font-size:15px; cursor:pointer; display:block; width:100%; }}
  .cal-t a.o {{ color:#14402f; font-weight:700; font-size:15px; text-decoration:none; display:block; }}
  .cal-t span.x {{ color:#cfcbc0; font-size:12px; }}
  .campaign {{ margin-top:14px; border:2px solid #c9a86a; border-radius:0; overflow:hidden; }}
  .campaign-head {{ background:#14402f; color:#fff; font-size:14px; font-weight:700; padding:9px 14px; letter-spacing:.04em; }}
  .campaign-until {{ float:right; font-size:11px; color:#e6c87a; font-weight:700; }}
  .campaign ul {{ list-style:none; padding:10px 14px 4px; }}
  .campaign li {{ font-size:13.5px; padding:4px 0 4px 20px; position:relative; color:#17181a; }}
  .campaign li::before {{ content:""; position:absolute; left:2px; top:11px; width:8px; height:8px; border-radius:50%; background:#c9a86a; }}
  .campaign li strong {{ color:#a5812f; }}
  .campaign-note {{ font-size:11px; color:#9a968a; padding:2px 14px 10px; }}
  .legend {{ font-size:11px; color:#6f6c62; margin-top:8px; }}
  .legend .o {{ color:#14402f; font-weight:700; }}
  .note {{ font-size:11px; color:#9a968a; line-height:1.8; margin:12px 0 8px; }}
  .phone {{ margin-top:26px; background:#14402f; border-radius:0; padding:18px; text-align:center; }}
  .phone .lead {{ font-size:13px; color:#e9e6da; line-height:1.8; }}
  .phone a.tel {{ display:inline-block; margin-top:10px; font-size:22px; font-weight:700; color:#e6c87a; text-decoration:none; letter-spacing:.05em; }}
  footer {{ margin-top:26px; font-size:12px; color:#6f6c62; line-height:1.9; text-align:center; }}
  .sample {{ margin-top:16px; font-size:11px; color:#a49f92; text-align:center; line-height:1.8; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <div class="logo-badge"><img src="{LOGO_URI}" alt="GOLF STUDIO SHADOW"></div>
    <h1>空き状況・ご予約</h1>
    <p class="sub">北巽駅すぐ・生野区のインドアゴルフスタジオ<br>1ヶ月先まで、実際の空き枠をそのまま表示しています</p>
    <span class="live">空き状況 {fetched} 時点</span>
    <nav class="nav">
      <a href="#trial"><span class="n-name">体験レッスン</span><span class="n-price">{NAV_TRIAL_PRICE}</span></a>
      <a href="#sim" class="gold"><span class="n-name">シミュレーションルーム</span><span class="n-price">1,800円〜</span></a>
      <a href="#vip" class="black"><span class="n-name">VIPルーム</span><span class="n-price">3,000円</span></a>
    </nav>
    <p class="group-note">2名様以上で同じ時間をご希望の場合は、空き枠数の確認のため<br>お電話でのご予約をお願いしています（<a href="tel:0667571630">06-6757-1630</a>）</p>
  </header>

  <section id="trial">
    <div class="menu-head">
      <h2>体験レッスン</h2>
      <div class="price"><span class="yen">{TRIAL_YEN}</span><span class="per">{TRIAL_PER}</span></div>
    </div>
    <p class="desc">初めての方限定。レッスンとカウンセリングで、今の課題と上達への道筋が見えます。手ぶらでOK、クラブの貸し出しもあります。</p>
    {CAMPAIGN_HTML}
    <img class="photo tall" src="{LESSON_URI}" alt="体験レッスンの様子">
    {calendar_html(trial, "trial")}
    <p class="legend"><span class="o">○</span> 予約できます ／ × 予約できません</p>
    <p class="note">○を押すと、その日時のまま公式の予約確認画面へ進みます。2名様以上で同じ時間をご希望の場合は、お電話でご相談ください。</p>
  </section>

  <section id="sim">
    <div class="menu-head">
      <h2>シミュレーションルーム</h2>
      <div class="price"><span class="yen">1,800円</span><span class="per">1コマ55分・2名まで</span></div>
    </div>
    <p class="desc">レッスンなしで打席だけ使えます。弾道測定器SkyTrak完備で、シミュレーションラウンドも本格練習も。数字を見ながら打つと、直す所がすぐ分かります。</p>
    <img class="photo" src="{SIM_URI}" alt="シミュレーションルーム">
    {calendar_html(sim, "sim")}
    <p class="legend"><span class="o">○</span> 予約できます ／ × 予約できません</p>
    <p class="note">○を押すと、その日時のまま公式の予約確認画面へ進みます。2名様以上で同じ時間をご希望の場合は、お電話でご相談ください。</p>
  </section>

  <section id="vip">
    <div class="menu-head">
      <h2>VIPルーム（完全個室）</h2>
      <div class="price"><span class="yen">3,000円</span><span class="per">1コマ55分・1部屋</span></div>
    </div>
    <p class="desc">最大4名まで。シミュレーションラウンドも練習もOK。弾道・スイングの計測データが見られる個室で、飲食の持ち込みもできます。</p>
    <img class="photo" src="{VIP_URI}" alt="VIPルーム">
    {calendar_html(vip, "vip")}
    <p class="legend"><span class="o">○</span> 予約できます ／ × 予約できません</p>
    <p class="note">○を押すと、その日時のまま公式の予約確認画面へ進みます。2名様以上で同じ時間をご希望の場合は、お電話でご相談ください。</p>
  </section>

  <div class="phone">
    <p class="lead">1ヶ月より先のご予約や、団体でのご利用は<br>お電話でお問い合わせください</p>
    <a class="tel" href="tel:0667571630">06-6757-1630</a>
  </div>

  <footer>
    大阪府大阪市生野区巽北3丁目15-24 豊都ビル205号室<br>
    火〜金 10:00〜21:00 / 土・日・祝 10:00〜20:00 / 月曜定休
    <div class="sample">これは表示サンプル（試作）です。空き状況は取得時点の実データで、予約の確定は公式予約ページで行います。</div>
  </footer>
</div>
</body>
</html>
"""

with open("lp-sample.html", "w", encoding="utf-8") as f:
    f.write(html)
print("wrote lp-sample.html", len(html), "bytes")
