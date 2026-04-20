import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import math

# タイトルと説明
st.title("クレーンゲーム フック攻略予測")
st.write("リングを振り子と見立てて、最適な奥移動のタイミングを計算します。")

# --- 入力フォーム ---
st.sidebar.header("パラメータ入力")
L_cm = st.sidebar.number_input("支点から重心までの長さ (cm)", value=20.0, step=1.0, format="%.1f")
t_d = st.sidebar.number_input("奥移動〜落下までの時間 (秒)", value=1.0, step=0.1, format="%.2f")
hook_clock = st.sidebar.number_input("フックの向き (時計の文字盤: 1〜12)", value=3.0, step=1.0, min_value=1.0, max_value=12.0)

# --- 物理計算 ---
L_m = L_cm / 100.0  # メートルに変換
g = 9.80665         # 重力加速度 (m/s^2)

if L_m > 0:
    # 周期の計算
    T = 2 * math.pi * math.sqrt(L_m / g)
    
    # フックの向きを角度（度）に変換
    # 3時=0度(右), 12時=90度(奥), 9時=180度(左), 6時=270度(手前)
    target_deg = (3 - hook_clock) * 30
    if target_deg < 0:
        target_deg += 360
        
    # 落下時間による位相のズレ（度）
    phase_shift_deg = (t_d % T) / T * 360
    
    # ボタンを押すべきタイミングの角度（度）
    press_deg = (target_deg - phase_shift_deg) % 360
    
    # 角度からXY方向の成分（ベクトル）を計算
    press_rad = math.radians(press_deg)
    press_x = math.cos(press_rad)
    press_y = math.sin(press_rad)

    # --- 結果表示 ---
    st.subheader("計算結果")
    st.write(f"**揺れの周期 (1往復):** 約 {T:.2f} 秒")
    st.write(f"**結果:** リングが **{press_deg:.0f}度** の位置にきた瞬間にボタンを押します！")
    
    # XY方向への分解説明
    st.markdown("#### 【XY方向の分解】")
    x_dir = "右" if press_x >= 0 else "左"
    y_dir = "奥" if press_y >= 0 else "手前"
    st.write(f"リングが中心から見て **{x_dir}方向に約 {abs(press_x*100):.0f}%**、かつ **{y_dir}方向に約 {abs(press_y*100):.0f}%** 振れたタイミングがベストです。")

    # --- グラフ描画 ---
    fig, ax = plt.subplots(figsize=(6, 6))
    
    # 円（リングの軌道）
    circle = plt.Circle((0, 0), 1, color='lightgray', fill=False, linestyle='--', linewidth=2)
    ax.add_patch(circle)
    
    # 中心点と十字線
    ax.axhline(0, color='gray', linestyle=':', linewidth=1)
    ax.axvline(0, color='gray', linestyle=':', linewidth=1)
    ax.plot(0, 0, 'ko') # 中心
    
    # フックの向き（ターゲット）を青矢印で描画
    target_rad = math.radians(target_deg)
    ax.annotate('Hook Position', xy=(math.cos(target_rad)*1.1, math.sin(target_rad)*1.1), 
                xytext=(math.cos(target_rad)*1.4, math.sin(target_rad)*1.4),
                arrowprops=dict(facecolor='blue', shrink=0.05),
                fontsize=10, color='blue', ha='center', va='center')
    
    # ボタンを押すタイミングを赤矢印で描画
    ax.arrow(0, 0, press_x*0.9, press_y*0.9, head_width=0.08, head_length=0.1, fc='red', ec='red')
    ax.text(press_x*1.1, press_y*1.1, f"Push Timing!\n({press_deg:.0f} deg)", 
            color='red', ha='center', va='center', fontweight='bold')
    
    # グラフの見た目調整
    ax.set_xlim(-1.5, 1.5)
    ax.set_ylim(-1.5, 1.5)
    ax.set_aspect('equal')
    ax.set_xlabel("X (Left - Right)")
    ax.set_ylabel("Y (Front - Back)")
    ax.grid(True, linestyle=':')
    
    st.pyplot(fig)
else:
    st.error("長さは0より大きい数値を入力してください。")