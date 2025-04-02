import streamlit as st
import requests
from datetime import datetime
import pandas as pd
import altair as alt
import math
import random
from calendar import monthrange
import gspread
from google.oauth2.service_account import Credentials

# ---------- カスタムCSS ----------
st.markdown(
    """
    <style>
    .reportview-container, .main, .block-container, .stApp {
        background-color: #000000 !important;
        color: #FFFFFF !important;
    }
    .sidebar .sidebar-content {
        background-color: #000000 !important;
        color: #FFFFFF !important;
    }
    table, th, td {
        color: #FFFFFF !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# セッションステートの初期化
if 'saved' not in st.session_state:
    st.session_state.saved = False

# ---------- 各種設定・関数 ----------

def load_credentials():
    try:
        credentials = st.secrets["credentials"]
    except Exception:
        st.error("ログイン情報の読み込みに失敗しました。")
        credentials = {}
    return credentials

def load_goals():
    try:
        goals = st.secrets["goals"]
    except Exception:
        st.error("目標金額の読み込みに失敗しました。")
        goals = {}
    return goals

def get_exchange_rate(url="https://open.er-api.com/v6/latest/USD"):
    try:
        response = requests.get(url)
        data = response.json()
        return data["rates"]["JPY"]
    except Exception:
        st.error("為替レートの取得に失敗しました。")
        return 0

def calculate_rewards(usd, rate, reward_rate=0.6, tax_rate=0.1021):
    before_tax = usd * rate * reward_rate
    tax = before_tax * tax_rate
    after_tax = before_tax - tax
    return math.ceil(before_tax), math.ceil(tax), math.ceil(after_tax)

def connect_to_sheet():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open("報酬管理シート（2025）").sheet1
        return sheet
    except Exception:
        st.error("Google スプレッドシートへの接続に失敗しました。")
        return None

def save_to_sheet(sheet, user_id, usd, rate, before_tax, tax, after_tax):
    current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = [current_date, user_id, usd, round(rate, 1), before_tax, tax, after_tax]
    try:
        sheet.append_row(new_row)
        st.success("✅ スプレッドシートに保存されました！")
    except Exception:
        st.error("データの保存に失敗しました。")

def load_records(sheet, user_id):
    try:
        records = sheet.get_all_records()
        df = pd.DataFrame(records)
    except Exception:
        st.error("シートからのデータ取得に失敗しました。")
        return pd.DataFrame()

    if "日付" in df.columns:
        df["日付"] = pd.to_datetime(df["日付"], errors="coerce")
    else:
        st.error("日付データが存在しません。")
        return pd.DataFrame()

    df = df[df["源氏名"] == user_id].sort_values("日付", ascending=False)
    df = df.drop(columns=["源氏名"]).reset_index(drop=True)
    return df

def display_history(df):
    st.subheader("📚 過去の報酬履歴")
    styled_df = df.copy().head(10)
    for col in ["ドル収益", "税引前報酬", "源泉徴収額", "税引後お給料"]:
        if col in styled_df.columns:
            styled_df[col] = styled_df[col].apply(lambda x: f"{x:,.0f}")
    if "レート" in styled_df.columns:
        styled_df["レート"] = styled_df["レート"].apply(lambda x: f"{x:.1f}")
    styled_df.index = range(1, len(styled_df) + 1)
    st.table(styled_df)

    recent_vals = df.head(10)["税引後お給料"]
    recent_vals = recent_vals[recent_vals > 0]
    recent_avg = recent_vals.mean() if not recent_vals.empty else 0
    st.markdown(f"🧮 **直近10回の平均お給料：¥{math.ceil(recent_avg):,} 円**")
    max_salary = df["税引後お給料"].max()
    st.markdown(f"👑 **過去最高お給料：¥{math.ceil(max_salary):,} 円**")

def display_charts(df):
    st.subheader("📈 近30日の報酬の推移")
    recent_df = df.sort_values("日付").head(30).sort_values("日付")
    if recent_df.empty:
        st.info("表示するデータがありません。")
        return

    chart = alt.Chart(recent_df).mark_line(point=True).encode(
        x="日付:T",
        y="税引後お給料:Q",
        tooltip=["日付:T", "税引後お給料:Q"]
    ).properties(width=350, height=250)
    avg = recent_df["税引後お給料"].mean()
    avg_line = alt.Chart(pd.DataFrame({"平均": [avg]})).mark_rule(color="red").encode(
        y="平均:Q"
    )
    st.altair_chart(chart + avg_line, use_container_width=True)

def display_monthly_bar_chart(df):
    st.subheader("📊 月別の合計報酬（直近3ヶ月）")
    df["月"] = df["日付"].dt.to_period("M").astype(str)
    monthly_df = df.groupby("月")["税引後お給料"].sum().reset_index()
    monthly_df = monthly_df.sort_values("月", ascending=False).head(3).sort_values("月")

    bar = alt.Chart(monthly_df).mark_bar(color="#90caf9").encode(
        x=alt.X("月:N", sort=None),
        y=alt.Y("税引後お給料:Q"),
        tooltip=["月", "税引後お給料"]
    ).properties(width=400, height=250)
    st.altair_chart(bar, use_container_width=True)

def display_calendar(df):
    st.subheader("📆 今月の活動カレンダー")
    today = datetime.now()
    year = today.year
    month = today.month
    start_weekday, last_day = monthrange(year, month)
    saved_dates = df["日付"].dt.strftime("%Y-%m-%d").tolist() if not df.empty else []
    saved_set = set(saved_dates)
    days_of_week = ["月", "火", "水", "木", "金", "土", "日"]

    calendar_html = """
    <style>
        table.calendar {
            border-collapse: collapse;
            width: 100%;
            max-width: 500px;
            margin: 0 auto;
            table-layout: fixed;
            background-color: #000000;
        }
        table.calendar th, table.calendar td {
            border: 1px solid #444444;
            padding: 8px;
            text-align: center;
            width: 14.2857%;
            color: #FFFFFF;
        }
        table.calendar th {
            background-color: #222222;
        }
    </style>
    <table class="calendar">
      <tr>
    """
    for day in days_of_week:
        calendar_html += f"<th>{day}</th>"
    calendar_html += "</tr>"

    week = [""] * start_weekday
    for d in range(1, last_day + 1):
        day_str = datetime(year, month, d).strftime("%Y-%m-%d")
        mark = "🌟" if day_str in saved_set else ""
        week.append(f"{d}{mark}")
        if len(week) == 7:
            calendar_html += "<tr>" + "".join([f"<td>{cell}</td>" if cell != "" else "<td>&nbsp;</td>" for cell in week]) + "</tr>"
            week = []
    if week:
        while len(week) < 7:
            week.append("")
        calendar_html += "<tr>" + "".join([f"<td>{cell}</td>" if cell != "" else "<td>&nbsp;</td>" for cell in week]) + "</tr>"
    calendar_html += "</table>"
    st.markdown(calendar_html, unsafe_allow_html=True)

def display_simulator(df, user_id):
    st.subheader("🧠 あと何回出ればどれくらい？シミュレーター")
    
    current_month = datetime.now().strftime("%Y-%m")
    this_month_df = df[df["日付"].dt.strftime("%Y-%m") == current_month]
    current_total = this_month_df["税引後お給料"].sum()
    avg_salary = df["税引後お給料"].mean()

    # シミュレーターは数値入力のみで動的に再計算（画面全体は再初期化されない）
    future_sessions = st.number_input("例えば今月あと何回配信すると？", min_value=0, max_value=30, value=3, key="simulator_sessions")
    projected_total = current_total + avg_salary * future_sessions

    last_day = datetime.now().replace(day=monthrange(datetime.now().year, datetime.now().month)[1]).strftime("%m月%d日")
    st.markdown(f"📅 {last_day} 時点で、{user_id} さんの予測お給料は **¥{int(projected_total):,} 円** になりそうです！")
    st.markdown(f"💡 今：¥{int(current_total):,} 円 ＋ 予測：¥{int(avg_salary * future_sessions):,} 円（平均 ¥{int(avg_salary):,}/回 × {future_sessions} 回）")

# ---------- メイン処理 ----------
def main():
    credentials_dict = load_credentials()
    goals = load_goals()

    st.title("🔐 ライバー専用｜報酬計算ツール (Ver.10.7.3-GS-Full-Mobile++ グラフ&月別棒グラフ版)")
    st.subheader("👤 ログイン")

    user_id = st.text_input("ID（源氏名）を入力してください")
    user_pass = st.text_input("Password（パスワード）を入力してください", type="password")

    if user_id in credentials_dict and credentials_dict[user_id] == user_pass:
        st.success("✅ ログイン成功しました！")
        sheet = connect_to_sheet()
        if sheet is None:
            return

        rate = get_exchange_rate()
        if rate == 0:
            st.error("適切な為替レートが取得できなかったため、計算を終了します。")
            return

        usd_input = st.text_input("💵 今日のドル収益 ($)", placeholder="例：200")
        try:
            usd = float(usd_input)
        except Exception:
            usd = 0.0

        before_tax, tax, after_tax = calculate_rewards(usd, rate)

        st.write(f"📈 ドル円レート：{rate:.1f} 円")
        st.write(f"💰 税引前報酬：¥{before_tax:,} 円")
        st.write(f"🧾 源泉徴収額：-¥{tax:,} 円")
        st.success(f"🎉 税引後お給料：¥{after_tax:,} 円")
        st.info("💬 本日も大変お疲れ様でした。")

        st.markdown(
            """
            <div style='background-color:#4a148c; color:#FFFFFF; padding:12px; border-left: 6px solid #f48fb1; border-radius:5px;'>
            ⬇️ <strong>このボタンを押さないと、今日のお給料が保存されません！</strong>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.markdown(
            "<span style='color:#f8bbd0; font-weight:bold;'>⚠️ 必ず『保存する』ボタンを押してください！</span>",
            unsafe_allow_html=True
        )

        if st.button("💾 保存する（※忘れずに！）"):
            save_to_sheet(sheet, user_id, usd, rate, before_tax, tax, after_tax)
            st.session_state.saved = True

        # 保存ボタンが押された場合のみ、過去の履歴・グラフ・シミュレーターを表示
        if st.session_state.saved:
            df = load_records(sheet, user_id)
            if df.empty:
                st.info("まだ記録がありません。")
            else:
                display_history(df)
                display_charts(df)
                display_monthly_bar_chart(df)
                display_calendar(df)
                display_simulator(df, user_id)
    else:
        if user_id and user_pass:
            st.error("❌ IDまたはパスワードが正しくありません。")

if __name__ == "__main__":
    main()
