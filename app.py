import streamlit as st
import numpy as np
import matplotlib.pyplot as plt
import japanize_matplotlib
import math
import json
import io
import csv
from datetime import datetime

# ==========================================
# ページ設定とCSS
# ==========================================
st.set_page_config(page_title="フック攻略予測", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
html, body, [class*="css"]  { font-family: 'Noto Sans JP', sans-serif; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] {
    height: 48px; border-radius: 10px 10px 0 0; padding: 0 18px;
    font-weight: 700; font-size: 15px;
}
.stTabs [aria-selected="true"] { background-color: #F0EEFE; }
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
.stButton > button { border-radius: 10px; font-weight: 700; padding: 10px 0; }
div[data-testid="stNumberInput"] input, div[data-baseweb="select"] { border-radius: 10px; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div style="background:linear-gradient(135deg,#6C5CE7,#00B4D8);
            padding:22px 24px;border-radius:16px;margin-bottom:18px;">
  <div style="color:white;font-size:26px;font-weight:900;">🪝 フック攻略予測</div>
  <div style="color:#EFEDFE;font-size:13px;margin-top:4px;">
    自動計算(赤) × 実測周期(青) でベストタイミングを算出・保存
  </div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# セッションステート初期化
# ==========================================
if "saved_configs" not in st.session_state:
    st.session_state.saved_configs = []
if "store_name" not in st.session_state:
    st.session_state.store_name = f"{datetime.now().strftime('%m/%d')} 〇〇店 UFO9 1番台 右側"
if "side" not in st.session_state:
    st.session_state.side = "右側"
if "hook_clock" not in st.session_state:
    st.session_state.hook_clock = 3

STORE_OPTIONS = ["トレジャーランド", "もってきーな茂原", "もってきーな椎名崎", "レジャーランド"]
MACHINE_OPTIONS = ["UFO10", "UFO9", "BLAST D", "UFO8", "UFO7", "クレナ2", "クレフレ"]

# ==========================================
# 計算関数（分離型物理モデル + フック向き反映）
# ==========================================
def get_amplitude(T, speed_level):
    if T <= 0:
        return 0.0
    speeds = {"大": 20.0, "中": 15.0, "小": 10.0}
    V = speeds.get(speed_level[0], 15.0)
    omega = 2 * math.pi / T
    return V / omega

def calc_decoupled_pos(T, t_d, t_move, hook_clock, speed_level):
    """
    横移動(X)と奥移動(Y)を計算し、フックの向き（3時/9時など）による影響を反映する。
    """
    if T <= 0:
        return 0.0, 0.0, 0.0
    
    A = get_amplitude(T, speed_level)
    omega = 2 * math.pi / T
    
    # 3時 -> cos(0) = 1, 9時 -> cos(180°) = -1
    target_deg = (3 - hook_clock) * 30
    if target_deg < 0:
        target_deg += 360
    hook_factor = math.cos(math.radians(target_deg))
    
    # 横移動停止からt_d経過後のX位置（フック向きを反映）
    x_cm = A * math.sin(omega * t_d) * hook_factor
    
    # 奥移動開始からt_move経過後のY位置
    y_cm = -A * math.sin(omega * t_move)
    
    return x_cm, y_cm, A

def get_vx_sign(T, t_d, hook_clock):
    if T <= 0: return 1
    omega = 2 * math.pi / T
    target_deg = (3 - hook_clock) * 30
    if target_deg < 0: target_deg += 360
    hook_factor = math.cos(math.radians(target_deg))
    val = math.cos(omega * t_d) * hook_factor
    return 1 if val >= 0 else -1

# --- UI用ヘルパー ---
def set_hook(n):
    st.session_state.hook_clock = n

def set_hook_other():
    st.session_state.hook_clock = int(st.session_state.hook_other_input)

def set_side(s):
    st.session_state.side = s
    compose_store_name()

def compose_store_name():
    stall = st.session_state.get("stall_no", 0)
    stall_part = f"{int(stall)}番台" if stall and stall > 0 else ""
    parts = [
        datetime.now().strftime("%m/%d"),
        st.session_state.get("store_sel", ""),
        st.session_state.get("machine_sel", ""),
        stall_part,
        st.session_state.side,
    ]
    st.session_state.store_name = " ".join(p for p in parts if p)

def format_aim_pos(hx, hy):
    x_str = f"右に {abs(hx):.1f} cm" if hx >= 0 else f"左に {abs(hx):.1f} cm"
    y_str = f"奥に {abs(hy):.1f} cm" if hy >= 0 else f"手前に {abs(hy):.1f} cm"
    return f"{x_str} ／ {y_str}"

def format_x_status(x_norm, v_sign):
    """例: '左側 62% (→右方向)' のように、位置(%)と進行方向をまとめる。"""
    side = "右側" if x_norm >= 0 else "左側"
    arrow = "→右方向" if v_sign >= 0 else "←左方向"
    return f"{side} {abs(x_norm) * 100:.0f}% ({arrow})"

# ==========================================
# データ読み込み(JSON)
# ==========================================
with st.expander("📂 保存データを読み込む（前回のJSONファイル）", expanded=False):
    uploaded = st.file_uploader("JSONファイルを選択", type=["json"], label_visibility="collapsed")
    if uploaded is not None:
        try:
            loaded = json.load(uploaded)
            if isinstance(loaded, list):
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

# ==========================================
# タブ構成
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["⚙️ パーツ設定", "🕹️ プレイ条件", "🎯 2D解析(停止位置)", "📋 保存データ"])

# ------------------------------------------
# タブ1: パーツ設定
# ------------------------------------------
with tab1:
    st.markdown("##### 🔴 自動計算（チェーン＋リング）")
    st.caption("モノタロウ規格（鉄マンテルチェーン）の実測値準拠")

    chain_type = st.selectbox("チェーンの線径 (規格質量)", [
        "1.6mm (0.58 g/cm)",
        "2.0mm (0.88 g/cm)",
        "2.6mm (1.48 g/cm)",
        "3.2mm (2.26 g/cm)"
    ])
    L_chain = st.number_input("チェーンの長さ (cm)", value=15.0, step=1.0, format="%.1f")

    st.markdown("##### ⭕ リング")
    D_ring = st.number_input("リングの直径 (cm)", value=10.0, step=0.1, format="%.1f")
    ring_type = st.selectbox("リングの線の太さ", [
        "8.0mm (極太)",
        "7.0mm (太め)",
        "6.0mm (標準・カインズ基準)",
        "5.0mm (やや細め)",
        "4.0mm (細め)"
    ], index=2)
    d_ring_mm = float(ring_type.split("mm")[0])

    st.divider()
    st.markdown("##### 🔵 手動入力（実測の周期）")
    T_manual = st.number_input("1往復の秒数", value=0.85, step=0.01, format="%.2f")

# ------------------------------------------
# タブ2: プレイ条件
# ------------------------------------------
with tab2:
    st.markdown("##### アームの操作時間")
    t_d = st.number_input("横移動が止まってから、落下するまでの合計時間 (秒)", value=3.00, step=0.1, format="%.2f")
    t_move = st.number_input("そのうち、奥移動ボタンを押している時間 (秒)", value=1.00, step=0.1, format="%.2f")
    
    st.markdown("##### アームの移動速度")
    speed_level = st.selectbox("速度設定", [
        "大 (速い・揺れやすい: 約20cm/s)",
        "中 (標準的: 約15cm/s)",
        "小 (遅い・揺れにくい: 約10cm/s)"
    ], index=1)

    st.markdown("##### フックの向き")
    hcol1, hcol2 = st.columns(2)
    with hcol1:
        st.button(
            "🕒 3時", use_container_width=True,
            type="primary" if st.session_state.hook_clock == 3 else "secondary",
            on_click=set_hook, args=(3,),
        )
    with hcol2:
        st.button(
            "🕘 9時", use_container_width=True,
            type="primary" if st.session_state.hook_clock == 9 else "secondary",
            on_click=set_hook, args=(9,),
        )

    with st.expander(f"その他の時刻を指定（現在: {st.session_state.hook_clock}時）"):
        st.number_input(
            "時計の文字盤 (1〜12)",
            value=float(st.session_state.hook_clock),
            min_value=1.0, max_value=12.0, step=1.0,
            key="hook_other_input", on_change=set_hook_other,
        )
    hook_clock = float(st.session_state.hook_clock)

# ==========================================
# 物理計算処理
# ==========================================
if "1.6mm" in chain_type: chain_density = 0.58
elif "2.0mm" in chain_type: chain_density = 0.88
elif "2.6mm" in chain_type: chain_density = 1.48
elif "3.2mm" in chain_type: chain_density = 2.26
else: chain_density = 0.58

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
L_manual_cm = g * (T_manual / (2 * math.pi)) ** 2 * 100 if T_manual > 0 else 0

x_cm_auto, y_cm_auto, A_auto = calc_decoupled_pos(T_auto, t_d, t_move, hook_clock, speed_level)
# 修正箇所: hook_clock を渡すように修正
x_cm_manual, y_cm_manual, A_manual = calc_decoupled_pos(T_manual, t_d, t_move, hook_clock, speed_level)

x_norm_auto = x_cm_auto / A_auto if A_auto > 0 else 0
x_norm_manual = x_cm_manual / A_manual if A_manual > 0 else 0

v_sign_auto = get_vx_sign(T_auto, t_d, hook_clock)
v_sign_manual = get_vx_sign(T_manual, t_d, hook_clock)

def render_badge(label, color, direction, pct, sub):
    st.markdown(f"""
    <div style="background:{color}12;border:1px solid {color}55;border-radius:14px;
                padding:16px;text-align:center;">
        <div style="font-size:13px;color:{color};font-weight:700;margin-bottom:6px;">{label}</div>
        <div style="font-size:30px;font-weight:900;color:{color};line-height:1.1;">{direction} {pct}%</div>
        <div style="font-size:12px;color:#666;margin-top:6px;">{sub}</div>
    </div>
    """, unsafe_allow_html=True)

# ------------------------------------------
# タブ3: 2D解析（最適な停止位置 + 回転方向の矢印）
# ------------------------------------------
with tab3:
    st.caption("横移動と奥移動の揺れを独立して計算し、目標地点に落下させるための「フックの最適な停止位置」と、リングの回転方向（軌道の向き）を可視化します。")

    if T_auto <= 0 and T_manual <= 0:
        st.info("周期が計算できていません。「パーツ設定」タブを確認してください。")
    else:
        hx_auto, hy_auto = -x_cm_auto, -y_cm_auto
        hx_manual, hy_manual = -x_cm_manual, -y_cm_manual

        rcol_a, rcol_b = st.columns(2)
        with rcol_a:
            st.markdown("**🔴 自動計算での狙い目**")
            if T_auto > 0:
                st.success(format_aim_pos(hx_auto, hy_auto))
            else:
                st.caption("未計算")

        with rcol_b:
            st.markdown("**🔵 手動入力での狙い目**")
            if T_manual > 0:
                st.success(format_aim_pos(hx_manual, hy_manual))
            else:
                st.caption("未計算")

        st.divider()

        # 軌道の可視化
        fig2, ax2 = plt.subplots(figsize=(6, 6))
        
        ax2.plot(0, 0, 'g+', markersize=20, markeredgewidth=3, label="🎯 狙いたい目標")
        all_vals = [0.0]

        def plot_trajectory_with_arrow(T, t_d, t_move, hook_clock, A, H_x, H_y, color, label):
            if T <= 0: return
            omega = 2 * math.pi / T
            target_deg = (3 - hook_clock) * 30
            if target_deg < 0: target_deg += 360
            hook_factor = math.cos(math.radians(target_deg))

            t_max = max(t_d, t_move)
            ts = np.linspace(-t_max, 0, 300)
            Rx, Ry = np.zeros_like(ts), np.zeros_like(ts)
            
            for i, t in enumerate(ts):
                x_rel = A * math.sin(omega * (t + t_d)) * hook_factor if t >= -t_d else 0
                y_rel = -A * math.sin(omega * (t + t_move)) if t >= -t_move else 0
                Rx[i] = H_x + x_rel
                Ry[i] = H_y + y_rel
                
            ax2.plot(Rx, Ry, color=color, alpha=0.6, linewidth=2, label=f"{label} 軌道")
            ax2.plot(H_x, H_y, 's', color=color, markersize=10, label=f"{label} フック停止位置")
            
            for idx in [int(len(ts) * 0.35), int(len(ts) * 0.75)]:
                p1_x, p1_y = Rx[idx], Ry[idx]
                p2_x, p2_y = Rx[idx+2], Ry[idx+2]
                dx, dy = p2_x - p1_x, p2_y - p1_y
                if math.hypot(dx, dy) > 0:
                    ax2.annotate('', xy=(p1_x + dx*2, p1_y + dy*2), xytext=(p1_x, p1_y),
                                 arrowprops=dict(arrowstyle="->", color=color, lw=2, shrinkA=0, shrinkB=0))

            all_vals.extend(Rx.tolist() + Ry.tolist())

        plot_trajectory_with_arrow(T_auto, t_d, t_move, hook_clock, A_auto, hx_auto, hy_auto, '#e63946', "🔴自動")
        plot_trajectory_with_arrow(T_manual, t_d, t_move, hook_clock, A_manual, hx_manual, hy_manual, '#457b9d', "🔵手動")

        ax2.axhline(0, color='gray', linestyle=':', linewidth=0.8)
        ax2.axvline(0, color='gray', linestyle=':', linewidth=0.8)
        ax2.set_xlabel("← 左  X(左右) [cm]  右 →")
        ax2.set_ylabel("← 手前  Y(奥行き) [cm]  奥 →")
        ax2.set_aspect('equal', adjustable='box')
        
        lim = max(5.0, np.nanmax(np.abs(all_vals)) * 1.2)
        ax2.set_xlim(-lim, lim)
        ax2.set_ylim(-lim, lim)
        ax2.legend(loc='upper right', fontsize=8)
        st.pyplot(fig2)
        st.caption("軌道上の矢印（➔）により、フック停止後にリングがどちらの回転方向へスイングするか一目でわかります。")

# ==========================================
# 共通表示 (1D X軸プロット + 保存機能)
# ==========================================
st.divider()
st.markdown("### 📊 横揺れの位相 (参考)")
st.caption("操作時間によって生じるX軸方向の揺れ幅を％で表したものです。")

rcol1, rcol2 = st.columns(2)
with rcol1:
    if T_auto > 0:
        render_badge("🔴 自動計算", "#e63946", "右" if x_norm_auto >= 0 else "左", f"{abs(x_norm_auto*100):.0f}",
                     f"周期 約{T_auto:.2f}秒 / 重心 {L_cm:.1f}cm")
with rcol2:
    if T_manual > 0:
        render_badge("🔵 手動入力", "#457b9d", "右" if x_norm_manual >= 0 else "左", f"{abs(x_norm_manual*100):.0f}",
                     f"周期 {T_manual:.2f}秒 / 逆算重心 {L_manual_cm:.1f}cm")

fig, ax = plt.subplots(figsize=(8, 3))
ax.plot([-1.2, 1.2], [0, 0], color='black', linewidth=1.5)
ax.plot([-1, 1], [0, 0], '|', color='gray', markersize=20)
ax.axvline(0, color='gray', linestyle=':', linewidth=1)
ax.text(-1, 0.1, "左端", ha='center', fontsize=12)
ax.text(1, 0.1, "右端", ha='center', fontsize=12)
ax.text(0, -0.4, "中心\n(落下目標)", ha='center', fontsize=12, color='green')
ax.plot(0, 0, 'go', markersize=6)

if T_auto > 0:
    ax.plot(x_norm_auto, 0, 'ro', markersize=14, alpha=0.7)
    if abs(x_norm_auto) < 0.99:
        ax.arrow(x_norm_auto, 0, v_sign_auto * 0.15, 0, head_width=0.08, head_length=0.06, fc='red', ec='red', linewidth=2)
    ax.text(x_norm_auto, 0.25, f"自動(赤)\n{abs(x_norm_auto*100):.0f}%", color='red', ha='center', va='bottom', fontweight='bold', fontsize=10)

if T_manual > 0:
    ax.plot(x_norm_manual, 0, 'bo', markersize=14, alpha=0.7)
    if abs(x_norm_manual) < 0.99:
        ax.arrow(x_norm_manual, 0, v_sign_manual * 0.15, 0, head_width=0.08, head_length=0.06, fc='blue', ec='blue', linewidth=2)
    ax.text(x_norm_manual, -0.15, f"手動(青)\n{abs(x_norm_manual*100):.0f}%", color='blue', ha='center', va='top', fontweight='bold', fontsize=10)

ax.set_xlim(-1.5, 1.5)
ax.set_ylim(-0.7, 0.7)
ax.axis('off')
st.pyplot(fig)

# ==========================================
# データの保存機能
# ==========================================
st.divider()
st.markdown("### 💾 現在のパラメータを保存")

qs_col1, qs_col2 = st.columns(2)
with qs_col1:
    st.selectbox("店舗", STORE_OPTIONS, key="store_sel", on_change=compose_store_name)
with qs_col2:
    st.selectbox("機種", MACHINE_OPTIONS, key="machine_sel", on_change=compose_store_name)

sd_col1, sd_col2, sd_col3 = st.columns([1, 1, 1])
with sd_col1:
    st.button("⬅️ 左側", use_container_width=True, type="primary" if st.session_state.side == "左側" else "secondary", on_click=set_side, args=("左側",))
with sd_col2:
    st.button("➡️ 右側", use_container_width=True, type="primary" if st.session_state.side == "右側" else "secondary", on_click=set_side, args=("右側",))
with sd_col3:
    st.number_input("台番号(任意)", min_value=0, value=0, step=1, key="stall_no", on_change=compose_store_name)

st.text_input("店舗・筐体名", key="store_name")

if st.button("設定を保存する", use_container_width=True, type="primary"):
    if st.session_state.store_name:
        chain_mm = chain_type.split(" ")[0]
        st.session_state.saved_configs.append({
            "店舗_筐体名": st.session_state.store_name,
            "操作時間": f"全体{t_d:.1f}s (奥{t_move:.1f}s)",
            "速度": speed_level.split(" ")[0],
            "フック向き": f"{hook_clock:.0f}時",
            "チェーン": f"{chain_mm}, 長さ{L_chain:.1f}cm",
            "リング": f"直径{D_ring:.1f}cm (太さ{d_ring_mm:.1f}mm)",
            "自動_周期": f"{T_auto:.2f}秒",
            "自動_X位置": format_x_status(x_norm_auto, v_sign_auto),
            "自動_停止位置": format_aim_pos(-x_cm_auto, -y_cm_auto),
            "手動_周期": f"{T_manual:.2f}秒",
            "手動_X位置": format_x_status(x_norm_manual, v_sign_manual),
            "手動_停止位置": format_aim_pos(-x_cm_manual, -y_cm_manual)
        })
        st.success("保存しました！「保存データ」タブに追加されています。")
    else:
        st.warning("店舗・筐体名を入力してください。")

# ------------------------------------------
# タブ4: 保存データ一覧
# ------------------------------------------
with tab4:
    if len(st.session_state.saved_configs) == 0:
        st.info("まだ保存されたデータがありません。")
    else:
        dcol1, dcol2 = st.columns(2)
        json_bytes = json.dumps(st.session_state.saved_configs, ensure_ascii=False, indent=2).encode("utf-8")
        with dcol1:
            st.download_button("📥 JSONで保存", data=json_bytes, file_name=f"crane_data_{datetime.now().strftime('%Y%m%d_%H%M')}.json", mime="application/json", use_container_width=True)

        csv_buf = io.StringIO()
        if st.session_state.saved_configs:
            writer = csv.DictWriter(csv_buf, fieldnames=list(st.session_state.saved_configs[0].keys()))
            writer.writeheader()
            writer.writerows(st.session_state.saved_configs)
        with dcol2:
            st.download_button("📊 CSVで保存", data=csv_buf.getvalue().encode("utf-8-sig"), file_name=f"crane_data_{datetime.now().strftime('%Y%m%d_%H%M')}.csv", mime="text/csv", use_container_width=True)

        st.divider()
        for idx, data in enumerate(reversed(st.session_state.saved_configs)):
            with st.container(border=True):
                st.markdown(f"### 🕹️ {data['店舗_筐体名']}")
                st.markdown(f"**🔹 操作:** {data['操作時間']} / 速度:{data['速度']} / フック:{data['フック向き']}")
                st.markdown(f"🔴 **自動:** 周期 {data['自動_周期']} / X位置 {data['自動_X位置']} / 停止位置 {data['自動_停止位置']}")
                st.markdown(f"🔵 **手動:** 周期 {data['手動_周期']} / X位置 {data['手動_X位置']} / 停止位置 {data['手動_停止位置']}")
        
        st.write("")
        if st.button("🗑️ 保存データをすべて消去", use_container_width=True):
            st.session_state.saved_configs = []
            st.rerun()
