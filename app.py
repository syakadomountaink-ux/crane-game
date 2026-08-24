
Crane game app · PY
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
st.set_page_config(page_title="フック攻略予測", layout="centered")
 
# ==========================================
# デザイン(CSS)
# ==========================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap');
 
html, body, [class*="css"]  { font-family: 'Noto Sans JP', sans-serif; }
 
/* タブ */
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] {
    height: 48px; border-radius: 10px 10px 0 0; padding: 0 18px;
    font-weight: 700; font-size: 15px;
}
.stTabs [aria-selected="true"] { background-color: #F0EEFE; }
 
/* カード風コンテナ */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border-radius: 16px !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}
 
/* ボタン */
.stButton > button {
    border-radius: 10px; font-weight: 700; padding: 10px 0;
}
 
/* number/select input */
div[data-testid="stNumberInput"] input, div[data-baseweb="select"] {
    border-radius: 10px;
}
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
 
# --- 保存データと入力欄の初期化 (セッションステート) ---
if "saved_configs" not in st.session_state:
    st.session_state.saved_configs = []
 
if "store_name" not in st.session_state:
    st.session_state.store_name = f"{datetime.now().strftime('%m/%d')} 〇〇店 UFO9 1番台 右側"
 
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
 
 
def set_hook(n):
    st.session_state.hook_clock = n
 
 
def set_hook_other():
    st.session_state.hook_clock = int(st.session_state.hook_other_input)
 
 
# --- 2D(X+Y)拡張: 奥行き方向の揺れを含めた計算 ---
def calc_xy(T, t_d, hook_clock, y_kick_ratio):
    """
    X軸: 従来モデル(フックの向きで決まる揺れの平面)をそのまま使用。
    Y軸: 奥移動が止まる瞬間(t=0基準、位相0・速度あり)から励起される
         独立した前後方向の振動を新たに加算する。
    同じ振り子(同じ周期T)から生じる2つの成分の合成として、
    軌道は基本的に楕円(位相差があるリサージュ図形)になる。
    """
    if T <= 0:
        return 0.0, 0.0
    phase_advance_deg = (t_d % T) / T * 360
 
    target_deg = (3 - hook_clock) * 30
    if target_deg < 0:
        target_deg += 360
    hook_rad = math.radians(target_deg)
 
    press_phase_rad = math.radians((180 - phase_advance_deg) % 360)
    disp = math.sin(press_phase_rad)
 
    x = disp * math.cos(hook_rad)
    y_plane = disp * math.sin(hook_rad)
    y_kick = y_kick_ratio * math.sin(math.radians(phase_advance_deg))
 
    return x, y_plane + y_kick
 
 
def find_best_timings(T, hook_clock, y_kick_ratio, target=(0.0, 0.0), n=1440, top_k=3):
    """1周期分を細かく走査し、目標位置に最も近くなる待ち時間(t_d)候補を探す。"""
    if T <= 0:
        return [], np.array([]), np.array([]), np.array([])
    ts = np.linspace(0, T, n, endpoint=False)
    xs = np.empty(n)
    ys = np.empty(n)
    for i, t in enumerate(ts):
        xs[i], ys[i] = calc_xy(T, t, hook_clock, y_kick_ratio)
    dist = np.sqrt((xs - target[0]) ** 2 + (ys - target[1]) ** 2)
 
    candidates = []
    for i in range(n):
        if dist[i] <= dist[i - 1] and dist[i] <= dist[(i + 1) % n]:
            candidates.append((float(ts[i]), float(dist[i]), float(xs[i]), float(ys[i])))
    candidates.sort(key=lambda c: c[1])
    return candidates[:top_k], ts, xs, ys
 
 
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
# 変更頻度が高い「パーツ設定(チェーン・リング)」を最優先タブに配置
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs(["⚙️ パーツ設定", "🕹️ プレイ条件", "📋 保存データ", "🎯 2D解析(奥行き含む)"])
 
# ------------------------------------------
# タブ1: パーツ設定（台ごとに変える最重要項目）
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
# タブ2: プレイ条件（落下時間・フック向き）
# ------------------------------------------
with tab2:
    st.markdown("##### 奥移動〜落下までの時間")
    t_d = st.number_input("秒", value=3.00, step=0.1, format="%.2f", label_visibility="collapsed")
 
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
 
    st.divider()
    st.markdown("##### 奥行き(Y軸)の振れ幅")
    st.caption("奥移動が急停止するほど大きくなる、前後方向の揺れの強さ（目安・実戦で調整）")
    y_kick_ratio = st.slider("奥行きの振れ幅比率", 0, 100, 50, format="%d%%", label_visibility="collapsed") / 100.0
 
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
# 結果表示
# ==========================================
st.markdown("### 📊 予測結果")
 
rcol1, rcol2 = st.columns(2)
with rcol1:
    if T_auto > 0:
        render_badge("🔴 自動計算", "#e63946", "右" if x_auto >= 0 else "左", f"{abs(x_auto*100):.0f}",
                     f"周期 約{T_auto:.2f}秒 / 重心 {L_cm:.1f}cm")
with rcol2:
    if T_manual > 0:
        render_badge("🔵 手動入力", "#457b9d", "右" if x_manual >= 0 else "左", f"{abs(x_manual*100):.0f}",
                     f"周期 {T_manual:.2f}秒 / 逆算重心 {L_manual_cm:.1f}cm")
 
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
st.markdown("### 💾 現在のパラメータを保存")
 
st.text_input("店舗・筐体名 (例: 〇〇店 UFO9 1番台 右側)", key="store_name")
if st.button("設定を保存する", use_container_width=True, type="primary"):
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
 
# ------------------------------------------
# タブ4: 2D解析（X軸+Y軸の合成振動 / 楕円軌道 / 自動探索）
# ------------------------------------------
with tab4:
    st.caption(
        "奥移動が止まる瞬間に生まれる奥行き(Y軸)方向の揺れを、"
        "従来のX軸(フックの向きで決まる揺れ)に合成します。"
        "同じ周期の2成分が合わさるため、軌道は基本的に楕円を描きます。"
    )
 
    with st.expander("🎯 目標位置を調整（通常は中央=0%のままでOK）"):
        tgcol1, tgcol2 = st.columns(2)
        target_x = tgcol1.number_input("目標X (左右, %)", value=0.0, step=5.0, format="%.0f") / 100.0
        target_y = tgcol2.number_input("目標Y (奥行き, %)", value=0.0, step=5.0, format="%.0f") / 100.0
 
    if T_auto <= 0 and T_manual <= 0:
        st.info("周期が計算できていません。「パーツ設定」タブを確認してください。")
    else:
        # --- 現在のt_dでの位置 ---
        x2_auto, y2_auto = calc_xy(T_auto, t_d, hook_clock, y_kick_ratio) if T_auto > 0 else (0, 0)
        x2_manual, y2_manual = calc_xy(T_manual, t_d, hook_clock, y_kick_ratio) if T_manual > 0 else (0, 0)
 
        # --- 自動探索 ---
        best_auto, ts_a, xs_a, ys_a = find_best_timings(T_auto, hook_clock, y_kick_ratio, (target_x, target_y)) if T_auto > 0 else ([], np.array([]), np.array([]), np.array([]))
        best_manual, ts_m, xs_m, ys_m = find_best_timings(T_manual, hook_clock, y_kick_ratio, (target_x, target_y)) if T_manual > 0 else ([], np.array([]), np.array([]), np.array([]))
 
        # --- 楕円軌道の可視化 ---
        fig2, ax2 = plt.subplots(figsize=(6, 6))
        if len(xs_a) > 0:
            ax2.plot(xs_a, ys_a, color='#e63946', alpha=0.5, linewidth=1.5, label="🔴 自動計算の軌道")
            ax2.plot(x2_auto, y2_auto, 'o', color='#e63946', markersize=12)
            if best_auto:
                bx, by = best_auto[0][2], best_auto[0][3]
                ax2.plot(bx, by, '*', color='#e63946', markersize=20, markeredgecolor='black', markeredgewidth=0.6)
        if len(xs_m) > 0:
            ax2.plot(xs_m, ys_m, color='#457b9d', alpha=0.5, linewidth=1.5, label="🔵 手動入力の軌道")
            ax2.plot(x2_manual, y2_manual, 'o', color='#457b9d', markersize=12)
            if best_manual:
                bx, by = best_manual[0][2], best_manual[0][3]
                ax2.plot(bx, by, '*', color='#457b9d', markersize=20, markeredgecolor='black', markeredgewidth=0.6)
 
        ax2.plot(target_x, target_y, 'g+', markersize=16, markeredgewidth=3, label="🎯 目標位置")
        ax2.axhline(0, color='gray', linestyle=':', linewidth=0.8)
        ax2.axvline(0, color='gray', linestyle=':', linewidth=0.8)
        ax2.set_xlabel("← 左　　X(左右)　　右 →")
        ax2.set_ylabel("← 手前　　Y(奥行き)　　奥 →")
        ax2.set_aspect('equal', adjustable='box')
 
        all_vals = np.concatenate([xs_a, ys_a, xs_m, ys_m, np.array([target_x, target_y, 0.3])])
        lim = max(0.5, np.nanmax(np.abs(all_vals)) * 1.25) if len(all_vals) else 1.2
        ax2.set_xlim(-lim, lim)
        ax2.set_ylim(-lim, lim)
        ax2.legend(loc='upper right', fontsize=8)
        st.pyplot(fig2)
        st.caption("● = 現在の待ち時間での位置　★ = その周期での最適な待ち時間での位置")
 
        st.divider()
 
        # --- 現在地と推奨タイミング ---
        rcol_a, rcol_b = st.columns(2)
        with rcol_a:
            st.markdown("**🔴 自動計算**")
            if T_auto > 0:
                st.write(f"現在(t_d={t_d:.2f}秒): X {x2_auto*100:+.0f}% / Y {y2_auto*100:+.0f}%")
                if best_auto:
                    st.success("おすすめの待ち時間")
                    for bt, bd, bx, by in best_auto:
                        st.markdown(f"- **{bt:.2f}秒** → X {bx*100:+.0f}% / Y {by*100:+.0f}% (誤差 {bd*100:.0f}%)")
            else:
                st.caption("周期未計算")
 
        with rcol_b:
            st.markdown("**🔵 手動入力**")
            if T_manual > 0:
                st.write(f"現在(t_d={t_d:.2f}秒): X {x2_manual*100:+.0f}% / Y {y2_manual*100:+.0f}%")
                if best_manual:
                    st.success("おすすめの待ち時間")
                    for bt, bd, bx, by in best_manual:
                        st.markdown(f"- **{bt:.2f}秒** → X {bx*100:+.0f}% / Y {by*100:+.0f}% (誤差 {bd*100:.0f}%)")
            else:
                st.caption("周期未計算")
 
        st.caption(
            "※「誤差」は目標位置からのズレの目安（値が小さいほど中心に近いタイミング）です。"
            "候補は1周期内で計算しているので、実際に押すのは表示された秒数、"
            "またはそこに周期Tを足した時刻になります。"
        )
 
