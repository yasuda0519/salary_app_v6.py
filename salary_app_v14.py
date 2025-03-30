import streamlit as st
import requests
from datetime import datetime
import os
import pandas as pd
import altair as alt
import json
import math
import random
from calendar import monthrange

# ========== ログイン情報の読み込み ==========
try:
    credentials = st.secrets["credentials"]
except Exception as e:
    st.error("ログイン情報の読み込みに失敗しました。")
    credentials = {}

# ========== 目標金額の読み込み ==========
try:
    goals = st.secrets["goals"]
except Exception as e:
    st.error("目標金額の読み込みに失敗しました。")
    goals = {}

# ========== ログイン画面 ==========
st.title("🔐 ライバー専用｜報酬計算ツール (Ver.10.7.3)")
st.subheader("👤 ログイン")

user_id = st.text_input("ID（源氏名）を入力してください")
user_pass = st.text_input("Password（パスワード）を入力してください", type="password")

if user_id in credentials and credentials[user_id] == user_pass:
    st.success("✅ ログイン成功しました！")

    # ===== 為替レート取得 =====
    url = "https://open.er-api.com/v6/latest/USD"
    try:
        response = requests.get(url)
        data = response.json()
        rate = data["rates"]["JPY"]
    except Exception as e:
        st.error("為替レートの取得に失敗しました。")
        rate = 0

    if rate == 0:
        st.error("適切な為替レートが取得できなかったため、計算を終了します。")
    else:
        # ===== ドル収益の入力 =====
        usd_input = st.text_input("💵 今日のドル収益 ($)", placeholder="例：200")
        try:
            usd = float(usd_input)
        except:
            usd = 0.0

        reward_rate = 0.6
        tax_rate = 0.1021

        before_tax = usd * rate * reward_rate
        tax = before_tax * tax_rate
        after_tax = before_tax - tax

        st.write(f"📈 ドル円レート：{rate:.2f} 円")
        st.write(f"💰 税引前報酬：¥{math.ceil(before_tax):,} 円")
        st.write(f"🧾 源泉徴収額：-¥{math.ceil(tax):,} 円")
        st.success(f"🎉 税引後お給料：¥{math.ceil(after_tax):,} 円")
        st.info("💬 本日も大変お疲れ様でした。")
        st.caption("提供：グランドチャット")

        st.warning("⬇️ このボタンを押さないと、今日のお給料が保存されません！")
        st.markdown("<span style='color:gold; font-weight:bold;'>⚠️ 必ず『保存する』ボタンを押してください！</span>", unsafe_allow_html=True)

        # ===== 保存処理と保存後の比較 =====
        if st.button("💾 保存する（※忘れずに！）"):
            # CSV 保存先のフォルダとファイルパスを決定
            folder = os.path.expanduser("~/Desktop/reports")
            os.makedirs(folder, exist_ok=True)
            file_path = os.path.join(folder, f"{user_id}.csv")

            # 新しいデータの作成
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            new_data = {
                "日付": current_date,
                "ドル収益": usd,
                "レート": rate,
                "税引前報酬": math.ceil(before_tax),
                "源泉徴収額": math.ceil(tax),
                "税引後お給料": math.ceil(after_tax),
            }

            # CSV の読み込みと更新
            if os.path.exists(file_path):
                try:
                    df = pd.read_csv(file_path)
                except Exception as e:
                    df = pd.DataFrame()
                df = pd.concat([df, pd.DataFrame([new_data])], ignore_index=True)
            else:
                df = pd.DataFrame([new_data])

            # CSV に保存
            df.to_csv(file_path, index=False)
            st.success(f"✅ {user_id}.csv に保存しました！")

            # ★ 保存後の比較処理 ★
            try:
                df_check = pd.read_csv(file_path)
                df_check["日付"] = pd.to_datetime(df_check["日付"])
                recent_30 = df_check.sort_values("日付", ascending=False).head(30)
                if math.ceil(after_tax) > recent_30["税引後お給料"].max():
                    st.balloons()
                    st.success("🎉 おめでとうございます！過去30日で最高のお給料を記録しました！")
            except Exception as e:
                st.error(f"比較中にエラーが発生しました: {e}")

            # ===== 以下、履歴表示・グラフ・カレンダーの表示 =====

            # 日付変換とデータ整形
            try:
                df["日付"] = pd.to_datetime(df["日付"])
            except Exception as e:
                st.error("日付の変換に失敗しました。")
            df = df.sort_values(by="日付", ascending=False)
            int_cols = ["ドル収益", "税引前報酬", "源泉徴収額", "税引後お給料"]
            df[int_cols] = df[int_cols].fillna(0).applymap(lambda x: int(round(x)))

            st.subheader("📚 過去の報酬履歴")
            st.table(df)

            recent_vals = df.head(10)["税引後お給料"]
            recent_vals = recent_vals[recent_vals > 0]
            recent_avg = recent_vals.mean() if not recent_vals.empty else 0
            st.markdown(f"🧮 **直近10回の平均お給料：¥{math.ceil(recent_avg):,} 円**")

            max_salary = df["税引後お給料"].max()
            st.markdown(f"👑 **過去最高お給料：¥{math.ceil(max_salary):,} 円**")

            goal = goals.get(user_id, 50000)
            current_month = datetime.now().strftime("%Y-%m")
            df["月"] = df["日付"].dt.strftime("%Y-%m")
            monthly_total = df[df["月"] == current_month]["税引後お給料"].sum()
            progress = (monthly_total / goal) * 100 if goal > 0 else 0

            st.markdown(f"🎯 今月の目標：¥{goal:,} 円")
            st.markdown(f"✅ 達成率：{math.floor(progress)}%")
            st.progress(min(100, math.floor(progress)))

            if progress >= 100:
                st.success("🔥 目標達成おめでとうございます！！")
            else:
                st.info("👍 引き続きがんばりましょう！")
                messages = [
                    "その調子！あと少しで目標達成だね🔥",
                    "数字に出てるよ、あなたの努力✨",
                    "今日の記録が、未来の土台になる。",
                    "ここまで続けてる時点で偉すぎる。",
                    "小さな積み重ねが、未来を変えるんだよね。",
                ]
                st.info(random.choice(messages))

            # ===== グラフの表示 =====
            st.subheader("📈 近30日の報酬の推移")
            recent_df = df.sort_values("日付").tail(30)
            avg_value = recent_df["税引後お給料"].mean()
            avg_line = alt.Chart(pd.DataFrame({"平均": [avg_value]})).mark_rule(color="red").encode(
                y=alt.Y("平均:Q")
            )
            line_chart = alt.Chart(recent_df).mark_line(point=True).encode(
                x='日付:T',
                y='税引後お給料:Q',
                tooltip=['日付:T', '税引後お給料:Q']
            ).properties(width=350, height=250)
            st.altair_chart(line_chart + avg_line, use_container_width=True)

            monthly_df = df.groupby("月")["税引後お給料"].sum().reset_index()
            st.subheader("📊 月別の合計報酬")
            bar_chart = alt.Chart(monthly_df).mark_bar().encode(
                x="月:N",
                y="税引後お給料:Q",
                tooltip=["月:N", "税引後お給料:Q"]
            ).properties(width=350, height=250)
            st.altair_chart(bar_chart, use_container_width=True)

            # ===== カレンダーの表示 =====
            st.subheader("📆 今月の活動カレンダー")
            today = datetime.now()
            year = today.year
            month = today.month
            start_weekday, last_day = monthrange(year, month)
            all_days = [datetime(year, month, d).strftime("%Y-%m-%d") for d in range(1, last_day + 1)]
            saved_dates = df["日付"].dt.strftime("%Y-%m-%d").tolist()
            saved_set = set(saved_dates)

            days_of_week = ["月", "火", "水", "木", "金", "土", "日"]

            calendar_html = """
<style>
    table.calendar {
        border-collapse: collapse;
        width: 100%;
        max-width: 500px;
        margin: 0 auto;
        table-layout: fixed; /* 各セルを均等幅に */
        background-color: #ffffff; /* テーブル全体の背景色を白に */
    }
    table.calendar th, table.calendar td {
        border: 1px solid #ddd;
        padding: 8px;
        text-align: center;
        width: 14.2857%;
        color: #000000; /* 文字色を黒に */
    }
    table.calendar th {
        background-color: #f2f2f2; /* 見出しセルの背景色を薄いグレーに */
    }
</style>
<table class="calendar">
  <tr>
"""

# 以下、曜日の見出しと日付セルの追加処理
            for day in days_of_week:
                calendar_html += f"<th>{day}</th>"
            calendar_html += "</tr>"

            week = [""] * start_weekday
            for d in range(1, last_day + 1):
                day_str = datetime(year, month, d).strftime("%Y-%m-%d")
                mark = "🎙" if day_str in saved_set else ""
                week.append(f"{d}{mark}")
                if len(week) == 7:
                    calendar_html += (
                        "<tr>" +
                        "".join([f"<td>{cell}</td>" if cell != "" else "<td>&nbsp;</td>" for cell in week]) +
                        "</tr>"
                    )
                    week = []
            if week:
                while len(week) < 7:
                    week.append("")
                calendar_html += (
                    "<tr>" +
                    "".join([f"<td>{cell}</td>" if cell != "" else "<td>&nbsp;</td>" for cell in week]) +
                    "</tr>"
                )
            calendar_html += "</table>"
            st.markdown(calendar_html, unsafe_allow_html=True)

else:
    if user_id and user_pass:
        st.error("❌ IDまたはパスワードが正しくありません。")
