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
# 計算関数（物理モデル）
# ==========================================
def get_amplitude(T, speed_level):
    """周期と速度から、実際の振幅(cm)を算出する"""
    if T <= 0:
        return 0.0
    speeds = {"大": 20.0, "中": 15.0, "小": 10.0}
    V = speeds.get(speed_level[0], 15.0)
    omega = 2 * math.pi / T
    return V / omega

def calc_physics(T, t_move, t_drop, hook_clock, speed_level):
    """
    奥移動の開始と停止に伴う加速度を考慮し、2次元(X/Y)の座標を正規化して返す。
    """
    if T <= 0:
        return 0.0, 0.0, 0.0
    
    speeds = {"大": 20.0, "中": 15.0, "小": 10.0}
    V = speeds.get(speed_level[0], 15.0)
    
    omega = 2 * math.pi / T
    A = V / omega
    
    t_total = t_move + t_drop
    
    disp_X_raw = A * math.sin(omega * t_total)
    vx_raw = V * math.cos(omega * t_total)
    
    disp_Y_raw = -2 * A * math.sin(math.pi * t_move / T) * math.cos(omega * t_total - math.pi * t_move / T)
    
    target_deg = (3 - hook_clock) * 30
    if target_deg < 0:
        target_deg += 360
    hook_rad = math.radians(target_deg)
    
    final_x = disp_X_raw * math.cos(hook_rad)
    final_y = (disp_X_raw * math.sin(hook_rad)) + disp_Y_raw
    
    norm_x = final_x / A if A != 0 else 0
    norm_y = final_y / A if A != 0 else 0
    norm_vx = vx_raw * math.cos(hook_rad)
    
    return norm_x, norm_y, norm_vx

def find_best_timings(T, t_move, hook_clock, speed_level, target=(0.0, 0.0), n=1440, top_k=3):
    """
    t_move を固定し、t_drop（待機時間）を1周期分走査して目標座標に近いタイミングを探す。
    """
    if T <= 0:
        return [], np.array([]), np.array([]), np.array([])
        
    ts = np.linspace(0, T, n, endpoint=False)
    xs = np.empty(n)
    ys = np.empty(n)
    
    for i, t in enumerate(ts):
        x, y, _ = calc_physics(T, t_move, t, hook_clock, speed_level)
        xs[i] = x
        ys[i] = y
        
    dist = np.sqrt((xs - target[0]) ** 2 + (ys - target[1]) ** 2)

    candidates = []
    for i in range(n):
        if dist[i] <= dist[i - 1] and dist[i] <= dist[(i + 1) % n]:
            candidates.append((float(ts[i]), float(dist[i]), float(xs[i]), float(ys[i])))
            
    candidates.sort(key=lambda c: c[1])
    return candidates[:top_k], ts, xs, ys

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

def format_relative_pos(x_cm, y_cm):
    """フックからの相対位置を分かりやすい日本語文字列にフォーマットする"""
    x_str = f"右に {x_cm:.1f}cm" if x_cm >= 0 else f"左に {abs(x_cm):.1f}cm"
    y_str = f"奥に {y_cm:.1f}cm" if y_cm >= 0 else f"手前に {abs(y_cm):.1f}cm"
    return f"{x_str} / {y_str}"

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
# タブ構成（順番変更）
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["⚙️ パーツ設定", "🕹️ プレイ条件", "🎯 2D解析(奥揺れ)", "📋 保存データ"])

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
    t_move = st.number_input("奥移動ボタンを押している時間 (秒)", value=1.00, step=0.1, format="%.2f")
    t_drop = st.number_input("奥移動が止まってから落下するまでの時間 (秒)", value=2.00, step=0.1, format="%.2f")
    
    st.markdown("##### アームの移動速度")
    st.caption("一般的な筐体の設定目安です")
    speed_level = st.selectbox("速度設定", [
        "大 (速い・揺れやすい: 約20cm/s)",
        "中 (標準的: 約15cm/s)",
        "小 (遅い・揺れにくい: 約10cm/s)"
    ], index=1)

    st.markdown("##### フックの向き")
    st.caption("お店の設定はほぼ 3時 か 9時 のどちらか")
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
# 自動計算ロジック
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
x_auto, y_auto, vx_auto = calc_physics(T_auto, t_move, t_drop, hook_clock, speed_level)
dir_auto = "右" if vx_auto >= 0 else "左"

x_manual, y_manual, vx_manual = calc_physics(T_manual, t_move, t_drop, hook_clock, speed_level)
dir_manual = "右" if vx_manual >= 0 else "左"

L_manual_cm = g * (T_manual / (2 * math.pi)) ** 2 * 100 if T_manual > 0 else 0

def render_badge(label, color, direction, pct, sub):
    st.markdown(f"""
    <div style="background:{color}12;border:1px solid {color}55;border-radius:14px;
                padding:16px;text-align:center;">
        <div style="font-size:13px;color:{color};font-weight:700;margin-bottom:6px;">{label}</div>
        <div style="font-size:30px;font-weight:900;color:{color};line-height:1.1;">{direction} {pct}%</div>
        <div style="font-size:12px;color:#666;margin-top:6px;">{sub}</div>
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 共通表示 (1D X軸プロット + 保存機能)
# ==========================================
st.markdown("### 📊 予測結果 (X軸)")

rcol1, rcol2 = st.columns(2)
with rcol1:
    if T_auto > 0:
        render_badge("🔴 自動計算", "#e63946", "右" if x_auto >= 0 else "左", f"{abs(x_auto*100):.0f}",
                     f"周期 約{T_auto:.2f}秒 / 重心 {L_cm:.1f}cm")
with rcol2:
    if T_manual > 0:
        render_badge("🔵 手動入力", "#457b9d", "右" if x_manual >= 0 else "左", f"{abs(x_manual*100):.0f}",
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

st.text_input("店舗・筐体名（上の選択から自動入力／手動で編集も可）", key="store_name")

if st.button("設定を保存する", use_container_width=True, type="primary"):
    if st.session_state.store_name:
        chain_mm = chain_type.split(" ")[0]
        st.session_state.saved_configs.append({
            "店舗_筐体名": st.session_state.store_name,
            "移動時間": f"奥{t_move:.1f}秒+待{t_drop:.1f}秒",
            "速度": speed_level.split(" ")[0],
            "フック向き": f"{hook_clock:.0f}時",
            "チェーン": f"{chain_mm}, 長さ{L_chain:.1f}cm",
            "リング": f"直径{D_ring:.1f}cm (太さ{d_ring_mm:.1f}mm)",
            "自動_周期": f"{T_auto:.2f}秒",
            "自動_位置": f"{abs(x_auto*100):.0f}% (VX:{dir_auto})",
            "手動_周期": f"{T_manual:.2f}秒",
            "手動_位置": f"{abs(x_manual*100):.0f}% (VX:{dir_manual})"
        })
        st.success("保存しました！「保存データ」タブに追加されています。")
    else:
        st.warning("店舗・筐体名を入力してください。")


# ------------------------------------------
# タブ3: 2D解析（軌道探索）
# ------------------------------------------
with tab3:
    st.caption("奥移動の開始と停止に伴う加速度を理論式で計算し、X/Y平面上の楕円軌道を可視化します。")

    with st.expander("🎯 目標位置を調整（通常は中央=0%のままでOK）"):
        tgcol1, tgcol2 = st.columns(2)
        target_x = tgcol1.number_input("目標X (左右, %)", value=0.0, step=5.0, format="%.0f") / 100.0
        target_y = tgcol2.number_input("目標Y (奥行き, %)", value=0.0, step=5.0, format="%.0f") / 100.0

    if T_auto <= 0 and T_manual <= 0:
        st.info("周期が計算できていません。「パーツ設定」タブを確認してください。")
    else:
        A_auto = get_amplitude(T_auto, speed_level)
        A_manual = get_amplitude(T_manual, speed_level)
        
        # --- 自動探索 ---
        best_auto, ts_a, xs_a, ys_a = find_best_timings(T_auto, t_move, hook_clock, speed_level, (target_x, target_y)) if T_auto > 0 else ([], np.array([]), np.array([]), np.array([]))
        best_manual, ts_m, xs_m, ys_m = find_best_timings(T_manual, t_move, hook_clock, speed_level, (target_x, target_y)) if T_manual > 0 else ([], np.array([]), np.array([]), np.array([]))

        # --- 楕円軌道の可視化 (cm単位) ---
        fig2, ax2 = plt.subplots(figsize=(6, 6))
        all_vals_cm = [5.0] 
        
        if len(xs_a) > 0:
            xs_a_cm, ys_a_cm = xs_a * A_auto, ys_a * A_auto
            ax2.plot(xs_a_cm, ys_a_cm, color='#e63946', alpha=0.5, linewidth=1.5, label="🔴 自動計算の軌道")
            ax2.plot(x_auto * A_auto, y_auto * A_auto, 'o', color='#e63946', markersize=12)
            if best_auto:
                bx_cm, by_cm = best_auto[0][2] * A_auto, best_auto[0][3] * A_auto
                ax2.plot(bx_cm, by_cm, '*', color='#e63946', markersize=20, markeredgecolor='black', markeredgewidth=0.6)
            all_vals_cm.extend(xs_a_cm.tolist())
            all_vals_cm.extend(ys_a_cm.tolist())
                
        if len(xs_m) > 0:
            xs_m_cm, ys_m_cm = xs_m * A_manual, ys_m * A_manual
            ax2.plot(xs_m_cm, ys_m_cm, color='#457b9d', alpha=0.5, linewidth=1.5, label="🔵 手動入力の軌道")
            ax2.plot(x_manual * A_manual, y_manual * A_manual, 'o', color='#457b9d', markersize=12)
            if best_manual:
                bx_cm, by_cm = best_manual[0][2] * A_manual, best_manual[0][3] * A_manual
                ax2.plot(bx_cm, by_cm, '*', color='#457b9d', markersize=20, markeredgecolor='black', markeredgewidth=0.6)
            all_vals_cm.extend(xs_m_cm.tolist())
            all_vals_cm.extend(ys_m_cm.tolist())

        ref_A = A_auto if T_auto > 0 else A_manual
        tx_cm, ty_cm = target_x * ref_A, target_y * ref_A
        ax2.plot(tx_cm, ty_cm, 'g+', markersize=16, markeredgewidth=3, label="🎯 目標位置")
        all_vals_cm.extend([tx_cm, ty_cm])

        ax2.axhline(0, color='gray', linestyle=':', linewidth=0.8)
        ax2.axvline(0, color='gray', linestyle=':', linewidth=0.8)
        ax2.set_xlabel("← 左  X(左右) [cm]  右 →")
        ax2.set_ylabel("← 手前  Y(奥行き) [cm]  奥 →")
        ax2.set_aspect('equal', adjustable='box')

        lim = np.nanmax(np.abs(all_vals_cm)) * 1.15
        ax2.set_xlim(-lim, lim)
        ax2.set_ylim(-lim, lim)
        ax2.legend(loc='upper right', fontsize=8)
        st.pyplot(fig2)
        st.caption("● = 現在の待ち時間での位置 ★ = 最適なタイミングでの位置")

        st.divider()

        # --- 現在地と推奨タイミング (相対座標での表示) ---
        rcol_a, rcol_b = st.columns(2)
        with rcol_a:
            st.markdown("**🔴 自動計算**")
            if T_auto > 0:
                st.write(f"現在位置 (待機 {t_drop:.2f}秒):")
                st.write(f"👉 フックから **{format_relative_pos(x_auto * A_auto, y_auto * A_auto)}**")
                
                if best_auto:
                    st.success("おすすめの待ち時間と停止位置")
                    for bt, bd, bx, by in best_auto:
                        bx_cm = bx * A_auto
                        by_cm = by * A_auto
                        st.markdown(f"- 待機 **{bt:.2f}秒** ･･･ フックから **{format_relative_pos(bx_cm, by_cm)}** (誤差 {bd * A_auto:.1f}cm)")
            else:
                st.caption("周期未計算")

        with rcol_b:
            st.markdown("**🔵 手動入力**")
            if T_manual > 0:
                st.write(f"現在位置 (待機 {t_drop:.2f}秒):")
                st.write(f"👉 フックから **{format_relative_pos(x_manual * A_manual, y_manual * A_manual)}**")
                
                if best_manual:
                    st.success("おすすめの待ち時間と停止位置")
                    for bt, bd, bx, by in best_manual:
                        bx_cm = bx * A_manual
                        by_cm = by * A_manual
                        st.markdown(f"- 待機 **{bt:.2f}秒** ･･･ フックから **{format_relative_pos(bx_cm, by_cm)}** (誤差 {bd * A_manual:.1f}cm)")
            else:
                st.caption("周期未計算")

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
                st.markdown(f"**🔹 操作:** {data['移動時間']} / 速度:{data['速度']} / フック:{data['フック向き']}")
                st.markdown(f"🔴 **自動:** 左右 **{data['自動_位置']}** (周期 {data['自動_周期']})")
                st.markdown(f"🔵 **手動:** 左右 **{data['手動_位置']}** (周期 {data['手動_周期']})")
        
        st.write("")
        if st.button("🗑️ 保存データをすべて消去", use_container_width=True):
            st.session_state.saved_configs = []
            st.rerun()
