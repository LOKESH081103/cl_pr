import streamlit as st
import openpyxl
import pandas as pd
from io import BytesIO
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import matplotlib.gridspec as gridspec
import numpy as np
from datetime import datetime
import os

st.set_page_config(page_title="Collections Hourly Snapshot", layout="wide")

st.title("Collections Hourly Snapshot Dashboard")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

def parse_sheet3(wb):
    ws = wb.worksheets[2]
    rows = list(ws.iter_rows(values_only=True))

    # Row indices (0-based):
    # Row 1 (index 1): headers -> Fresh, 1-29, 1-29 NORM, 30-59, 60-89, STAGE 2 Reduction
    # Row 2 (index 2): EFF values
    # Row 3 (index 3): Flow values

    header_row = rows[1]
    eff_row    = rows[2]
    flow_row   = rows[3]

    # Columns for each bucket (0-based in tuple):
    # B=1, C=2, D=3, E=4, F=5, G=6, H=7, I=8, J=9, K=10, L=11, M=12
    buckets = {
        'Fresh':              {'eff_col': 2,  'flow_col': 2},
        '1-29':               {'eff_col': 4,  'flow_col': 4},
        '1-29 NORM':          {'eff_col': 6,  'flow_col': 6},
        '30-59':              {'eff_col': 8,  'flow_col': 8},
        '60-89':              {'eff_col': 10, 'flow_col': 10},
        'STAGE 2 Reduction':  {'eff_col': 12, 'flow_col': 12},
    }

    data = {}
    for name, cols in buckets.items():
        eff_val  = eff_row[cols['eff_col']]
        flow_val = flow_row[cols['flow_col']]
        data[name] = {
            'eff':  eff_val  if eff_val  is not None else 0,
            'flow': flow_val if flow_val is not None else 0,
        }

    # Sub-zone table starts at row index 7 (row 8 in Excel)
    # Columns: B=zone, C=Fresh, D=1-29, E=30-59, F=60-89
    zone_data = []
    for row in rows[7:22]:
        zone = row[1]
        if zone is None:
            continue
        zone_data.append({
            'zone':  zone,
            'fresh': row[2],
            '1-29':  row[3],
            '30-59': row[4],
            '60-89': row[5],
        })

    return data, zone_data

def fmt_pct(v):
    return f"{v*100:.2f}%" if v is not None else "—"

def fmt_flow(v):
    return f"{v:,.2f} Crs" if v is not None else "—"

BOX_CONFIGS = [
    {'key': 'Fresh',             'label': 'Fresh',             'bg': '#1B5E7A', 'text': 'white'},
    {'key': '1-29',              'label': '1-29 (S2 Concern)', 'bg': '#F5A800', 'text': 'white'},
    {'key': '1-29 NORM',         'label': '1-29 Norm',         'bg': '#F5A800', 'text': 'white'},
    {'key': '30-59',             'label': '30-59',             'bg': '#4CAF50', 'text': 'white'},
    {'key': '60-89',             'label': '60-89 (S3 Concern)','bg': '#E8A090', 'text': 'white'},
    {'key': 'STAGE 2 Reduction', 'label': 'S2 Roll Back',      'bg': '#E8A090', 'text': 'white'},
]

ZONE_ORDER = [
    ('NORTH',   ['NORTH_1','NORTH_2','NORTH_3']),
    ('SOUTH',   ['SOUTH_1','SOUTH_2']),
    ('WEST',    ['WEST_1','WEST_2']),
    ('EAST',    ['EAST_1','EAST_2']),
    ('PAN INDIA', []),
]

def get_zone_val(zone_data, zone_name, bucket):
    for r in zone_data:
        if r['zone'].strip().upper() == zone_name.strip().upper():
            return r.get(bucket)
    return None

def generate_dashboard_image(bucket_data, zone_data, timestamp_str):
    fig = plt.figure(figsize=(22, 14), facecolor='white')
    fig.patch.set_facecolor('white')

    # ─── Title ───────────────────────────────────────────────────
    fig.text(0.5, 0.97, f"Collections Hourly Snapshot  |  Updates  |  {timestamp_str}",
             ha='center', va='top', fontsize=14, fontweight='bold', color='#222')

    # ─── TOP 6 BOXES ─────────────────────────────────────────────
    box_axes = []
    for i in range(6):
        ax = fig.add_axes([0.03 + i*0.159, 0.76, 0.148, 0.175])
        ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
        box_axes.append(ax)

    for i, cfg in enumerate(BOX_CONFIGS):
        ax   = box_axes[i]
        key  = cfg['key']
        bd   = bucket_data.get(key, {})
        eff  = bd.get('eff', 0)
        flow = bd.get('flow', 0)

        # header band
        ax.add_patch(FancyBboxPatch((0,0), 1, 1,
            boxstyle="round,pad=0.02", linewidth=1.2,
            edgecolor='#ccc', facecolor='white'))
        ax.add_patch(FancyBboxPatch((0, 0.68), 1, 0.32,
            boxstyle="square,pad=0", linewidth=0,
            facecolor=cfg['bg'], clip_on=True))

        ax.text(0.5, 0.82, cfg['label'], ha='center', va='center',
                fontsize=9, fontweight='bold', color=cfg['text'],
                transform=ax.transAxes)

        ax.text(0.5, 0.54, fmt_pct(eff), ha='center', va='center',
                fontsize=12, fontweight='bold', color='#111',
                transform=ax.transAxes)

        ax.text(0.5, 0.36, "vs. LMTD", ha='center', va='center',
                fontsize=7.5, color='#666', transform=ax.transAxes)

        ax.text(0.5, 0.18, f"Flow Value  {flow:,.2f} Crs",
                ha='center', va='center',
                fontsize=7.5, color='#333', fontweight='bold',
                transform=ax.transAxes)

    # ─── SUB-ZONE CUT EFFICIENCY TABLE ───────────────────────────
    table_ax = fig.add_axes([0.03, 0.05, 0.45, 0.66])
    table_ax.set_xlim(0, 1); table_ax.set_ylim(0, 1); table_ax.axis('off')

    # Outer border
    table_ax.add_patch(FancyBboxPatch((0,0), 1, 1,
        boxstyle="round,pad=0.01", linewidth=1.2,
        edgecolor='#bbb', facecolor='white'))

    # Section title
    table_ax.text(0.5, 0.96, "SUB-ZONE CUT (EFFICIENCY%)",
                  ha='center', va='top', fontsize=10, fontweight='bold', color='#222')

    # Column headers
    cols_x = [0.08, 0.30, 0.50, 0.70, 0.88]
    col_labels = ['ZONE', 'FRESH', '1-29', '30-59', '60-89']
    table_ax.axhline(0.89, xmin=0.02, xmax=0.98, color='#1B5E7A', linewidth=1.5)
    for cx, cl in zip(cols_x, col_labels):
        table_ax.text(cx, 0.915, cl, ha='center', va='center',
                      fontsize=8, fontweight='bold', color='#1B5E7A')
    table_ax.axhline(0.89, xmin=0.02, xmax=0.98, color='#1B5E7A', linewidth=1)

    row_h   = 0.056
    y_start = 0.855
    row_idx = 0

    def pct_cell(v):
        if v is None: return "—"
        return f"{v*100:.2f}%"

    for zone_name, subs in ZONE_ORDER:
        # Zone header row
        y = y_start - row_idx * row_h
        bg_color = '#D0DCE8' if zone_name != 'PAN INDIA' else '#eaf4ea'
        table_ax.add_patch(plt.Rectangle((0.01, y - row_h*0.8), 0.98, row_h*0.85,
                                         color=bg_color, zorder=0))
        table_ax.text(cols_x[0] - 0.05, y - row_h*0.35, zone_name,
                      ha='left', va='center', fontsize=8.5, fontweight='bold', color='#1B5E7A')
        for ci, bucket in enumerate(['fresh','1-29','30-59','60-89']):
            val = get_zone_val(zone_data, zone_name, bucket)
            table_ax.text(cols_x[ci+1], y - row_h*0.35, pct_cell(val),
                          ha='center', va='center', fontsize=8, color='#222')
        row_idx += 1

        # Sub-zone rows
        for sub in subs:
            y = y_start - row_idx * row_h
            if row_idx % 2 == 0:
                table_ax.add_patch(plt.Rectangle((0.01, y - row_h*0.8), 0.98, row_h*0.85,
                                                 color='#f5f8fc', zorder=0))
            table_ax.text(cols_x[0], y - row_h*0.35, sub.replace('_', ' '),
                          ha='left', va='center', fontsize=8, color='#333')
            for ci, bucket in enumerate(['fresh','1-29','30-59','60-89']):
                val = get_zone_val(zone_data, sub, bucket)
                table_ax.text(cols_x[ci+1], y - row_h*0.35, pct_cell(val),
                              ha='center', va='center', fontsize=8, color='#444')
            row_idx += 1

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    plt.close(fig)
    buf.seek(0)
    return buf


# ─── MAIN ────────────────────────────────────────────────────────────────────

if uploaded_file:
    wb = openpyxl.load_workbook(uploaded_file, data_only=True)
    bucket_data, zone_data = parse_sheet3(wb)

    now = datetime.now()
    timestamp_str = now.strftime("%-d-%b-%y | %A | %-I:%M %p")

    # ── TOP 6 METRIC BOXES ──────────────────────────────────────────────────
    st.markdown("### 📊 Key Metrics")
    cols = st.columns(6)
    box_styles = [
        ("Fresh",             "#1B5E7A", "white"),
        ("1-29 (S2 Concern)", "#F5A800", "white"),
        ("1-29 Norm",         "#F5A800", "white"),
        ("30-59",             "#4CAF50", "white"),
        ("60-89 (S3 Concern)","#E8A090", "#333"),
        ("S2 Roll Back",      "#E8A090", "#333"),
    ]
    keys = ['Fresh','1-29','1-29 NORM','30-59','60-89','STAGE 2 Reduction']

    for i, (col, (label, bg, tc)) in enumerate(zip(cols, box_styles)):
        key = keys[i]
        bd  = bucket_data.get(key, {})
        eff  = bd.get('eff', 0)
        flow = bd.get('flow', 0)

        col.markdown(f"""
        <div style="
            background:{bg}; border-radius:10px; padding:10px 8px 12px 8px;
            text-align:center; min-height:130px; box-shadow:0 2px 6px #0002;">
            <div style="color:{tc};font-weight:bold;font-size:14px;margin-bottom:8px">{label}</div>
            <div style="color:{'white' if bg not in ['#E8A090'] else '#222'};
                font-size:20px;font-weight:bold;margin-bottom:4px">{fmt_pct(eff)}</div>
            <div style="color:{'#eee' if bg not in ['#E8A090'] else '#555'};
                font-size:11px;margin-bottom:6px">vs. LMTD &nbsp;</div>
            <div style="color:{'white' if bg not in ['#E8A090'] else '#333'};
                font-size:11px;font-weight:bold">Flow Value &nbsp;{flow:,.2f} Crs</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── SUB-ZONE TABLE ──────────────────────────────────────────────────────
    st.markdown("### 📋 Sub-Zone Cut (Efficiency%)")

    def pct_cell(v):
        return f"{v*100:.2f}%" if v is not None else "—"

    table_rows = []
    for zone_name, subs in ZONE_ORDER:
        # Zone header
        row = {
            'ZONE': f"**{zone_name}**",
            'FRESH': pct_cell(get_zone_val(zone_data, zone_name, 'fresh')),
            '1-29':  pct_cell(get_zone_val(zone_data, zone_name, '1-29')),
            '30-59': pct_cell(get_zone_val(zone_data, zone_name, '30-59')),
            '60-89': pct_cell(get_zone_val(zone_data, zone_name, '60-89')),
            '_is_zone': True
        }
        table_rows.append(row)
        for sub in subs:
            table_rows.append({
                'ZONE': sub.replace('_', ' '),
                'FRESH': pct_cell(get_zone_val(zone_data, sub, 'fresh')),
                '1-29':  pct_cell(get_zone_val(zone_data, sub, '1-29')),
                '30-59': pct_cell(get_zone_val(zone_data, sub, '30-59')),
                '60-89': pct_cell(get_zone_val(zone_data, sub, '60-89')),
                '_is_zone': False
            })

    df_display = pd.DataFrame(table_rows).drop(columns=['_is_zone'])
    st.dataframe(df_display, use_container_width=True, hide_index=True)

    st.markdown("---")

    # ── GENERATE + DOWNLOAD IMAGE ────────────────────────────────────────────
    st.markdown("### 🖼️ Download Dashboard Image")
    if st.button("Generate & Download Image"):
        with st.spinner("Generating dashboard image..."):
            img_buf = generate_dashboard_image(bucket_data, zone_data, timestamp_str)
        st.image(img_buf, caption="Collections Hourly Snapshot", use_container_width=True)
        img_buf.seek(0)
        st.download_button(
            label="⬇️ Download PNG",
            data=img_buf,
            file_name=f"collections_snapshot_{now.strftime('%Y%m%d_%H%M')}.png",
            mime="image/png"
        )
else:
    st.info("Please upload the Excel file to get started.")
