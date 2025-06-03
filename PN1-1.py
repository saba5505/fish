import streamlit as st
import pandas as pd
import unicodedata
from datetime import datetime, timedelta
import gspread
from google.oauth2.service_account import Credentials

# --- ★ここを編集してください----------------------------------
# GoogleスプレッドシートIDをコピーしてここに貼る
SPREADSHEET_ID = "ここにGoogleスプレッドシートIDを入れる"

# credentials.jsonはStreamlitの同じフォルダに配置してください
CREDENTIALS_FILE = "credentials.json"
# ------------------------------------------------------------

# 商品リストを読み込む（Googleスプレッドシートの別シートを使うなど自由に変更可）
# ここでは「products」シートに商品名リストがある想定
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
creds = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
client = gspread.authorize(creds)

try:
    # 商品一覧のシート名「products」を指定（必要に応じて変更）
    product_sheet = client.open_by_key(SPREADSHEET_ID).worksheet("products")
    products_list = product_sheet.col_values(1)  # 1列目を商品名リストとして取得
except Exception as e:
    st.error(f"商品リストの取得に失敗しました: {e}")
    products_list = []

# ──────────────────────────
# ユーティリティ関数
# ──────────────────────────
def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.translate(str.maketrans(
        "アイウエオカキクケコサシスセソタチツテトナニヌネノ"
        "ハヒフヘホマミムメモヤユヨラリルレロワヲン",
        "あいうえおかきくけこさしすせそたちつてとなにぬねの"
        "はひふへほまみむめもやゆよらりるれろわをん"
    ))
    return text

st.title("🐟 fishパンロス Google Sheets版")

# 1. 商品名フィルタ
input_text = st.text_input("商品の頭文字を入力してください").strip()

if input_text:
    key = normalize_text(input_text)
    cand_list = [p for p in products_list if key in normalize_text(p)]
    if len(cand_list) == 0:
        st.warning("該当する商品が見つかりません")
        selected_product = None
    else:
        selected_product = st.selectbox("商品を選択してください", cand_list)
else:
    selected_product = None

if selected_product:
    now = datetime.now()
    sheet_name = f"{now.month}月pannhaiki"
    last_day = (now.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1)

    # 月別シート取得（なければ作成）
    try:
        ws = client.open_by_key(SPREADSHEET_ID).worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        # シートがなければ新規作成し、1行目にヘッダをセット
        sh = client.open_by_key(SPREADSHEET_ID)
        ws = sh.add_worksheet(title=sheet_name, rows="100", cols=str(last_day.day + 2))
        header = ["商品名"] + [f"{i+1:02d}" for i in range(last_day.day)] + ["ロス合計個数"]
        ws.append_row(header)

    # 商品名の行を探す
    records = ws.get_all_records()
    product_names = [row["商品名"] for row in records]

    if selected_product in product_names:
        row_idx = product_names.index(selected_product) + 2  # 1行目がヘッダなので+2
    else:
        # 新規行追加
        new_row = [selected_product] + [0]*last_day.day + [0]
        ws.append_row(new_row)
        row_idx = len(product_names) + 2

    col_idx = now.day + 1  # 1列目が商品名なので2日→3列目など

    # 現在の値取得
    try:
        cell_value = ws.cell(row_idx, col_idx).value
        prev_qty = int(cell_value) if cell_value else 0
    except:
        prev_qty = 0

    qty = st.number_input(f"{selected_product} の廃棄個数を入力", min_value=0, step=1, value=0)
    st.info(f"本日すでに記録されている数量: {prev_qty} 個")
    add_mode = st.checkbox("既存の数に合計する")

    if st.button("記録"):
        try:
            new_qty = prev_qty + qty if add_mode else qty
            ws.update_cell(row_idx, col_idx, new_qty)

            # 合計列更新
            row_values = ws.row_values(row_idx)
            total_loss = sum(int(v) if v.isdigit() else 0 for v in row_values[1:last_day.day+1])
            ws.update_cell(row_idx, last_day.day + 2, total_loss)

            st.success(f"{selected_product} の廃棄 {new_qty} 個 を記録しました")
        except Exception as e:
            st.error(f"保存に失敗しました: {e}")

    # 今月シートを表示（pandas DataFrameに変換）
    data = ws.get_all_values()
    df_month = pd.DataFrame(data[1:], columns=data[0])
    st.subheader("📊 今月の廃棄データ")
    st.dataframe(df_month)

# 終了ボタン
if st.button("入力を終了する"):
    st.warning("✅ 入力を終了しました。画面を閉じてください。")
    st.stop()
