import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
import math

st.title("クレーンゲーム フック攻略予測")
st.write("設定に合わせて重心の計算方法を選び、ベストな奥移動のタイミングを算出します。")

# --- 入力フォーム ---
st.sidebar.header("1. 重心の設定")

# モード切替
mode = st.sidebar.radio("計算モード", ["自動計算 (チェーン＋リング)", "手動入力 (重心距離を直接指定)"])

if mode == "自動計算 (チェーン＋リング)":
    st.sidebar.caption("※チェーン5mm/リング4mmの鉄製として計算")
    L_chain = st.sidebar.number_input("チェーンの長さ (cm)", value=15.0, step=1.0, format="%.1f")
    D_ring = st.sidebar.number_input("リングの外径 (cm)", value=5.0, step=0.1, format="%.1f")
    
    # 内部計算
    density = 7.8 
    d_chain = 5.0 
    d_ring = 4.0  
    r_chain_cm = (d_chain / 10.0) / 2.0
    m_chain = 2 * (math.pi * r_chain_cm**2) * L_chain * density
    y_chain = L_chain / 2.0
    r_ring_cm = (d_ring / 10.0) / 2.0
    R_center_cm = (D_ring / 2.0) - r_ring_cm
    m_ring = (math.pi * r_ring_cm**2) * (2 * math.pi * R_center_cm) * density
    y_ring = L_chain + (D_ring / 2.0)
    
    L_cm = (m_chain * y_chain + m_ring * y_ring) / (m_chain + m_ring) if (m_chain + m_ring) > 0 else 0
    calc_info = f"推定質量: チェーン約 {m_chain:.0f}g / リング約 {m_ring:.0f}g"

else:
    L_cm = st.sidebar.number_input("支点から重心までの距離 (cm)", value=17.5, step=0.5, format="%.1f")
    calc_info = "手動設定による計算"

st.sidebar.divider()

st.sidebar.header("2. プレイ条件")
t_d = st.sidebar.number_input("奥移動〜落下までの時間 (秒)", value=1.00, step=0.1, format="%.2f")
hook_clock = st.sidebar.number_input("フックの向き (時計の文字盤: 1〜12)", value=3.0, step=1.0, min_value=1.0, max_value=12.0)

# --- 物理計算 ---
L_m = L_cm / 100.0  
g = 9.80665

if L_m > 0:
    T = 2 * math.pi * math.sqrt(L_m / g)
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

    # --- 結果表示 ---
    st.subheader("計算結果")
    
    st.markdown(f"""
    **【適用パラメータ】**
    * 使用する重心距離: **支点から {L_cm:.1f} cm** ({calc_info})
    * 揺れの周期 (1往復): 約 {T:.2f} 秒
    """)
    
    x_pos_text = "右" if x_pos >= 0 else "左"
    x_dir_text = "右" if v_x >= 0 else "左"
    
    if abs(y_pos) < 0.01:
        y_pos_text = "中心付近（前後の振れなし）"
    else:
        y_pos_text = "奥" if y_pos > 0 else "手前"

    st.markdown(f"""
    ### 💡 アームを動かすタイミング：
    * **前後（Y軸）:** リングが **【{y_pos_text}】** に振れたタイミング！
    * **左右（X軸）:** リングが **【{x_pos_text}側に約 {abs(x_pos*100):.0f}%】** 振れ、**【{x_dir_text}方向】** に動いている瞬間！
    """)

    # --- 1次元グラフ描画 ---
    fig, ax = plt.subplots(figsize=(8, 3)) 
    ax.plot([-1.2, 1.2], [0, 0], color='black', linewidth=1.5)
    ax.plot([-1, 1], [0, 0], '|', color='gray', markersize=20)
    ax.axvline(0, color='gray', linestyle=':', linewidth=1)
    ax.text(-1, 0.1, "左端", ha='center', fontsize=12)
    ax.text(1, 0.1, "右端", ha='center', fontsize=12)
    ax.text(0, -0.25, "中心\n(落下目標)", ha='center', fontsize=12, color='blue')
    ax.plot(0, 0, 'ko', markersize=6) 
    ax.plot(x_pos, 0, 'ro', markersize=15)
    
    if abs(v_x) > 0.01:
        v_sign = 1 if v_x > 0 else -1
        ax.arrow(x_pos, 0, v_sign * 0.2, 0, head_width=0.1, head_length=0.08, fc='red', ec='red', linewidth=2)
    
    ax.text(x_pos, 0.25, "Push Timing!", color='red', ha='center', va='bottom', fontweight='bold', fontsize=12)
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-0.6, 0.6)
    ax.axis('off') 
    st.pyplot(fig)
else:
    st.error("有効な値を入力してください。")
