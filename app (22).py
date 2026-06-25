import streamlit as st
import openpyxl
from io import BytesIO
from datetime import datetime
import base64, textwrap, tempfile, os

st.set_page_config(page_title="Collections Hourly Snapshot", layout="wide")
st.title("Collections Hourly Snapshot Dashboard")

uploaded_file = st.file_uploader("Upload Excel File", type=["xlsx"])

# ── PARSE ──────────────────────────────────────────────────────────────────────
def parse_sheet3(wb):
    ws  = wb.worksheets[2]
    rows = list(ws.iter_rows(values_only=True))
    eff_row, flow_row = rows[2], rows[3]

    bucket_cols = {
        'Fresh':             2,
        '1-29':              4,
        '1-29 NORM':         6,
        '30-59':             8,
        '60-89':             10,
        'STAGE 2 Reduction': 12,
    }
    bucket_data = {}
    for name, c in bucket_cols.items():
        bucket_data[name] = {
            'eff':  eff_row[c]  or 0,
            'flow': flow_row[c] or 0,
        }

    zone_data = []
    for row in rows[8:23]:
        if row[1] is None:
            continue
        zone_data.append({
            'zone':  row[1],
            'fresh': row[2],
            '1-29':  row[3],
            '30-59': row[4],
            '60-89': row[5],
        })
    return bucket_data, zone_data

def get_val(zone_data, name, bucket):
    for r in zone_data:
        if r['zone'].strip().upper() == name.strip().upper():
            v = r.get(bucket)
            return f"{v*100:.2f}%" if v is not None else "—"
    return "—"

def pct(v):
    return f"{v*100:.2f}%" if v else "—"

def flow_fmt(v):
    return f"₹ {v:,.2f} Crs" if v else "—"

# ── HTML BUILDER ───────────────────────────────────────────────────────────────
ZONE_ORDER = [
    ('PAN INDIA', []),
    ('NORTH',     ['NORTH_1','NORTH_2','NORTH_3']),
    ('SOUTH',     ['SOUTH_1','SOUTH_2']),
    ('WEST',      ['WEST_1','WEST_2']),
    ('EAST',      ['EAST_1','EAST_2']),
]

BOX_CONFIGS = [
    ('Fresh',             'Fresh',             '#1a6080', '#ffffff'),
    ('1-29',              '1-29 (S2 Concern)', '#e6a817', '#ffffff'),
    ('1-29 NORM',         '1-29 Norm',         '#e6a817', '#ffffff'),
    ('30-59',             '30-59',             '#3da850', '#ffffff'),
    ('60-89',             '60-89 (S3 Concern)','#c8846e', '#ffffff'),
    ('STAGE 2 Reduction', 'S2 Roll Back',      '#c8846e', '#ffffff'),
]

def build_html(bucket_data, zone_data, timestamp_str):
    # ── top boxes
    boxes_html = ""
    for key, label, bg, tc in BOX_CONFIGS:
        bd   = bucket_data.get(key, {})
        eff  = bd.get('eff', 0)
        fl   = bd.get('flow', 0)
        boxes_html += f"""
        <div class="box">
          <div class="box-header" style="background:{bg};color:{tc};">{label}</div>
          <div class="box-body">
            <div class="box-eff">{pct(eff)}</div>
            <div class="box-lmtd">vs. LMTD &nbsp;</div>
            <div class="box-flow">Flow Value &nbsp;<b>{fl:,.2f} Crs</b></div>
          </div>
        </div>"""

    # ── sub-zone rows
    zone_rows_html = ""
    for zone_name, subs in ZONE_ORDER:
        display = zone_name.replace('_',' ')
        bg_class = "row-pan" if zone_name == "PAN INDIA" else "row-zone"
        zone_rows_html += f"""
        <tr class="{bg_class}">
          <td class="zone-name"><b>{display}</b></td>
          <td>{get_val(zone_data, zone_name, 'fresh')}</td>
          <td>{get_val(zone_data, zone_name, '1-29')}</td>
          <td>{get_val(zone_data, zone_name, '30-59')}</td>
          <td>{get_val(zone_data, zone_name, '60-89')}</td>
        </tr>"""
        for i, sub in enumerate(subs):
            disp_sub = sub.replace('_',' ')
            alt = "row-alt" if i % 2 == 1 else ""
            zone_rows_html += f"""
        <tr class="row-sub {alt}">
          <td class="sub-name">{disp_sub}</td>
          <td>{get_val(zone_data, sub, 'fresh')}</td>
          <td>{get_val(zone_data, sub, '1-29')}</td>
          <td>{get_val(zone_data, sub, '30-59')}</td>
          <td>{get_val(zone_data, sub, '60-89')}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', Arial, sans-serif;
    background: #f0f2f5;
    padding: 24px;
    width: 1400px;
  }}
  .card {{
    background: white;
    border-radius: 10px;
    box-shadow: 0 2px 12px rgba(0,0,0,0.10);
    padding: 22px 26px 26px 26px;
  }}
  .title {{
    font-size: 20px;
    font-weight: 700;
    color: #1a1a2e;
    margin-bottom: 20px;
    letter-spacing: 0.3px;
  }}
  /* ── TOP BOXES */
  .boxes {{
    display: flex;
    gap: 14px;
    margin-bottom: 24px;
  }}
  .box {{
    flex: 1;
    border-radius: 8px;
    border: 1px solid #dde3ea;
    overflow: hidden;
    box-shadow: 0 1px 4px rgba(0,0,0,0.07);
  }}
  .box-header {{
    padding: 9px 12px;
    font-size: 13px;
    font-weight: 700;
    text-align: center;
    letter-spacing: 0.2px;
  }}
  .box-body {{
    padding: 12px 10px 14px 10px;
    text-align: center;
    background: white;
  }}
  .box-eff {{
    font-size: 22px;
    font-weight: 800;
    color: #1a1a2e;
    line-height: 1.2;
  }}
  .box-lmtd {{
    font-size: 11px;
    color: #888;
    margin: 5px 0 6px 0;
  }}
  .box-flow {{
    font-size: 11.5px;
    color: #444;
  }}
  /* ── TABLE */
  .section-title {{
    font-size: 13px;
    font-weight: 700;
    color: #1a3a5c;
    text-transform: uppercase;
    letter-spacing: 0.6px;
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 2px solid #1a6080;
    display: inline-block;
  }}
  table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 12.5px;
  }}
  thead th {{
    background: #1a6080;
    color: white;
    padding: 9px 12px;
    text-align: center;
    font-weight: 700;
    font-size: 12px;
    letter-spacing: 0.4px;
  }}
  thead th:first-child {{ text-align: left; padding-left: 16px; }}
  td {{
    padding: 8px 12px;
    text-align: center;
    color: #333;
    border-bottom: 1px solid #eef0f3;
  }}
  td:first-child {{ text-align: left; }}
  .row-pan   {{ background: #e6f4ea; }}
  .row-pan td {{ color: #1a5c2a; font-size: 13px; }}
  .row-zone  {{ background: #dce8f0; }}
  .row-zone td {{ color: #1a3a5c; }}
  .zone-name {{ padding-left: 16px !important; }}
  .row-sub td {{ color: #444; }}
  .row-alt   {{ background: #f5f8fb; }}
  .sub-name  {{ padding-left: 30px !important; color: #555 !important; }}
  tr:hover   {{ background: #eef5fb !important; transition: background 0.15s; }}
</style>
</head>
<body>
<div class="card">
  <div class="title">Collections Hourly Snapshot &nbsp;|&nbsp; Updates &nbsp;|&nbsp; {timestamp_str}</div>

  <div class="boxes">{boxes_html}</div>

  <div class="section-title">Sub-Zone Cut (Efficiency%)</div>
  <table>
    <thead>
      <tr>
        <th style="width:22%">ZONE</th>
        <th>FRESH</th>
        <th>1-29</th>
        <th>30-59</th>
        <th>60-89</th>
      </tr>
    </thead>
    <tbody>
      {zone_rows_html}
    </tbody>
  </table>
</div>
</body>
</html>"""
    return html


def render_dashboard_png(bucket_data, zone_data, timestamp_str) -> bytes:
    """Renders the dashboard straight to a PNG using Matplotlib (no browser/Chromium needed)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    W = 1450
    PAD = 24
    CARD_PAD = 26
    inner_w = W - 2 * PAD - 2 * CARD_PAD

    box_gap   = 14
    n_boxes   = len(BOX_CONFIGS)
    box_w     = (inner_w - box_gap * (n_boxes - 1)) / n_boxes
    box_h     = 95
    box_hdr_h = 30

    total_rows = sum(1 + len(subs) for _, subs in ZONE_ORDER)
    row_h      = 30
    header_h   = 34
    title_h    = 30
    section_h  = 30
    gap_after_title   = 14
    gap_after_boxes   = 24
    gap_after_section = 10

    H = (PAD * 2 + CARD_PAD * 2 + title_h + gap_after_title + box_h + gap_after_boxes
         + section_h + gap_after_section + header_h + total_rows * row_h + 10)

    fig, ax = plt.subplots(figsize=(W / 100, H / 100), dpi=200)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.invert_yaxis()
    ax.axis("off")
    fig.patch.set_facecolor("#f0f2f5")

    # card background
    ax.add_patch(Rectangle((PAD, PAD), W - 2 * PAD, H - 2 * PAD,
                            facecolor="white", edgecolor="none", zorder=1))

    x0 = PAD + CARD_PAD
    y  = PAD + CARD_PAD

    ax.text(x0, y, f"Collections Hourly Snapshot  |  Updates  |  {timestamp_str}",
            fontsize=14, fontweight="bold", color="#1a1a2e", ha="left", va="top", zorder=3)
    y += title_h + gap_after_title

    # top boxes
    bx = x0
    for key, label, bg, tc in BOX_CONFIGS:
        bd  = bucket_data.get(key, {})
        eff = bd.get('eff', 0)
        fl  = bd.get('flow', 0)
        ax.add_patch(Rectangle((bx, y), box_w, box_h, facecolor="white",
                                edgecolor="#dde3ea", linewidth=1, zorder=2))
        ax.add_patch(Rectangle((bx, y), box_w, box_hdr_h, facecolor=bg,
                                edgecolor="none", zorder=3))
        ax.text(bx + box_w / 2, y + box_hdr_h / 2, label, fontsize=9.5, fontweight="bold",
                color=tc, ha="center", va="center", zorder=4)
        ax.text(bx + box_w / 2, y + box_hdr_h + 24, pct(eff), fontsize=16, fontweight="bold",
                color="#1a1a2e", ha="center", va="center", zorder=4)
        ax.text(bx + box_w / 2, y + box_hdr_h + 44, "vs. LMTD", fontsize=8,
                color="#888888", ha="center", va="center", zorder=4)
        ax.text(bx + box_w / 2, y + box_hdr_h + 62, f"Flow Value  {fl:,.2f} Crs", fontsize=8,
                color="#444444", ha="center", va="center", zorder=4)
        bx += box_w + box_gap

    y += box_h + gap_after_boxes

    # section title
    ax.text(x0, y, "SUB-ZONE CUT (EFFICIENCY%)", fontsize=9.5, fontweight="bold",
            color="#1a3a5c", ha="left", va="top", zorder=3)
    ax.plot([x0, x0 + 260], [y + section_h - 8, y + section_h - 8],
            color="#1a6080", linewidth=2, zorder=3)
    y += section_h + gap_after_section

    # table
    col_w0      = inner_w * 0.22
    col_w_rest  = (inner_w - col_w0) / 4
    col_x       = [x0, x0 + col_w0, x0 + col_w0 + col_w_rest,
                   x0 + col_w0 + col_w_rest * 2, x0 + col_w0 + col_w_rest * 3]
    headers     = ["ZONE", "FRESH", "1-29", "30-59", "60-89"]

    ax.add_patch(Rectangle((x0, y), inner_w, header_h, facecolor="#1a6080",
                            edgecolor="none", zorder=2))
    ax.text(x0 + 16, y + header_h / 2, headers[0], fontsize=9, fontweight="bold",
            color="white", ha="left", va="center", zorder=3)
    for i in range(1, 5):
        cx = col_x[i] + col_w_rest / 2
        ax.text(cx, y + header_h / 2, headers[i], fontsize=9, fontweight="bold",
                color="white", ha="center", va="center", zorder=3)
    y += header_h

    for zone_name, subs in ZONE_ORDER:
        display  = zone_name.replace('_', ' ')
        is_pan   = zone_name == "PAN INDIA"
        row_bg   = "#e6f4ea" if is_pan else "#dce8f0"
        tcolor   = "#1a5c2a" if is_pan else "#1a3a5c"
        ax.add_patch(Rectangle((x0, y), inner_w, row_h, facecolor=row_bg,
                                edgecolor="none", zorder=2))
        ax.text(x0 + 16, y + row_h / 2, display, fontsize=9.5, fontweight="bold",
                color=tcolor, ha="left", va="center", zorder=3)
        vals = [get_val(zone_data, zone_name, b) for b in ('fresh', '1-29', '30-59', '60-89')]
        for i, v in enumerate(vals):
            cx = col_x[i + 1] + col_w_rest / 2
            ax.text(cx, y + row_h / 2, v, fontsize=9, color=tcolor,
                    ha="center", va="center", zorder=3)
        ax.plot([x0, x0 + inner_w], [y + row_h, y + row_h], color="#eef0f3", linewidth=1, zorder=3)
        y += row_h

        for i, sub in enumerate(subs):
            disp_sub = sub.replace('_', ' ')
            alt      = (i % 2 == 1)
            row_bg   = "#f5f8fb" if alt else "#ffffff"
            ax.add_patch(Rectangle((x0, y), inner_w, row_h, facecolor=row_bg,
                                    edgecolor="none", zorder=2))
            ax.text(x0 + 30, y + row_h / 2, disp_sub, fontsize=9, color="#555555",
                    ha="left", va="center", zorder=3)
            vals = [get_val(zone_data, sub, b) for b in ('fresh', '1-29', '30-59', '60-89')]
            for j, v in enumerate(vals):
                cx = col_x[j + 1] + col_w_rest / 2
                ax.text(cx, y + row_h / 2, v, fontsize=9, color="#444444",
                        ha="center", va="center", zorder=3)
            ax.plot([x0, x0 + inner_w], [y + row_h, y + row_h], color="#eef0f3", linewidth=1, zorder=3)
            y += row_h

    buf = BytesIO()
    fig.savefig(buf, format="png", facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


# ── STREAMLIT UI ──────────────────────────────────────────────────────────────
if uploaded_file:
    wb = openpyxl.load_workbook(uploaded_file, data_only=True)
    bucket_data, zone_data = parse_sheet3(wb)

    now = datetime.now()
    timestamp_str = (
        f"{now.day}-{now.strftime('%b-%y')} | "
        f"{now.strftime('%A')} | "
        f"{now.strftime('%I:%M %p').lstrip('0')}"
    )

    html = build_html(bucket_data, zone_data, timestamp_str)

    # ── live preview in streamlit
    st.components.v1.html(html, height=820, scrolling=True)

    st.markdown("---")
    st.markdown("### ⬇️ Download High-Resolution PNG")

    if st.button("🖼️ Generate & Download Image"):
        with st.spinner("Rendering dashboard to high-res PNG..."):
            try:
                png_bytes = render_dashboard_png(bucket_data, zone_data, timestamp_str)
                st.success("Image ready!")
                st.image(png_bytes, caption="Collections Hourly Snapshot", use_container_width=True)
                st.download_button(
                    label="⬇️ Download PNG",
                    data=png_bytes,
                    file_name=f"collections_snapshot_{now.strftime('%Y%m%d_%H%M')}.png",
                    mime="image/png",
                )
            except Exception as e:
                st.error(f"Error generating image: {e}")
else:
    st.info("📂 Please upload the Excel file (.xlsx) to get started.")
