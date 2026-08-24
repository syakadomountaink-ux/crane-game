import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
import math
import json
import io
import csv
from datetime import datetime

# ページ設定
st.set_page_config(page_title="クレーンゲーム攻略予測", layout="centered")

st.title("🎮 クレーンゲーム 横揺れ(X軸)攻略予測")
st.caption("自動計算（赤）と手動の周期（青）を同時に比較し、ベストなタイミングを算出・保存します。")

# --- 保存データと入力欄の初期化 (セッションステート) ---
if "saved_configs" not in st.session_state:
    st.session_state.saved_configs = []

if "store_name" not in st.session_state:
    st.session_state.store_name = f"{datetime.now().strftime('%m/%d')} 〇〇店 UFO9 1番台 右側"

if "t_d" not in st.session_state:
    st.session_state.t_d = 3.00

if "hook_clock" not in st.session_state:
    st.session_state.hook_clock = 3

# --- 共通の計算関数 ---
def calc_timing(T, t_d, hook_clock):
    if T <= 0:
        return 0, 0, 0
    phase_advance_deg = (t_d % T) / T * 360

    target_deg = (3 - hook_clock) * 30
    if target_deg < 0:
        target_deg += 360
    hook_rad = math.radians(target_deg)

    press_phase_deg = (180 - phase_advance_deg) % 360
    press_phase_rad = math.radians(press_phase_deg)

    displacement = math.sin(press_phase_rad)
    velocity = math.cos(press_phase_rad)

    x_pos = displacement * math.cos(hook_rad)
    y_pos = displacement * math.sin(hook_rad)
    v_x = velocity * math.cos(hook_rad)
    return x_pos, y_pos, v_x


def adjust_t_d(delta):
    st.session_state.t_d = round(max(0.1, st.session_state.t_d + delta), 2)


# ==========================================
# データ読み込み(JSON) — 一番上に置いて出先でもすぐ復元できるように
# ==========================================
with st.expander("📂 保存データを読み込む（前回のJSONファイル）", expanded=False):
    uploaded = st.file_uploader("JSONファイルを選択", type=["json"], label_visibility="collapsed")
    if uploaded is not None:
        try:
            loaded = json.load(uploaded)
            if isinstance(loaded, list):
                # 重複を避けつつ追加
                existing_names = {c.get("店舗_筐体名") for c in st.session_state.saved_configs}
                added = 0
                for item in loaded:
                    if item.get("店舗_筐体名") not in existing_names:
                        st.session_state.saved_configs.append(item)
                        added += 1
                st.success(f"{added}件のデータを読み込みました。")
            else:
                st.error("JSONの形式が正しくありません。")
        except Exception as e:
            st.error(f"読み込みに失敗しました: {e}")

st.divider()

# ==========================================
# タブ構成（スマホでサイドバーを開閉する手間をなくす）
# ==========================================
tab1, tab2, tab3 = st.tabs(["🕹️ プレイ条件", "⚙️ パーツ設定", "📋 保存データ"])

# ------------------------------------------
# タブ1: プレイ条件（毎回入力する頻度が高い項目）
# ------------------------------------------
with tab1:
    st.subheader("奥移動〜落下までの時間")
    st.number_input(
        "秒", value=st.session_state.t_d, step=0.1, format="%.2f", key="t_d_input",
        on_change=lambda: st.session_state.update(t_d=st.session_state.t_d_input),
    )
    st.session_state.t_d = st.session_state.t_d_input

    qcol1, qcol2, qcol3, qcol4 = st.columns(4)
    with qcol1:
        st.button("−0.5", use_container_width=True, on_click=adjust_t_d, args=(-0.5,))
    with qcol2:
        st.button("−0.1", use_container_width=True, on_click=adjust_t_d, args=(-0.1,))
    with qcol3:
        st.button("+0.1", use_container_width=True, on_click=adjust_t_d, args=(0.1,))
    with qcol4:
        st.button("+0.5", use_container_width=True, on_click=adjust_t_d, args=(0.5,))

    t_d = st.session_state.t_d

    st.subheader("フックの向き（時計の文字盤）")
    st.caption(f"現在の選択: **{st.session_state.hook_clock}時**")
    clock_layout = [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]
    for row in clock_layout:
        cols = st.columns(4)
        for i, num in enumerate(row):
            is_selected = st.session_state.hook_clock == num
            label = f"● {num}" if is_selected else str(num)
            if cols[i].button(label, key=f"clock_{num}", use_container_width=True):
                st.session_state.hook_clock = num
    hook_clock = float(st.session_state.hook_clock)

    st.subheader("🔵 手動入力（実測の周期）")
    T_manual = st.number_input("1往復の秒数", value=0.85, step=0.01, format="%.2f")

# ------------------------------------------
# タブ2: パーツ設定（毎回は変えない項目なので分離）
# ------------------------------------------
with tab2:
    st.subheader("🔴 自動計算（チェーン＋リング）")
    st.caption("※モノタロウ規格（鉄マンテルチェーン）の実測値準拠")

    chain_type = st.selectbox("チェーンの線径 (規格質量)", [
        "1.6mm (0.58 g/cm)",
        "2.0mm (0.88 g/cm)",
        "2.6mm (1.48 g/cm)",
        "3.2mm (2.26 g/cm)"
    ])
    L_chain = st.number_input("チェーンの長さ (cm)", value=15.0, step=1.0, format="%.1f")

    st.subheader("⭕ リング")
    D_ring = st.number_input("リングの直径 (cm)", value=10.0, step=0.1, format="%.1f")
    ring_type = st.selectbox("リングの線の太さ", [
        "8.0mm (極太)",
        "7.0mm (太め)",
        "6.0mm (標準・カインズ基準)",
        "5.0mm (やや細め)",
        "4.0mm (細め)"
    ], index=2)
    d_ring_mm = float(ring_type.split("mm")[0])

# ==========================================
# 自動計算の物理ロジック
# ==========================================
if "1.6mm" in chain_type:
    chain_density = 0.58
elif "2.0mm" in chain_type:
    chain_density = 0.88
elif "2.6mm" in chain_type:
    chain_density = 1.48
elif "3.2mm" in chain_type:
    chain_density = 2.26
else:
    chain_density = 0.58

m_chain = chain_density * L_chain
y_chain = L_chain / 2.0

density_ring = 7.85
r_ring_cm = (d_ring_mm / 10.0) / 2.0
R_center_cm = (D_ring / 2.0) - r_ring_cm
m_ring = (math.pi * r_ring_cm**2) * (2 * math.pi * R_center_cm) * density_ring if R_center_cm > 0 else 0
y_ring = L_chain + (D_ring / 2.0)

L_cm = (m_chain * y_chain + m_ring * y_ring) / (m_chain + m_ring) if (m_chain + m_ring) > 0 else 0
g = 9.80665

T_auto = 2 * math.pi * math.sqrt((L_cm / 100.0) / g) if L_cm > 0 else 0
x_auto, y_auto, vx_auto = calc_timing(T_auto, t_d, hook_clock)
dir_auto = "右" if vx_auto >= 0 else "左"

x_manual, y_manual, vx_manual = calc_timing(T_manual, t_d, hook_clock)
dir_manual = "右" if vx_manual >= 0 else "左"

L_manual_cm = 0
if T_manual > 0:
    L_manual_cm = g * (T_manual / (2 * math.pi)) ** 2 * 100

# ==========================================
# 結果表示（タブの外＝常に見える位置に固定）
# ==========================================
st.divider()
st.subheader("📊 予測結果")

rcol1, rcol2 = st.columns(2)
with rcol1:
    st.markdown("**🔴 自動計算**")
    st.write(f"周期: 約 {T_auto:.2f}秒 (重心 {L_cm:.1f}cm)")
    if T_auto > 0:
        st.markdown(f"### {'右' if x_auto >= 0 else '左'}側 約{abs(x_auto*100):.0f}% / {dir_auto}方向")

with rcol2:
    st.markdown("**🔵 手動入力**")
    st.write(f"周期: {T_manual:.2f}秒 (逆算重心 {L_manual_cm:.1f}cm)")
    if T_manual > 0:
        st.markdown(f"### {'右' if x_manual >= 0 else '左'}側 約{abs(x_manual*100):.0f}% / {dir_manual}方向")

# --- 1次元グラフ描画 ---
fig, ax = plt.subplots(figsize=(8, 3))
ax.plot([-1.2, 1.2], [0, 0], color='black', linewidth=1.5)
ax.plot([-1, 1], [0, 0], '|', color='gray', markersize=20)
ax.axvline(0, color='gray', linestyle=':', linewidth=1)

ax.text(-1, 0.1, "左端", ha='center', fontsize=12)
ax.text(1, 0.1, "右端", ha='center', fontsize=12)
ax.text(0, -0.4, "中心\n(落下目標)", ha='center', fontsize=12, color='green')
ax.plot(0, 0, 'go', markersize=6)

if T_auto > 0:
    ax.plot(x_auto, 0, 'ro', markersize=14, alpha=0.7)
    if abs(vx_auto) > 0.01:
        v_sign = 1 if vx_auto > 0 else -1
        ax.arrow(x_auto, 0, v_sign * 0.15, 0, head_width=0.08, head_length=0.06, fc='red', ec='red', linewidth=2)
    ax.text(x_auto, 0.25, f"自動(赤)\n{abs(x_auto*100):.0f}%", color='red', ha='center', va='bottom', fontweight='bold', fontsize=10)

if T_manual > 0:
    ax.plot(x_manual, 0, 'bo', markersize=14, alpha=0.7)
    if abs(vx_manual) > 0.01:
        v_sign = 1 if vx_manual > 0 else -1
        ax.arrow(x_manual, 0, v_sign * 0.15, 0, head_width=0.08, head_length=0.06, fc='blue', ec='blue', linewidth=2)
    ax.text(x_manual, -0.15, f"手動(青)\n{abs(x_manual*100):.0f}%", color='blue', ha='center', va='top', fontweight='bold', fontsize=10)

ax.set_xlim(-1.5, 1.5)
ax.set_ylim(-0.7, 0.7)
ax.axis('off')
st.pyplot(fig)

# ==========================================
# データの保存機能
# ==========================================
st.divider()
st.subheader("💾 現在のパラメータを保存")

st.text_input("店舗・筐体名 (例: 〇〇店 UFO9 1番台 右側)", key="store_name")
if st.button("設定を保存する", use_container_width=True):
    if st.session_state.store_name:
        chain_mm = chain_type.split(" ")[0]

        st.session_state.saved_configs.append({
            "店舗_筐体名": st.session_state.store_name,
            "落下時間": f"{t_d:.2f}秒",
            "フック向き": f"{hook_clock:.0f}時",
            "チェーン": f"{chain_mm}, 長さ{L_chain:.1f}cm",
            "リング": f"直径{D_ring:.1f}cm (太さ{d_ring_mm:.1f}mm)",
            "自動_周期": f"{T_auto:.2f}秒",
            "自動_重心": f"{L_cm:.1f}cm",
            "自動_位置": f"{abs(x_auto*100):.0f}% (VX:{dir_auto})",
            "手動_周期": f"{T_manual:.2f}秒",
            "手動_重心": f"{L_manual_cm:.1f}cm",
            "手動_位置": f"{abs(x_manual*100):.0f}% (VX:{dir_manual})"
        })
        st.success("保存しました！「保存データ」タブに追加されています。")
    else:
        st.warning("店舗・筐体名を入力してください。")

# ------------------------------------------
# タブ3: 保存データ一覧 + 書き出し
# ------------------------------------------
with tab3:
    if len(st.session_state.saved_configs) == 0:
        st.info("まだ保存されたデータがありません。")
    else:
        st.caption("※VXは動く方向（Velocity X）を示します。")

        # --- 書き出し(JSON / CSV) ---
        dcol1, dcol2 = st.columns(2)
        json_bytes = json.dumps(st.session_state.saved_configs, ensure_ascii=False, indent=2).encode("utf-8")
        with dcol1:
            st.download_button(
                "📥 JSONで保存(次回読込用)",
                data=json_bytes,
                file_name=f"crane_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json",
                mime="application/json",
                use_container_width=True,
            )

        csv_buf = io.StringIO()
        if st.session_state.saved_configs:
            writer = csv.DictWriter(csv_buf, fieldnames=list(st.session_state.saved_configs[0].keys()))
            writer.writeheader()
            writer.writerows(st.session_state.saved_configs)
        with dcol2:
            st.download_button(
                "📊 CSVで保存(閲覧・分析用)",
                data=csv_buf.getvalue().encode("utf-8-sig"),
                file_name=f"crane_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        st.divider()

        for idx, data in enumerate(reversed(st.session_state.saved_configs)):
            with st.container(border=True):
                st.markdown(f"### 🕹️ {data['店舗_筐体名']}")
                st.markdown(f"**🔹 プレイ条件:** 落下 **{data['落下時間']}** / フック **{data['フック向き']}**")
                st.markdown(f"**🔹 パーツ寸法:** チェーン **{data['チェーン']}** / リング **{data['リング']}**")
                st.markdown(f"🔴 **自動計算:** 左右 **{data['自動_位置']}** (周期 {data['自動_周期']} / 目算重心 {data['自動_重心']})")
                st.markdown(f"🔵 **手動入力:** 左右 **{data['手動_位置']}** (周期 {data['手動_周期']} / **逆算重心 {data['手動_重心']}**)")

        st.write("")
        if st.button("🗑️ 保存データをすべて消去", use_container_width=True):
            st.session_state.saved_configs = []
            st.rerun()
