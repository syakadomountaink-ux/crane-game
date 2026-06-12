import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
import math
from datetime import datetime

# ページ設定
st.set_page_config(page_title="クレーンゲーム攻略予測", layout="wide")

st.title("クレーンゲーム 3次元攻略予測 (Phase3: 引きずり逆算マップ)")
st.write("リングが「本体中心に引きずられる軌道」を逆算し、フックに完璧に掛かるUFO停止位置を割り出します。")

# --- 保存データと入力欄の初期化 ---
if "saved_configs" not in st.session_state:
    st.session_state.saved_configs = []

if "store_name" not in st.session_state:
    st.session_state.store_name = f"{datetime.now().strftime('%m/%d')} 〇〇店 UFO9 1番台 右側"

# --- 物理逆算ソルバー ---
def calc_perfect_drag(T, t_d, hook_clock, D_hook, v_y_cm_s, L_cm):
    if T <= 0 or L_cm <= 0: return 0, 0, 0, 0, 0, 0
    
    # 1. リングの理想の落下地点 (X_aim, Y_aim)
    target_rad = math.radians((3 - hook_clock) * 30)
    if target_rad < 0: target_rad += 2 * math.pi
    X_aim = D_hook * math.cos(target_rad)
    Y_aim = D_hook * math.sin(target_rad)
    
    # 2. t_dにおけるY軸の慣性揺れ (Y_swing)
    v_y_m_s = v_y_cm_s / 100.0
    L_m = L_cm / 100.0
    g = 9.80665
    omega = math.sqrt(g / L_m)
    A_y_cm = (v_y_m_s / omega) * 100 
    Y_swing = A_y_cm * math.sin(omega * t_d)
    
    # 3. 引きずり軌道が原点(0,0)を通るためのUFO停止位置 (UFO_x, UFO_y) を逆算
    # リング落下点(X_aim, Y_aim)とUFO本体が原点を通る直線上にある条件から算出
    if abs(Y_aim) > 0.01:
        c = 1.0 - (Y_swing / Y_aim)
        UFO_x = c * X_aim
        UFO_y = c * Y_aim
        X_swing_req = X_aim - UFO_x
    else:
        # フックが真横(3時/9時)の場合、Y_swingがある限り完全な直線引きずりは不可能。
        # 最善の妥協点としてY軸のズレを受け入れ、X軸のみ合わせる。
        UFO_x = X_aim
        UFO_y = -Y_swing
        X_swing_req = 0.0
        
    return UFO_x, UFO_y, X_aim, Y_aim, X_swing_req, Y_swing

# ==========================================
# 左側メニュー (パラメータ入力)
# ==========================================
st.sidebar.header("1. プレイ条件 (共通)")
t_d = st.sidebar.number_input("奥移動〜落下までの時間 (秒)", value=3.00, step=0.1, format="%.2f")

st.sidebar.subheader("🎯 フック（原点）の設定")
hook_clock = st.sidebar.number_input("フックの向き (時計の文字盤: 1〜12)", value=12.0, step=1.0, min_value=1.0, max_value=12.0)
D_hook = st.sidebar.number_input("リングを落とす深さ (cm)", value=3.0, step=0.5, format="%.1f")
st.sidebar.caption("※フックの開いている奥へ、何cm深くリングを落とすか")

st.sidebar.subheader("🚚 筐体の移動スペック")
v_y_cm_s = st.sidebar.number_input("Y軸の移動速度 (cm/秒)", value=15.0, step=1.0, format="%.1f")

st.sidebar.divider()

st.sidebar.header("2. 🔴自動計算 (チェーン＋リング)")
chain_type = st.sidebar.selectbox("チェーンの線径", ["1.6mm (0.58g/cm)", "2.0mm (0.82g/cm)"])
L_chain = st.sidebar.number_input("チェーンの長さ (cm)", value=15.0, step=1.0, format="%.1f")

st.sidebar.subheader("⭕ リング")
D_ring = st.sidebar.number_input("リングの直径 (cm)", value=10.0, step=0.1, format="%.1f")
ring_type = st.sidebar.selectbox("線の太さ", ["6.0mm (標準・カインズ基準)", "5.0mm (やや細め)", "4.0mm (細め)", "3.0mm (極細)"])
d_ring_mm = float(ring_type.split("mm")[0])

# 自動計算ロジック
chain_density = 0.58 if "1.6mm" in chain_type else 0.82
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

ufo_x_auto, ufo_y_auto, aim_x, aim_y, x_swing_auto, y_swing_auto = calc_perfect_drag(T_auto, t_d, hook_clock, D_hook, v_y_cm_s, L_cm)

st.sidebar.divider()

st.sidebar.header("3. 🔵手動入力 (周期指定)")
T_manual = st.sidebar.number_input("手動の周期 (秒)", value=0.85, step=0.01, format="%.2f")
L_manual_cm = g * (T_manual / (2 * math.pi))**2 * 100 if T_manual > 0 else 0

ufo_x_man, ufo_y_man, _, _, x_swing_man, y_swing_man = calc_perfect_drag(T_manual, t_d, hook_clock, D_hook, v_y_cm_s, L_manual_cm)

# ==========================================
# メイン画面 (2D逆算マップ)
# ==========================================
st.subheader("🗺️ 引きずり軌道 逆算2Dマップ (真上からの視点)")
st.write("フック（★）に引きずり込むために、**UFO本体（×）をどこで停止させるべきか**を逆算しました。")

fig2d, ax2d = plt.subplots(figsize=(10, 10))
max_r = max(10, abs(ufo_x_auto)+5, abs(ufo_y_auto)+5, D_hook+5, abs(y_swing_auto)+5)
ax2d.set_xlim(-max_r, max_r)
ax2d.set_ylim(-max_r, max_r)
ax2d.grid(True, linestyle='--', alpha=0.5)

# 十字線とフック
ax2d.axhline(0, color='black', linewidth=1)
ax2d.axvline(0, color='black', linewidth=1)
ax2d.plot(0, 0, marker='*', color='gold', markersize=35, markeredgecolor='black', label="フック (目標原点)")

# フックの向きを示す矢印
ax2d.arrow(0, 0, aim_x*0.5, aim_y*0.5, head_width=1.0, head_length=1.5, fc='gold', ec='orange', linewidth=3, alpha=0.5)

# 🔴自動計算のプロット
if T_auto > 0:
    # UFO停止位置
    ax2d.plot(ufo_x_auto, ufo_y_auto, marker='X', color='red', markersize=18, label="UFO停止座標 (自動)")
    # リング落下位置
    ax2d.plot(aim_x, aim_y, marker='o', color='lightcoral', markersize=12, label="リング落下地点")
    
    # 揺れの軌道 (UFO -> 落下点) 点線
    ax2d.plot([ufo_x_auto, aim_x], [ufo_y_auto, aim_y], color='red', linestyle=':', linewidth=2, alpha=0.5)
    
    # ★引きずりの軌道 (落下点 -> UFO) 太い実線矢印
    ax2d.annotate('', xy=(ufo_x_auto, ufo_y_auto), xytext=(aim_x, aim_y),
                  arrowprops=dict(facecolor='red', edgecolor='red', arrowstyle='->', lw=4, alpha=0.8))

# 🔵手動入力のプロット
if T_manual > 0:
    ax2d.plot(ufo_x_man, ufo_y_man, marker='X', color='blue', markersize=18, label="UFO停止座標 (手動)")
    ax2d.plot([ufo_x_man, aim_x], [ufo_y_man, aim_y], color='blue', linestyle=':', linewidth=2, alpha=0.5)
    ax2d.annotate('', xy=(ufo_x_man, ufo_y_man), xytext=(aim_x, aim_y),
                  arrowprops=dict(facecolor='blue', edgecolor='blue', arrowstyle='->', lw=4, alpha=0.8))

ax2d.set_xlabel("左右 X軸 (cm)", fontsize=12)
ax2d.set_ylabel("前後 Y軸 (cm) ※上が奥方向", fontsize=12)
ax2d.legend(loc='upper left', fontsize=10)
ax2d.set_aspect('equal')
st.pyplot(fig2d)

# --- 座標とタイミングの数値出力 ---
col1, col2 = st.columns(2)
with col1:
    st.info(f"🔴 **【自動】UFO停止座標:**\n\n X(左右): **{ufo_x_auto:+.1f} cm** / Y(前後): **{ufo_y_auto:+.1f} cm**\n\n*(※必要な左右の横揺れ幅: {abs(x_swing_auto):.1f} cm)*")
with col2:
    st.info(f"🔵 **【手動】UFO停止座標:**\n\n X(左右): **{ufo_x_man:+.1f} cm** / Y(前後): **{ufo_y_man:+.1f} cm**\n\n*(※必要な左右の横揺れ幅: {abs(x_swing_man):.1f} cm)*")

# ==========================================
# データの保存機能
# ==========================================
st.divider()
st.subheader("💾 現在のパラメータを保存")
save_col1, save_col2 = st.columns([3, 1])
with save_col1:
    st.text_input("店舗・筐体名 (例: 〇〇店 UFO9 1番台 右側)", key="store_name")
with save_col2:
    st.write("") 
    if st.button("設定を保存する"):
        if st.session_state.store_name:
            chain_mm = chain_type.split(" ")[0] 
            st.session_state.saved_configs.append({
                "店舗_筐体名": st.session_state.store_name,
                "フック": f"{hook_clock}時 (深さ{D_hook}cm)",
                "自動_UFO停止": f"X: {ufo_x_auto:+.1f} / Y: {ufo_y_auto:+.1f}",
                "手動_UFO停止": f"X: {ufo_x_man:+.1f} / Y: {ufo_y_man:+.1f}"
            })
            st.success(f"保存しました！")
        else:
            st.warning("店舗・筐体名を入力してください。")

if len(st.session_state.saved_configs) > 0:
    st.divider()
    st.subheader("📸 スクショ用 攻略メモ出力")
    with st.container(border=True):
        for data in reversed(st.session_state.saved_configs):
            with st.container(border=True): 
                st.markdown(f"### 🕹️ {data['店舗_筐体名']}")
                st.markdown(f"**🔹 フック設定:** {data['フック']}")
                st.markdown(f"🔴 **【自動】UFO停止座標:** **{data['自動_UFO停止']}**")
                st.markdown(f"🔵 **【手動】UFO停止座標:** **{data['手動_UFO停止']}**")
    st.write("") 
    if st.button("🗑️ 保存データをすべて消去"):
        st.session_state.saved_configs = []
        st.rerun()
