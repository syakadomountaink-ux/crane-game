import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
import math
from datetime import datetime

# ページ設定
st.set_page_config(page_title="クレーンゲーム攻略予測", layout="wide")

st.title("クレーンゲーム 3次元攻略予測 (Phase2: 2Dターゲットマップ)")
st.write("目標位置から逆算し、「UFO本体をどこで止めればリングが目標に落ちるか」をマップ化します。")

# --- 保存データと入力欄の初期化 ---
if "saved_configs" not in st.session_state:
    st.session_state.saved_configs = []

if "store_name" not in st.session_state:
    st.session_state.store_name = f"{datetime.now().strftime('%m/%d')} 〇〇店 UFO9 1番台 右側"

# --- 共通の計算関数 ---
def calc_timing(T, t_d, hook_clock, v_y_cm_s, L_cm):
    if T <= 0 or L_cm <= 0: return 0, 0, 0, 0
    
    # 既存のX軸(位相)の計算
    phase_advance_deg = (t_d % T) / T * 360
    target_deg = (3 - hook_clock) * 30
    if target_deg < 0: target_deg += 360
    hook_rad = math.radians(target_deg)

    press_phase_deg = (180 - phase_advance_deg) % 360
    press_phase_rad = math.radians(press_phase_deg)
    
    displacement = math.sin(press_phase_rad) 
    velocity = math.cos(press_phase_rad)

    x_pos = displacement * math.cos(hook_rad)
    v_x = velocity * math.cos(hook_rad)
    
    # Y軸(前後)の慣性揺れ計算
    v_y_m_s = v_y_cm_s / 100.0
    L_m = L_cm / 100.0
    g = 9.80665
    omega = math.sqrt(g / L_m)
    
    # Y軸の最大振幅 (cm)
    A_y_cm = (v_y_m_s / omega) * 100 
    
    # 落下時間(t_d)におけるY軸の変位 (cm)
    y_pos_cm = A_y_cm * math.sin(omega * t_d)
    
    return x_pos, v_x, A_y_cm, y_pos_cm

# ==========================================
# 左側メニュー (パラメータ入力)
# ==========================================
st.sidebar.header("1. プレイ条件 (共通)")
t_d = st.sidebar.number_input("奥移動〜落下までの時間 (秒)", value=3.00, step=0.1, format="%.2f")

st.sidebar.subheader("🎯 ターゲット逆算設定")
hook_clock = st.sidebar.number_input("フックの向き (時計の文字盤: 1〜12)", value=3.0, step=1.0, min_value=1.0, max_value=12.0)
D_hook = st.sidebar.number_input("狙う位置のズレ (cm)", value=2.0, step=0.5, format="%.1f")
st.sidebar.caption("※フックの開いている方向に、目標から何cmずらして落とすか")

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

# 自動計算の物理ロジック
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

x_auto, vx_auto, Ay_auto, y_pos_auto = calc_timing(T_auto, t_d, hook_clock, v_y_cm_s, L_cm)
dir_auto = "右" if vx_auto >= 0 else "左"

st.sidebar.divider()

st.sidebar.header("3. 🔵手動入力 (周期指定)")
T_manual = st.sidebar.number_input("手動の周期 (秒)", value=0.85, step=0.01, format="%.2f")

L_manual_cm = 0
if T_manual > 0:
    L_manual_cm = g * (T_manual / (2 * math.pi))**2 * 100

x_manual, vx_manual, Ay_manual, y_pos_manual = calc_timing(T_manual, t_d, hook_clock, v_y_cm_s, L_manual_cm)
dir_manual = "右" if vx_manual >= 0 else "左"

# --- 2Dマップ用の座標計算 (目標を原点0,0とする) ---
# フックの向きによるオフセット位置 (リングをここに落としたい)
target_rad = math.radians((3 - hook_clock) * 30)
if target_rad < 0: target_rad += 2 * math.pi
X_aim = D_hook * math.cos(target_rad)
Y_aim = D_hook * math.sin(target_rad)

# UFOを止めるべき位置 (目標落下位置 - 慣性によるズレ)
X_stop_auto = X_aim  # X軸はタイミングで合わせるため、基準位置は目標のXと同じ
Y_stop_auto = Y_aim - y_pos_auto

X_stop_manual = X_aim
Y_stop_manual = Y_aim - y_pos_manual

# ==========================================
# メイン画面 (結果とグラフ)
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔴 自動計算")
    st.write(f"**UFO停止位置:** X: **{X_stop_auto:.1f}cm** / Y(奥): **{Y_stop_auto:.1f}cm**")
    st.caption(f"周期 {T_auto:.2f}秒 / 振幅 ±{Ay_auto:.1f}cm")

with col2:
    st.subheader("🔵 手動入力")
    st.write(f"**UFO停止位置:** X: **{X_stop_manual:.1f}cm** / Y(奥): **{Y_stop_manual:.1f}cm**")
    st.caption(f"周期 {T_manual:.2f}秒 / 振幅 ±{Ay_manual:.1f}cm")

# --- 2Dマップ描画 ---
st.write("---")
st.subheader("🗺️ 2Dターゲットマップ (真上からの視点)")
st.write("景品（☆）を基準に、**UFO本体をどこで止めればよいか**を示します。矢印は落下時のリングの軌道です。")

fig2d, ax2d = plt.subplots(figsize=(8, 8))
max_range = max(10, abs(Y_stop_auto) + 5, abs(Y_stop_manual) + 5, D_hook + 5)
ax2d.set_xlim(-max_range, max_range)
ax2d.set_ylim(-max_range, max_range)
ax2d.grid(True, linestyle='--', alpha=0.6)

# 十字の基準線
ax2d.axhline(0, color='black', linewidth=1)
ax2d.axvline(0, color='black', linewidth=1)

# 景品 (0,0)
ax2d.plot(0, 0, marker='*', color='gold', markersize=25, markeredgecolor='black', label="景品 (ターゲット)")

# 落下目標点
ax2d.plot(X_aim, Y_aim, marker='o', color='orange', markersize=12, label=f"理想の落下位置 ({hook_clock}時方向)")

# 自動計算のUFO停止位置と軌道
if T_auto > 0:
    ax2d.plot(X_stop_auto, Y_stop_auto, marker='X', color='red', markersize=15, label="UFO停止位置 (自動)")
    ax2d.annotate('', xy=(X_aim, Y_aim), xytext=(X_stop_auto, Y_stop_auto),
                  arrowprops=dict(facecolor='red', edgecolor='red', arrowstyle='->', lw=2.5, alpha=0.7))

# 手動入力のUFO停止位置と軌道
if T_manual > 0:
    ax2d.plot(X_stop_manual, Y_stop_manual, marker='X', color='blue', markersize=15, label="UFO停止位置 (手動)")
    ax2d.annotate('', xy=(X_aim, Y_aim), xytext=(X_stop_manual, Y_stop_manual),
                  arrowprops=dict(facecolor='blue', edgecolor='blue', arrowstyle='->', lw=2.5, alpha=0.7))

ax2d.set_xlabel("左右 X軸 (cm)", fontsize=12)
ax2d.set_ylabel("前後 Y軸 (cm) ※上が奥方向", fontsize=12)
ax2d.legend(loc='upper right', fontsize=10)
ax2d.set_aspect('equal') # 縦横比を1:1にして歪みをなくす
st.pyplot(fig2d)


# --- 1次元グラフ描画 (X軸タイミング) ---
st.write("---")
st.subheader("⏱️ X軸（左右）のプッシュタイミング")
st.write("UFOを上記のX座標に合わせた上で、リングが以下の位置を通る瞬間にY軸(奥移動)をスタートします。")
fig, ax = plt.subplots(figsize=(10, 2)) 
ax.plot([-1.2, 1.2], [0, 0], color='black', linewidth=1.5)
ax.plot([-1, 1], [0, 0], '|', color='gray', markersize=20)
ax.axvline(0, color='gray', linestyle=':', linewidth=1)
ax.text(-1, 0.1, "左端", ha='center', fontsize=12)
ax.text(1, 0.1, "右端", ha='center', fontsize=12)
ax.plot(0, 0, 'go', markersize=6) 

if T_auto > 0:
    ax.plot(x_auto, 0, 'ro', markersize=14, alpha=0.7)
    if abs(vx_auto) > 0.01:
        v_sign = 1 if vx_auto > 0 else -1
        ax.arrow(x_auto, 0, v_sign * 0.15, 0, head_width=0.08, head_length=0.06, fc='red', ec='red', linewidth=2)
if T_manual > 0:
    ax.plot(x_manual, 0, 'bo', markersize=14, alpha=0.7)
    if abs(vx_manual) > 0.01:
        v_sign = 1 if vx_manual > 0 else -1
        ax.arrow(x_manual, 0, v_sign * 0.15, 0, head_width=0.08, head_length=0.06, fc='blue', ec='blue', linewidth=2)

ax.set_xlim(-1.5, 1.5)
ax.set_ylim(-0.7, 0.7)
ax.axis('off') 
st.pyplot(fig)


# ==========================================
# データの保存機能・スクショ用 UIセクション
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
                "落下時間": f"{t_d:.2f}秒",
                "フック向き": f"{hook_clock}時 (ズレ{D_hook}cm)",
                "チェーン": f"{chain_mm}, 長さ{L_chain:.1f}cm",
                "リング": f"直径{D_ring:.1f}cm (太さ{d_ring_mm:.1f}mm)",
                "自動_停止": f"X:{X_stop_auto:.1f} / Y:{Y_stop_auto:.1f}",
                "手動_停止": f"X:{X_stop_manual:.1f} / Y:{Y_stop_manual:.1f}"
            })
            st.success(f"保存しました！画面下部に追加されています。")
        else:
            st.warning("店舗・筐体名を入力してください。")

if len(st.session_state.saved_configs) > 0:
    st.divider()
    st.subheader("📸 スクショ用 攻略メモ出力")
    with st.container(border=True):
        for data in reversed(st.session_state.saved_configs):
            with st.container(border=True): 
                st.markdown(f"### 🕹️ {data['店舗_筐体名']}")
                st.markdown(f"**🔹 条件:** 落下 **{data['落下時間']}** / フック **{data['フック向き']}**")
                st.markdown(f"**🔹 パーツ:** チェーン **{data['チェーン']}** / リング **{data['リング']}**")
                st.markdown(f"🔴 **自動計算 停止位置:** **{data['自動_停止']}**")
                st.markdown(f"🔵 **手動入力 停止位置:** **{data['手動_停止']}**")
    st.write("") 
    if st.button("🗑️ 保存データをすべて消去"):
        st.session_state.saved_configs = []
        st.rerun()
