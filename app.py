import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
import math
from datetime import datetime

# ページ設定（スマホでも見やすいように画面幅を広く使う）
st.set_page_config(page_title="クレーンゲーム攻略予測", layout="wide")

st.title("クレーンゲーム 横揺れ(X軸)攻略予測")
st.write("自動計算（赤）と手動の周期（青）を同時に比較し、ベストなタイミングを算出・保存します。")

# --- 保存データの初期化 (セッションステート) ---
if "saved_configs" not in st.session_state:
    st.session_state.saved_configs = []

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
chain_type = st.sidebar.selectbox("チェーンの線径", ["1.6mm (0.58g/cm)", "2.0mm (0.82g/cm)"])
L_chain = st.sidebar.number_input("チェーンの長さ (cm)", value=15.0, step=1.0, format="%.1f")
D_ring = st.sidebar.number_input("リングの直径 (cm)", value=5.0, step=0.1, format="%.1f")

# 自動計算の物理ロジック
chain_density = 0.58 if "1.6mm" in chain_type else 0.82
m_chain = chain_density * L_chain
y_chain = L_chain / 2.0
density_steel = 7.8
d_ring_fixed = 4.0 / 10.0 
r_ring_cm = d_ring_fixed / 2.0
R_center_cm = (D_ring / 2.0) - r_ring_cm
m_ring = (math.pi * r_ring_cm**2) * (2 * math.pi * R_center_cm) * density_steel
y_ring = L_chain + (D_ring / 2.0)
L_cm = (m_chain * y_chain + m_ring * y_ring) / (m_chain + m_ring) if (m_chain + m_ring) > 0 else 0
g = 9.80665

T_auto = 2 * math.pi * math.sqrt((L_cm / 100.0) / g) if L_cm > 0 else 0
x_auto, y_auto, vx_auto = calc_timing(T_auto, t_d, hook_clock)

st.sidebar.divider()

st.sidebar.header("3. 🔵手動入力 (周期指定)")
st.sidebar.caption("ストップウォッチ等で測った1往復の秒数")
T_manual = st.sidebar.number_input("手動の周期 (秒)", value=0.00, step=0.01, format="%.2f")
x_manual, y_manual, vx_manual = calc_timing(T_manual, t_d, hook_clock)

# ==========================================
# メイン画面 (結果とグラフ)
# ==========================================
col1, col2 = st.columns(2)

with col1:
    st.subheader("🔴 自動計算の結果")
    st.write(f"**推定周期:** 約 {T_auto:.2f} 秒 (重心: {L_cm:.1f}cm)")
    if T_auto > 0:
        dir_auto = "右" if vx_auto >= 0 else "左"
        st.markdown(f"**X軸タイミング:** 【**{'右' if x_auto >= 0 else '左'}側に約 {abs(x_auto*100):.0f}%**】で【**{dir_auto}方向**】に動く瞬間")

with col2:
    st.subheader("🔵 手動入力の結果")
    st.write(f"**設定周期:** {T_manual:.2f} 秒")
    if T_manual > 0:
        dir_manual = "右" if vx_manual >= 0 else "左"
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
    save_name = st.text_input("この設定の名前 (例: 設定A, 初期位置 など)")
with save_col2:
    st.write("") # ボタンの位置合わせ用
    if st.button("設定を保存する"):
        if save_name:
            st.session_state.saved_configs.append({
                "設定名": save_name,
                "落下時間": f"{t_d:.2f}秒",
                "フック向き": f"{hook_clock}時",
                "自動_周期": f"{T_auto:.2f}秒",
                "自動_位置": f"{abs(x_auto*100):.0f}% (VX:{dir_auto})",
                "手動_周期": f"{T_manual:.2f}秒",
                "手動_位置": f"{abs(x_manual*100):.0f}% (VX:{dir_manual})"
            })
            st.success(f"「{save_name}」を保存しました！画面下部に追加されています。")
        else:
            st.warning("設定名を入力してください。")


# ==========================================
# 📸 スクショ用 UIセクション
# ==========================================
if len(st.session_state.saved_configs) > 0:
    st.divider()
    
    # 今日の日付を初期値に設定
    today_str = datetime.now().strftime("%m/%d")
    
    st.subheader("📸 スクショ用 攻略メモ出力")
    st.write("店舗名や筐体名を入力し、この下にある枠の中をスクリーンショットしてください。")
    
    # タイトルの入力欄
    memo_title = st.text_input("📝 メモのタイトルを変更", value=f"{today_str} 〇〇店 UFO9 1番台 右側")

    # --- ここから下がスクショに最適なエリア ---
    with st.container(border=True):
        st.markdown(f"## {memo_title}")
        st.caption("※VXは動く方向（Velocity X）を示します。")
        
        # 1件ずつカード状に表示
        for data in st.session_state.saved_configs:
            with st.container(border=True): 
                st.markdown(f"#### 🕹️ {data['設定名']}")
                st.markdown(f"**落下時間:** {data['落下時間']} / **フック:** {data['フック向き']}")
                st.markdown(f"🔴 **自動計算:** 左右 **{data['自動_位置']}** (周期 {data['自動_周期']})")
                st.markdown(f"🔵 **手動入力:** 左右 **{data['手動_位置']}** (周期 {data['手動_周期']})")

    st.write("") # スペース空け
    
    # リセットボタン
    if st.button("🗑️ 保存データをすべて消去"):
        st.session_state.saved_configs = []
        st.rerun()
