import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
import math
from datetime import datetime

st.set_page_config(page_title="クレーンゲーム攻略予測", layout="wide")

st.title("クレーンゲーム 3次元攻略予測")
st.write("目標座標からUFO本体の停止位置を算出し、X軸の操作タイミングを逆算します。")

# --- 保存データと入力欄の初期化 ---
if "saved_configs" not in st.session_state:
    st.session_state.saved_configs = []

if "store_name" not in st.session_state:
    st.session_state.store_name = f"{datetime.now().strftime('%m/%d')} 〇〇店 UFO9 1番台 右側"

# --- 物理逆算ソルバー ---
def calc_dynamics(T, t_d, hook_clock, hook_size, v_y_cm_s, L_cm, A_x_cm):
    if T <= 0 or L_cm <= 0 or A_x_cm <= 0: 
        return 0, 0, 0, 0, 0, 0, 0, "右", False
    
    # フックの中心（理想の落下位置）は開口サイズの半分
    D_hook = hook_size / 2.0

    # 1. ターゲット座標 (X_aim, Y_aim)
    target_rad = math.radians((3 - hook_clock) * 30)
    if target_rad < 0: target_rad += 2 * math.pi
    X_aim = D_hook * math.cos(target_rad)
    Y_aim = D_hook * math.sin(target_rad)
    
    # 2. Y軸の慣性振幅と t_d における変位
    v_y_m_s = v_y_cm_s / 100.0
    L_m = L_cm / 100.0
    g = 9.80665
    omega = math.sqrt(g / L_m)
    A_y_cm = (v_y_m_s / omega) * 100 
    Y_swing = A_y_cm * math.sin(omega * t_d)
    
    # 3. 直線引きずり条件からUFO停止座標 (UFO_x, UFO_y) を算出
    if abs(Y_aim) > 0.01:
        c = 1.0 - (Y_swing / Y_aim)
        UFO_x = c * X_aim
        UFO_y = c * Y_aim
    else:
        UFO_x = X_aim
        UFO_y = -Y_swing
        
    X_req = X_aim - UFO_x # t_d において必要なX軸の相対変位
    
    # 4. X軸のタイミング逆算
    if abs(X_req) > A_x_cm:
        # 振幅が不足しており、物理的に到達不可能
        return UFO_x, UFO_y, X_aim, Y_aim, X_req, Y_swing, 0, "右", False
        
    R = X_req / A_x_cm
    theta1 = math.asin(R)
    theta2 = math.pi - theta1
    
    # フックへ向かう（中心へ戻る）速度ベクトルを持つ位相を選択
    if R * math.cos(theta1) <= 0:
        theta_td = theta1
    else:
        theta_td = theta2
        
    # t=0（ボタン押下時）の位相と座標
    phi = theta_td - (omega * t_d)
    x_push = A_x_cm * math.sin(phi)
    v_dir = "右" if math.cos(phi) >= 0 else "左"
    
    return UFO_x, UFO_y, X_aim, Y_aim, X_req, Y_swing, x_push, v_dir, True

# ==========================================
# 左側メニュー (パラメータ入力)
# ==========================================
st.sidebar.header("1. プレイ条件")
t_d = st.sidebar.number_input("奥移動〜落下までの時間 (秒)", value=3.00, step=0.1, format="%.2f")
A_x_cm = st.sidebar.number_input("X軸の揺れ幅 (片側最大振幅 cm)", value=15.0, step=1.0, format="%.1f")

st.sidebar.subheader("🎯 フック（原点）の設定")
hook_clock = st.sidebar.number_input("フックの向き (時計の文字盤: 1〜12)", value=12.0, step=1.0, min_value=1.0, max_value=12.0)
hook_size = st.sidebar.number_input("フックの開口サイズ (根元〜先端 cm)", value=4.0, step=0.5, format="%.1f")
st.sidebar.caption("※リングがフックの中央に落ちるよう自動計算されます。")

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

# 質量・重心計算
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

u_x_a, u_y_a, aim_x, aim_y, req_x_a, swing_y_a, push_x_a, dir_a, possible_a = calc_dynamics(T_auto, t_d, hook_clock, hook_size, v_y_cm_s, L_cm, A_x_cm)

st.sidebar.divider()

st.sidebar.header("3. 🔵手動入力 (周期指定)")
T_manual = st.sidebar.number_input("手動の周期 (秒)", value=0.85, step=0.01, format="%.2f")
L_manual_cm = g * (T_manual / (2 * math.pi))**2 * 100 if T_manual > 0 else 0

u_x_m, u_y_m, _, _, req_x_m, swing_y_m, push_x_m, dir_m, possible_m = calc_dynamics(T_manual, t_d, hook_clock, hook_size, v_y_cm_s, L_manual_cm, A_x_cm)

# ==========================================
# メイン画面 (2Dマップと1Dタイミング)
# ==========================================
st.subheader("🗺️ 2Dマップ (UFO停止座標と軌道)")

fig2d, ax2d = plt.subplots(figsize=(10, 10))
# マップの表示範囲を動的に調整
max_r = max(10, abs(u_x_a)+5, abs(u_y_a)+5, hook_size+5, abs(swing_y_a)+5, A_x_cm+5)
ax2d.set_xlim(-max_r, max_r)
ax2d.set_ylim(-max_r, max_r)
ax2d.grid(True, linestyle='--', alpha=0.5)

# 基準線とフック
ax2d.axhline(0, color='black', linewidth=1)
ax2d.axvline(0, color='black', linewidth=1)
ax2d.plot(0, 0, marker='*', color='gold', markersize=30, markeredgecolor='black', label="フック根元 (0,0)")
# フックのサイズ感を示す矢印
ax2d.arrow(0, 0, aim_x*2, aim_y*2, head_width=1.0, head_length=1.5, fc='gold', ec='orange', linewidth=2, alpha=0.5)

# 自動計算のプロット
if T_auto > 0 and possible_a:
    ax2d.axhline(u_y_a, color='red', linestyle=':', linewidth=1, alpha=0.4)
    ax2d.axvline(u_x_a, color='red', linestyle=':', linewidth=1, alpha=0.4)
    ax2d.plot(u_x_a, u_y_a, marker='X', color='red', markersize=15, label="UFO停止座標 (自動)")
    ax2d.plot(aim_x, aim_y, marker='o', color='lightcoral', markersize=10, label="目標着地点 (フック中央)")
    ax2d.annotate('', xy=(u_x_a, u_y_a), xytext=(aim_x, aim_y),
                  arrowprops=dict(facecolor='red', edgecolor='red', arrowstyle='->', lw=3, alpha=0.7))

# 手動入力のプロット
if T_manual > 0 and possible_m:
    ax2d.axhline(u_y_m, color='blue', linestyle=':', linewidth=1, alpha=0.4)
    ax2d.axvline(u_x_m, color='blue', linestyle=':', linewidth=1, alpha=0.4)
    ax2d.plot(u_x_m, u_y_m, marker='X', color='blue', markersize=15, label="UFO停止座標 (手動)")
    ax2d.annotate('', xy=(u_x_m, u_y_m), xytext=(aim_x, aim_y),
                  arrowprops=dict(facecolor='blue', edgecolor='blue', arrowstyle='->', lw=3, alpha=0.7))

ax2d.set_xlabel("X座標 (cm)", fontsize=12)
ax2d.set_ylabel("Y座標 (cm) ※奥方向が正", fontsize=12)
ax2d.legend(loc='upper left', fontsize=10)
ax2d.set_aspect('equal')
st.pyplot(fig2d)

# --- 1次元グラフ描画 (X軸タイミング) ---
st.write("---")
st.subheader("⏱️ X軸 プッシュタイミング (1D)")

fig, ax = plt.subplots(figsize=(10, 2)) 
ax.plot([-A_x_cm*1.1, A_x_cm*1.1], [0, 0], color='black', linewidth=1.5)
ax.plot([-A_x_cm, A_x_cm], [0, 0], '|', color='gray', markersize=20)
ax.axvline(0, color='gray', linestyle=':', linewidth=1)
ax.text(-A_x_cm, 0.1, "左端", ha='center', fontsize=12)
ax.text(A_x_cm, 0.1, "右端", ha='center', fontsize=12)
ax.plot(0, 0, 'ko', markersize=4) 

if T_auto > 0:
    if possible_a:
        ax.plot(push_x_a, 0, 'ro', markersize=14, alpha=0.7)
        v_sign_a = 1 if dir_a == "右" else -1
        ax.arrow(push_x_a, 0, v_sign_a * (A_x_cm*0.1), 0, head_width=0.08, head_length=0.06, fc='red', ec='red', linewidth=2)
    else:
        st.error("🔴 自動計算: 設定されたX軸振幅では目標座標への到達が不可能です。")

if T_manual > 0:
    if possible_m:
        ax.plot(push_x_m, 0, 'bo', markersize=14, alpha=0.7)
        v_sign_m = 1 if dir_m == "右" else -1
        ax.arrow(push_x_m, 0, v_sign_m * (A_x_cm*0.1), 0, head_width=0.08, head_length=0.06, fc='blue', ec='blue', linewidth=2)
    else:
        st.error("🔵 手動入力: 設定されたX軸振幅では目標座標への到達が不可能です。")

ax.set_xlim(-A_x_cm*1.2, A_x_cm*1.2)
ax.set_ylim(-0.7, 0.7)
ax.axis('off') 
st.pyplot(fig)

# --- 座標出力 ---
col1, col2 = st.columns(2)
with col1:
    if possible_a:
        st.info(f"🔴 **【自動】**\n\nUFO停止座標: **X {u_x_a:+.1f} / Y {u_y_a:+.1f}**\n\nプッシュ位置: **{push_x_a:+.1f} cm ({dir_a}方向)**")
with col2:
    if possible_m:
        st.info(f"🔵 **【手動】**\n\nUFO停止座標: **X {u_x_m:+.1f} / Y {u_y_m:+.1f}**\n\nプッシュ位置: **{push_x_m:+.1f} cm ({dir_m}方向)**")

# ==========================================
# データの保存・出力
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
                "フック": f"{hook_clock}時 (開口サイズ{hook_size}cm)",
                "自動_UFO停止": f"X: {u_x_a:+.1f} / Y: {u_y_a:+.1f}" if possible_a else "到達不可",
                "手動_UFO停止": f"X: {u_x_m:+.1f} / Y: {u_y_m:+.1f}" if possible_m else "到達不可"
            })
            st.success(f"保存しました。")
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
