import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
import math
from datetime import datetime

# ページ設定
st.set_page_config(page_title="クレーンゲーム攻略予測", layout="wide")

st.title("クレーンゲーム 横揺れ(X軸)攻略予測")
st.write("自動計算（赤）と手動の周期（青）を同時に比較し、ベストなタイミングを算出・保存します。")

# --- 保存データと入力欄の初期化 (セッションステート) ---
if "saved_configs" not in st.session_state:
    st.session_state.saved_configs = []

if "store_name" not in st.session_state:
    st.session_state.store_name = f"{datetime.now().strftime('%m/%d')} 〇〇店 UFO9 1番台 右側"

# --- 共通の計算関数 ---
def calc_timing(T, t_d, hook_clock):
    if T <= 0: return 0, 0, 0
    phase_advance_deg = (t_d % T) / T * 360
    
    target_deg = (3 - hook_clock) * 30
    if target_deg < 0: target_deg += 360
    hook_rad = math.radians(target_deg)

    press_phase_deg = (180 - phase_advance_deg) % 360
    press_phase_rad = math.radians(press_phase_deg)
    
    displacement = math.sin(press_phase_rad) 
    velocity = math.cos(press_phase_rad)

    x_pos = displacement * math.cos(hook_rad)
    y_pos = displacement * math.sin(hook_rad)
    v_x = velocity * math.cos(hook_rad)
    return x_pos, y_pos, v_x

# ==========================================
# 左側メニュー (パラメータ入力)
# ==========================================
st.sidebar.header("1. プレイ条件 (共通)")
t_d = st.sidebar.number_input("奥移動〜落下までの時間 (秒)", value=3.00, step=0.1, format="%.2f")
hook_clock = st.sidebar.number_input("フックの向き (時計の文字盤: 1〜12)", value=3.0, step=1.0, min_value=1.0, max_value=12.0)

st.sidebar.divider()

st.sidebar.header("2. 🔴自動計算 (チェーン＋リング)")
st.sidebar.caption("※PyBulletシミュレーションと同じ質量設定を追加しました")

chain_type = st.sidebar.selectbox("チェーンの線径・密度", [
    "3.0mm (シミュレーション設定: 約6.67g/cm)", 
    "1.6mm (現実の標準: 0.58g/cm)", 
    "2.0mm (現実の太め: 0.82g/cm)"
])
# 初期値をPyBulletの設定(14リンク×1.5cm = 21cm)に合わせる
L_chain = st.sidebar.number_input("チェーンの長さ (cm)", value=21.0, step=1.0, format="%.1f")

st.sidebar.subheader("⭕ リング")
# 初期値をPyBulletの設定(直径4cm)に合わせる
D_ring = st.sidebar.number_input("リングの直径 (cm)", value=4.0, step=0.1, format="%.1f")
ring_type = st.sidebar.selectbox("線の太さ・質量", [
    "3.0mm (シミュレーション設定: 固定50g)", 
    "6.0mm (標準・カインズ基準)", 
    "5.0mm (やや細め)", 
    "4.0mm (細め)", 
    "3.0mm (極細・現実の鉄)"
])

# ------------------------------------------
# 自動計算の物理ロジック (最新パラメータ反映)
# ------------------------------------------
if "シミュレーション設定" in chain_type:
    # 140g / 21cm = 約6.67g/cm
    chain_density = 140.0 / 21.0 
elif "1.6mm" in chain_type:
    chain_density = 0.58
else:
    chain_density = 0.82

m_chain = chain_density * L_chain
y_chain = L_chain / 2.0

if "シミュレーション設定" in ring_type:
    # PyBulletでの baseMass=0.05kg をそのまま使用
    m_ring = 50.0 
    d_ring_mm = 3.0
else:
    # 現実の鉄（密度7.85g/cm³）での体積計算
    d_ring_mm = float(ring_type.split("mm")[0])
    density_ring = 7.85
    r_ring_cm = (d_ring_mm / 10.0) / 2.0
    R_center_cm = (D_ring / 2.0) - r_ring_cm
    m_ring = (math.pi * r_ring_cm**2) * (2 * math.pi * R_center_cm) * density_ring if R_center_cm > 0 else 0

y_ring = L_chain + (D_ring / 2.0)

# 重心と周期の計算
L_cm = (m_chain * y_chain + m_ring * y_ring) / (m_chain + m_ring) if (m_chain + m_ring) > 0 else 0
g = 9.81 # PyBulletの重力値に合わせる

T_auto = 2 * math.pi * math.sqrt((L_cm / 100.0) / g) if L_cm > 0 else 0
x_auto, y_auto, vx_auto = calc_timing(T_auto, t_d, hook_clock)
dir_auto = "右" if vx_auto >= 0 else "左"

st.sidebar.divider()

st.sidebar.header("3. 🔵手動入力 (周期指定)")
st.sidebar.caption("ストップウォッチ等で測った1往復の秒数")
T_manual = st.sidebar.number_input("手動の周期 (秒)", value=0.85, step=0.01, format="%.2f")
x_manual, y_manual, vx_manual = calc_timing(T_manual, t_d, hook_clock)
dir_manual = "右" if vx_manual >= 0 else "左"

# 手動入力の周期から重心(L)を逆算
L_manual_cm = 0
if T_manual > 0:
    L_manual_cm = g * (T_manual / (2 * math.pi))**2 * 100

# ==========================================
# メイン画面 (結果とグラフ)
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔴 自動計算の結果")
    st.write(f"**推定周期:** 約 {T_auto:.2f} 秒 (目算重心: {L_cm:.1f}cm)")
    st.caption(f"※推定質量: チェーン {m_chain:.1f}g / リング {m_ring:.1f}g")
    if T_auto > 0:
        st.markdown(f"**X軸タイミング:** 【**{'右' if x_auto >= 0 else '左'}側に約 {abs(x_auto*100):.0f}%**】で【**{dir_auto}方向**】に動く瞬間")

with col2:
    st.subheader("🔵 手動入力の結果")
    st.write(f"**設定周期:** {T_manual:.2f} 秒 (逆算重心: **{L_manual_cm:.1f}cm**)")
    st.caption("※実際の揺れから算出した実質的な重心位置です")
    if T_manual > 0:
        st.markdown(f"**X軸タイミング:** 【**{'右' if x_manual >= 0 else '左'}側に約 {abs(x_manual*100):.0f}%**】で【**{dir_manual}方向**】に動く瞬間")

# --- 1次元グラフ描画 ---
fig, ax = plt.subplots(figsize=(10, 3.5)) 
ax.plot([-1.2, 1.2], [0, 0], color='black', linewidth=1.5)
ax.plot([-1, 1], [0, 0], '|', color='gray', markersize=20)
ax.axvline(0, color='gray', linestyle=':', linewidth=1)

ax.text(-1, 0.1, "左端", ha='center', fontsize=12)
ax.text(1, 0.1, "右端", ha='center', fontsize=12)
ax.text(0, -0.4, "中心\n(落下目標)", ha='center', fontsize=12, color='green')
ax.plot(0, 0, 'go', markersize=6) 

# 自動計算（赤）のプロット
if T_auto > 0:
    ax.plot(x_auto, 0, 'ro', markersize=14, alpha=0.7)
    if abs(vx_auto) > 0.01:
        v_sign = 1 if vx_auto > 0 else -1
        ax.arrow(x_auto, 0, v_sign * 0.15, 0, head_width=0.08, head_length=0.06, fc='red', ec='red', linewidth=2)
    ax.text(x_auto, 0.25, f"自動(赤)\n{abs(x_auto*100):.0f}%", color='red', ha='center', va='bottom', fontweight='bold', fontsize=10)

# 手動入力（青）のプロット
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
                "フック向き": f"{hook_clock}時",
                "チェーン": f"{chain_mm}, 長さ{L_chain:.1f}cm",
                "リング": f"直径{D_ring:.1f}cm (太さ{d_ring_mm:.1f}mm)",
                "自動_周期": f"{T_auto:.2f}秒",
                "自動_重心": f"{L_cm:.1f}cm",
                "自動_位置": f"{abs(x_auto*100):.0f}% (VX:{dir_auto})",
                "手動_周期": f"{T_manual:.2f}秒",
                "手動_重心": f"{L_manual_cm:.1f}cm",
                "手動_位置": f"{abs(x_manual*100):.0f}% (VX:{dir_manual})"
            })
            st.success(f"保存しました！画面下部に追加されています。")
        else:
            st.warning("店舗・筐体名を入力してください。")


# ==========================================
# 📸 スクショ用 UIセクション
# ==========================================
if len(st.session_state.saved_configs) > 0:
    st.divider()
    
    st.subheader("📸 スクショ用 攻略メモ出力")
    st.write("この下にある枠の中をスクリーンショットしてください。")

    with st.container(border=True):
        st.caption("※VXは動く方向（Velocity X）を示します。")
        
        for data in reversed(st.session_state.saved_configs):
            with st.container(border=True): 
                st.markdown(f"### 🕹️ {data['店舗_筐体名']}")
                st.markdown(f"**🔹 プレイ条件:** 落下 **{data['落下時間']}** / フック **{data['フック向き']}**")
                st.markdown(f"**🔹 パーツ寸法:** チェーン **{data['チェーン']}** / リング **{data['リング']}**")
                st.markdown(f"🔴 **自動計算:** 左右 **{data['自動_位置']}** (周期 {data['自動_周期']} / 目算重心 {data['自動_重心']})")
                st.markdown(f"🔵 **手動入力:** 左右 **{data['手動_位置']}** (周期 {data['手動_周期']} / **逆算重心 {data['手動_重心']}**)")

    st.write("") 
    
    if st.button("🗑️ 保存データをすべて消去"):
        st.session_state.saved_configs = []
        st.rerun()
