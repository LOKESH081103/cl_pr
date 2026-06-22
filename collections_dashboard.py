import streamlit as st
import pandas as pd
import base64
from datetime import date

st.set_page_config(page_title="Daily Collections Update", layout="wide")

# ── EXACT column indices (0-based, arrow columns included) ────────────────────
COL_ZONE       = 0
COL_FR_FLOW    = 2;  COL_FR_EFF  = 3;  COL_FR_LMTD  = 6
COL_129_FLOW   = 9;  COL_129_EFF = 11; COL_129_LMTD = 14
COL_NORM_EFF   = 21; COL_NORM_LMTD = 24
COL_3059_FLOW  = 29; COL_3059_EFF = 31; COL_3059_LMTD = 34
COL_S3_FLOW    = 40; COL_S3_EFF   = 42; COL_S3_LMTD   = 45

SUBZONES = ['NORTH_1','NORTH_2','NORTH_3','EAST_1','EAST_2',
            'SOUTH_1','SOUTH_2','WEST_1','WEST_2']
DISPLAY  = {
    'NORTH_1':'North 1','NORTH_2':'North 2','NORTH_3':'North 3',
    'EAST_1':'East 1','EAST_2':'East 2',
    'SOUTH_1':'South 1','SOUTH_2':'South 2',
    'WEST_1':'West 1','WEST_2':'West 2',
}

# ── Helpers ───────────────────────────────────────────────────────────────────
def pct(val):
    """
    Parse a percentage value from Excel or CSV.
    Excel stores % as decimals (0.5746) OR as strings ('57.46%').
    • If the raw string ends with '%'  → strip it, parse float as-is (already ×100)
    • If float and abs value < 1.5    → it's a fraction, multiply by 100
    • Otherwise                        → use as-is
    """
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip()
    if s in ('', 'nan', 'None', '-'):
        return None
    has_pct_sign = s.endswith('%')
    s_clean = s.replace('%', '').replace(',', '')
    try:
        f = float(s_clean)
    except ValueError:
        return None
    if has_pct_sign:
        # Already human-readable: "57.46%" → 57.46
        return f
    else:
        # Raw decimal from Excel: 0.5746 → 57.46
        if abs(f) < 1.5:
            return round(f * 100, 4)
        return f

def num(val):
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    s = str(val).strip().replace(',', '').replace('%', '')
    if s in ('', 'nan', 'None', '-'):
        return None
    try:
        return float(s)
    except ValueError:
        return None

def fmt_pct(v):
    return f"{v:.2f}%" if v is not None else '-'

def fmt_num(v):
    return f"{v:,.2f}" if v is not None else '-'

# ── File loading ──────────────────────────────────────────────────────────────
def load_file(file):
    name = file.name.lower()
    if name.endswith('.csv'):
        return pd.read_csv(file, header=None, dtype=str)
    elif name.endswith('.xlsb'):
        return pd.read_excel(file, sheet_name="PROJ-OVERALL",
                             engine="pyxlsb", header=None, dtype=str)
    else:
        return pd.read_excel(file, sheet_name="PROJ-OVERALL",
                             header=None, dtype=str)

def find_data_rows(df):
    targets = {
        'NORTH','NORTH_1','NORTH_2','NORTH_3',
        'EAST','EAST_1','EAST_2',
        'SOUTH','SOUTH_1','SOUTH_2',
        'WEST','WEST_1','WEST_2',
        'PAN_INDIA'
    }
    result = []
    for _, row in df.iterrows():
        cell = str(row.iloc[0]).strip().upper().replace(' ', '_')
        if cell in targets:
            result.append(row.tolist())
    return result

def get_row(rows, name):
    norm = name.upper().replace(' ', '_')
    for r in rows:
        cell = str(r[0]).strip().upper().replace(' ', '_')
        if cell == norm:
            return r
    return None

def safe_get(row, idx):
    if row is None or idx >= len(row):
        return None
    return row[idx]

def extract_all(rows):
    all_zones = ['NORTH','NORTH_1','NORTH_2','NORTH_3',
                 'EAST','EAST_1','EAST_2',
                 'SOUTH','SOUTH_1','SOUTH_2',
                 'WEST','WEST_1','WEST_2','PAN_INDIA']
    metrics = {}
    for z in all_zones:
        r = get_row(rows, z)
        if r is None:
            continue
        metrics[z] = {
            'fresh_flow' : num(safe_get(r, COL_FR_FLOW)),
            'fresh_eff'  : pct(safe_get(r, COL_FR_EFF)),
            'fresh_lmtd' : pct(safe_get(r, COL_FR_LMTD)),
            '129_flow'   : num(safe_get(r, COL_129_FLOW)),
            '129_eff'    : pct(safe_get(r, COL_129_EFF)),
            '129_lmtd'   : pct(safe_get(r, COL_129_LMTD)),
            'norm_eff'   : pct(safe_get(r, COL_NORM_EFF)),
            'norm_lmtd'  : pct(safe_get(r, COL_NORM_LMTD)),
            '3059_flow'  : num(safe_get(r, COL_3059_FLOW)),
            '3059_eff'   : pct(safe_get(r, COL_3059_EFF)),
            '3059_lmtd'  : pct(safe_get(r, COL_3059_LMTD)),
            's3_flow'    : num(safe_get(r, COL_S3_FLOW)),
            's3_eff'     : pct(safe_get(r, COL_S3_EFF)),
            's3_lmtd'    : pct(safe_get(r, COL_S3_LMTD)),
        }
    return metrics

def bottom2_eff(today_m, eff_key):
    vals = [(DISPLAY[sz], today_m.get(sz, {}).get(eff_key))
            for sz in SUBZONES if today_m.get(sz, {}).get(eff_key) is not None]
    return sorted(vals, key=lambda x: x[1])[:2]

def bottom2_flow(today_m, flow_key):
    vals = [(DISPLAY[sz], today_m.get(sz, {}).get(flow_key))
            for sz in SUBZONES if today_m.get(sz, {}).get(flow_key) is not None]
    return sorted(vals, key=lambda x: x[1])[:2]

# ── HTML Report Generator ─────────────────────────────────────────────────────
def build_html_report(today_m, yest_m, date_str):
    pi_t = today_m.get('PAN_INDIA', {})
    pi_y = yest_m.get('PAN_INDIA', {})

    # ── Section 1 data ────────────────────────────────────────────────────────
    eff_buckets_s1 = [
        ("Fresh",              'fresh_eff',  'fresh_lmtd',  'fresh_flow'),
        ("1–29",               '129_eff',    '129_lmtd',    '129_flow'),
        ("1–29 Norm%",         'norm_eff',   'norm_lmtd',   None),
        ("30-59",              '3059_eff',   '3059_lmtd',   '3059_flow'),
        ("60-89 (S3 CONCERN)", 's3_eff',     's3_lmtd',     's3_flow'),
    ]

    def s1_rows():
        html = ""
        for label, eff_k, lmtd_k, flow_k in eff_buckets_s1:
            t_eff  = pi_t.get(eff_k)
            y_eff  = pi_y.get(eff_k)
            t_lmtd = pi_t.get(lmtd_k)
            t_flow = pi_t.get(flow_k) if flow_k else None
            html += f"""
            <tr>
              <td class="label">{label}</td>
              <td class="val today">{fmt_pct(t_eff)}</td>
              <td class="val">{fmt_pct(y_eff)}</td>
              <td class="val">{fmt_pct(t_lmtd)}</td>
              <td class="val flow">{fmt_num(t_flow) if t_flow is not None else '—'}</td>
            </tr>"""
        return html

    # ── Section 2 data ────────────────────────────────────────────────────────
    eff_buckets_s2 = [
        ("Fresh",               'fresh_eff'),
        ("1-29 (S2 Concern)",   '129_eff'),
        ("1-29 Norm",           'norm_eff'),
        ("30-59",               '3059_eff'),
        ("60-89 (S3 Concern)",  's3_eff'),
    ]

    def s2_rows():
        html = ""
        for label, eff_k in eff_buckets_s2:
            b = bottom2_eff(today_m, eff_k)
            b1n = b[0][0] if len(b) > 0 else '—'
            b1v = fmt_pct(b[0][1]) if len(b) > 0 else '—'
            b2n = b[1][0] if len(b) > 1 else '—'
            b2v = fmt_pct(b[1][1]) if len(b) > 1 else '—'
            html += f"""
            <tr>
              <td class="label">{label}</td>
              <td class="val subzone">{b1n}</td>
              <td class="val today">{b1v}</td>
              <td class="val subzone">{b2n}</td>
              <td class="val">{b2v}</td>
            </tr>"""
        return html

    # ── Section 3 data ────────────────────────────────────────────────────────
    flow_buckets_s3 = [
        ("Fresh",               'fresh_flow'),
        ("1-29 (S2 Concern)",   '129_flow'),
        ("30-59",               '3059_flow'),
        ("60-89 (S3 Concern)",  's3_flow'),
    ]

    def s3_rows():
        html = ""
        for label, flow_k in flow_buckets_s3:
            b = bottom2_flow(today_m, flow_k)
            b1n = b[0][0] if len(b) > 0 else '—'
            b1v = fmt_num(b[0][1]) if len(b) > 0 else '—'
            b2n = b[1][0] if len(b) > 1 else '—'
            b2v = fmt_num(b[1][1]) if len(b) > 1 else '—'
            html += f"""
            <tr>
              <td class="label">{label}</td>
              <td class="val subzone">{b1n}</td>
              <td class="val today">{b1v}</td>
              <td class="val subzone">{b2n}</td>
              <td class="val">{b2v}</td>
            </tr>"""
        return html

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<title>Daily Collections Update | {date_str}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

  * {{ box-sizing: border-box; margin: 0; padding: 0; }}

  body {{
    font-family: 'Inter', sans-serif;
    background: #f0f4f8;
    color: #1a202c;
    padding: 32px 24px;
  }}

  .report-wrapper {{
    max-width: 860px;
    margin: 0 auto;
  }}

  /* ── Header ── */
  .report-header {{
    background: linear-gradient(135deg, #1a365d 0%, #2b6cb0 100%);
    border-radius: 16px 16px 0 0;
    padding: 28px 36px 24px;
    color: #fff;
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
  }}
  .report-header .title {{
    font-size: 20px;
    font-weight: 700;
    letter-spacing: 0.5px;
  }}
  .report-header .subtitle {{
    font-size: 13px;
    opacity: 0.75;
    margin-top: 4px;
    font-weight: 400;
  }}
  .report-header .badge {{
    background: rgba(255,255,255,0.18);
    border: 1px solid rgba(255,255,255,0.3);
    border-radius: 8px;
    padding: 6px 14px;
    font-size: 13px;
    font-weight: 600;
    white-space: nowrap;
  }}

  /* ── Body card ── */
  .report-body {{
    background: #ffffff;
    border-radius: 0 0 16px 16px;
    padding: 32px 36px 36px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
  }}

  /* ── Section ── */
  .section {{ margin-bottom: 36px; }}
  .section:last-child {{ margin-bottom: 0; }}

  .section-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 14px;
  }}
  .section-number {{
    background: #2b6cb0;
    color: #fff;
    font-size: 11px;
    font-weight: 700;
    width: 24px; height: 24px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0;
  }}
  .section-title {{
    font-size: 14px;
    font-weight: 700;
    color: #1a365d;
    text-transform: uppercase;
    letter-spacing: 0.6px;
  }}

  /* ── Table ── */
  table {{
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #e2e8f0;
    font-size: 13px;
  }}
  thead tr {{
    background: #ebf4ff;
  }}
  thead th {{
    padding: 10px 14px;
    text-align: center;
    font-size: 11px;
    font-weight: 700;
    color: #2b6cb0;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 2px solid #bee3f8;
  }}
  thead th:first-child {{ text-align: left; }}

  tbody tr {{
    transition: background 0.15s;
  }}
  tbody tr:nth-child(even) {{
    background: #f7fafc;
  }}
  tbody tr:hover {{
    background: #ebf8ff;
  }}

  td {{
    padding: 10px 14px;
    border-bottom: 1px solid #e2e8f0;
  }}
  tbody tr:last-child td {{
    border-bottom: none;
  }}

  td.label {{
    font-weight: 600;
    color: #2d3748;
    text-align: left;
    white-space: nowrap;
  }}
  td.val {{
    text-align: center;
    color: #4a5568;
    font-variant-numeric: tabular-nums;
  }}
  td.today {{
    font-weight: 700;
    color: #1a365d;
  }}
  td.flow {{
    color: #276749;
    font-weight: 600;
  }}
  td.subzone {{
    font-weight: 600;
    color: #744210;
  }}

  /* ── Footer ── */
  .report-footer {{
    text-align: center;
    margin-top: 20px;
    font-size: 11px;
    color: #a0aec0;
    letter-spacing: 0.3px;
  }}
</style>
</head>
<body>
<div class="report-wrapper">

  <!-- Header -->
  <div class="report-header">
    <div>
      <div class="title">DAILY COLLECTIONS UPDATE</div>
      <div class="subtitle">PAN INDIA — Zone Efficiency Summary</div>
    </div>
    <div class="badge">📅 {date_str}</div>
  </div>

  <!-- Body -->
  <div class="report-body">

    <!-- Section 1 -->
    <div class="section">
      <div class="section-header">
        <div class="section-number">1</div>
        <div class="section-title">Zone Efficiency %</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Bucket</th>
            <th>Today</th>
            <th>Yesterday</th>
            <th>MAY-26 LMTD</th>
            <th>AOD Flow Value (GA Crs.)</th>
          </tr>
        </thead>
        <tbody>
          {s1_rows()}
        </tbody>
      </table>
    </div>

    <!-- Section 2 -->
    <div class="section">
      <div class="section-header">
        <div class="section-number">2</div>
        <div class="section-title">Bottom Sub-Zones | Efficiency %</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Bucket</th>
            <th>Bottom 1</th>
            <th>Eff %</th>
            <th>Bottom 2</th>
            <th>Eff %</th>
          </tr>
        </thead>
        <tbody>
          {s2_rows()}
        </tbody>
      </table>
    </div>

    <!-- Section 3 -->
    <div class="section">
      <div class="section-header">
        <div class="section-number">3</div>
        <div class="section-title">Bottom Sub-Zones | AOD Flow Value Crs.</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Bucket</th>
            <th>Bottom 1</th>
            <th>Flow Value</th>
            <th>Bottom 2</th>
            <th>Flow Value</th>
          </tr>
        </thead>
        <tbody>
          {s3_rows()}
        </tbody>
      </table>
    </div>

  </div><!-- /report-body -->

  <div class="report-footer">
    Generated on {date.today().strftime("%d %b %Y")} &nbsp;|&nbsp; Collections MIS Report &nbsp;|&nbsp; Confidential
  </div>
</div>
</body>
</html>"""
    return html

# ── Streamlit render (mirrors HTML tables) ────────────────────────────────────
def render_report(today_m, yest_m, date_str):
    pi_t = today_m.get('PAN_INDIA', {})
    pi_y = yest_m.get('PAN_INDIA', {})

    st.markdown(f"## 📋 DAILY COLLECTIONS UPDATE | {date_str} &nbsp; PAN INDIA",
                unsafe_allow_html=True)
    st.divider()

    # Section 1
    st.markdown("### 1. Zone Efficiency %")
    buckets = [
        ("Fresh",               'fresh_eff', 'fresh_lmtd', 'fresh_flow'),
        ("1–29",                '129_eff',   '129_lmtd',   '129_flow'),
        ("1–29 Norm%",          'norm_eff',  'norm_lmtd',  None),
        ("30-59",               '3059_eff',  '3059_lmtd',  '3059_flow'),
        ("60-89 (S3 CONCERN)",  's3_eff',    's3_lmtd',    's3_flow'),
    ]
    rows1 = []
    for label, eff_k, lmtd_k, flow_k in buckets:
        rows1.append({
            'Bucket':                   label,
            'Today':                    fmt_pct(pi_t.get(eff_k)),
            'Yesterday':                fmt_pct(pi_y.get(eff_k)),
            'MAY-26 LMTD':              fmt_pct(pi_t.get(lmtd_k)),
            'AOD Flow Value (GA Crs.)': fmt_num(pi_t.get(flow_k)) if flow_k and pi_t.get(flow_k) is not None else '—',
        })
    st.dataframe(pd.DataFrame(rows1).set_index('Bucket'), use_container_width=True)

    # Section 2
    st.markdown("### 2. Bottom Sub-Zones | Efficiency %")
    eff_b2 = [
        ("Fresh",               'fresh_eff'),
        ("1-29 (S2 Concern)",   '129_eff'),
        ("1-29 Norm",           'norm_eff'),
        ("30-59",               '3059_eff'),
        ("60-89 (S3 Concern)",  's3_eff'),
    ]
    rows2 = []
    for label, eff_k in eff_b2:
        b = bottom2_eff(today_m, eff_k)
        rows2.append({
            'Bucket':   label,
            'Bottom 1': b[0][0] if len(b) > 0 else '—',
            'Eff %':    fmt_pct(b[0][1]) if len(b) > 0 else '—',
            'Bottom 2': b[1][0] if len(b) > 1 else '—',
            'Eff % ':   fmt_pct(b[1][1]) if len(b) > 1 else '—',
        })
    st.dataframe(pd.DataFrame(rows2).set_index('Bucket'), use_container_width=True)

    # Section 3
    st.markdown("### 3. Bottom Sub-Zones | AOD Flow Value Crs.")
    flow_b2 = [
        ("Fresh",               'fresh_flow'),
        ("1-29 (S2 Concern)",   '129_flow'),
        ("30-59",               '3059_flow'),
        ("60-89 (S3 Concern)",  's3_flow'),
    ]
    rows3 = []
    for label, flow_k in flow_b2:
        b = bottom2_flow(today_m, flow_k)
        rows3.append({
            'Bucket':       label,
            'Bottom 1':     b[0][0] if len(b) > 0 else '—',
            'Flow Value':   fmt_num(b[0][1]) if len(b) > 0 else '—',
            'Bottom 2':     b[1][0] if len(b) > 1 else '—',
            'Flow Value ':  fmt_num(b[1][1]) if len(b) > 1 else '—',
        })
    st.dataframe(pd.DataFrame(rows3).set_index('Bucket'), use_container_width=True)

# ── Download button ───────────────────────────────────────────────────────────
def download_button(html_str, filename):
    b64 = base64.b64encode(html_str.encode()).decode()
    href = f'data:text/html;base64,{b64}'
    st.markdown(
        f"""
        <a href="{href}" download="{filename}" style="
            display:inline-block;
            margin-top:16px;
            padding:10px 24px;
            background:linear-gradient(135deg,#1a365d,#2b6cb0);
            color:#fff;
            font-family:sans-serif;
            font-size:14px;
            font-weight:600;
            border-radius:8px;
            text-decoration:none;
            letter-spacing:0.3px;
        ">⬇️ Download Report (HTML)</a>
        """,
        unsafe_allow_html=True
    )

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("📊 Daily Collections Update Generator")
st.caption("Upload today's and yesterday's dashboard files to auto-generate the PAN INDIA summary.")

col1, col2 = st.columns(2)
with col1:
    today_file = st.file_uploader("📁 Today's Dashboard", type=['xlsx','xls','xlsb','csv'], key='today')
with col2:
    yest_file  = st.file_uploader("📁 Yesterday's Dashboard", type=['xlsx','xls','xlsb','csv'], key='yest')

report_date = st.text_input("Report Date", value="22-Jun-26", placeholder="e.g. 22-Jun-26")

if st.button("⚡ Generate Report", type="primary", use_container_width=True):
    if not today_file or not yest_file:
        st.error("Please upload both today's and yesterday's dashboard files.")
    else:
        with st.spinner("Parsing dashboards…"):
            try:
                today_df   = load_file(today_file)
                yest_df    = load_file(yest_file)
                today_rows = find_data_rows(today_df)
                yest_rows  = find_data_rows(yest_df)

                if not today_rows or not yest_rows:
                    st.error(
                        "Could not find zone data. Ensure the first column has zone "
                        "names: NORTH, EAST, SOUTH, WEST, PAN INDIA, NORTH_1, etc."
                    )
                else:
                    today_m = extract_all(today_rows)
                    yest_m  = extract_all(yest_rows)

                    render_report(today_m, yest_m, report_date)

                    st.divider()
                    html_report = build_html_report(today_m, yest_m, report_date)
                    fname = f"Collections_Update_{report_date.replace('-','_')}.html"
                    download_button(html_report, fname)

            except Exception as e:
                st.error(f"Error: {e}")
                st.exception(e)

st.divider()
with st.expander("ℹ️ How to use"):
    st.markdown("""
    1. Export the dashboard as **Excel (.xlsx / .xlsb)** or **CSV** — same column layout.
    2. Upload **today's** file on the left, **yesterday's** on the right.
    3. Set the report date and click **Generate Report**.
    4. Click **Download Report** to save a clean HTML file you can open in any browser or print to PDF.
    """)
