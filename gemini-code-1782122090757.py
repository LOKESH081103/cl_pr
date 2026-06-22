from PIL import Image, ImageDraw, ImageFont
import io
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
 
def create_report_image(today_m, yest_m, report_date):
    """
    Create a professional report image with structured layout.
    """
    pi_t = today_m.get('PAN_INDIA', {})
    pi_y = yest_m.get('PAN_INDIA', {})
 
    # ── Image dimensions ──
    width = 1600
    height = 2400
    img = Image.new("RGB", (width, height), "#ffffff")
    draw = ImageDraw.Draw(img)
 
    # ── Colors ──
    COLOR_HEADER_BG = "#1a365d"
    COLOR_HEADER_TEXT = "#ffffff"
    COLOR_SECTION_BG = "#2b6cb0"
    COLOR_SECTION_TEXT = "#ffffff"
    COLOR_GRID_HEADER_BG = "#ebf4ff"
    COLOR_GRID_HEADER_TEXT = "#2b6cb0"
    COLOR_GRID_BORDER = "#e2e8f0"
    COLOR_GRID_ROW_ALT = "#f7fafc"
    COLOR_TEXT = "#1a202c"
    COLOR_TEXT_SECONDARY = "#4a5568"
    COLOR_SUBZONE = "#744210"
 
    # ── Fonts ──
    try:
        font_title = ImageFont.truetype("arial.ttf", 48)
        font_subtitle = ImageFont.truetype("arial.ttf", 20)
        font_section = ImageFont.truetype("arial.ttf", 24)
        font_header = ImageFont.truetype("arial.ttf", 16)
        font_body = ImageFont.truetype("arial.ttf", 14)
        font_small = ImageFont.truetype("arial.ttf", 12)
    except:
        font_title = ImageFont.load_default()
        font_subtitle = ImageFont.load_default()
        font_section = ImageFont.load_default()
        font_header = ImageFont.load_default()
        font_body = ImageFont.load_default()
        font_small = ImageFont.load_default()
 
    y_pos = 0
 
    # ════════════════════════════════════════════════════════════════════════════
    # HEADER SECTION
    # ════════════════════════════════════════════════════════════════════════════
    draw.rectangle([0, 0, width, 140], fill=COLOR_HEADER_BG)
    draw.text((50, 30), "DAILY COLLECTIONS UPDATE", fill=COLOR_HEADER_TEXT, font=font_title)
    draw.text((50, 90), f"PAN INDIA | {report_date}", fill=COLOR_HEADER_TEXT, font=font_subtitle)
    y_pos = 180
 
    # ════════════════════════════════════════════════════════════════════════════
    # SECTION 1: Zone Efficiency %
    # ════════════════════════════════════════════════════════════════════════════
    # Section header
    draw.rectangle([30, y_pos, width - 30, y_pos + 50], fill=COLOR_SECTION_BG)
    draw.text((50, y_pos + 12), "1. Zone Efficiency %", fill=COLOR_SECTION_TEXT, font=font_section)
    y_pos += 70
 
    # Table header
    headers = ["Bucket", "Today", "Yesterday", "LMTD (MAY-26)", "AOD Flow (GA Crs.)"]
    col_widths = [200, 180, 180, 200, 250]
    col_x = [50, 250, 430, 610, 810]
 
    # Header background
    draw.rectangle([30, y_pos, width - 30, y_pos + 50], fill=COLOR_GRID_HEADER_BG)
    for i, header in enumerate(headers):
        draw.text((col_x[i] + 10, y_pos + 15), header, fill=COLOR_GRID_HEADER_TEXT, font=font_header)
    # Draw header border
    draw.line([30, y_pos + 50, width - 30, y_pos + 50], fill=COLOR_GRID_BORDER, width=2)
    y_pos += 50
 
    # Table rows
    buckets_s1 = [
        ("Fresh", 'fresh_eff', 'fresh_lmtd', 'fresh_flow'),
        ("1–29", '129_eff', '129_lmtd', '129_flow'),
        ("1–29 Norm%", 'norm_eff', 'norm_lmtd', None),
        ("30-59", '3059_eff', '3059_lmtd', '3059_flow'),
        ("60-89 (S3 Concern)", 's3_eff', 's3_lmtd', 's3_flow'),
    ]
 
    row_height = 45
    for idx, (label, eff_k, lmtd_k, flow_k) in enumerate(buckets_s1):
        # Alternate row background
        if idx % 2 == 0:
            draw.rectangle([30, y_pos, width - 30, y_pos + row_height], fill=COLOR_GRID_ROW_ALT)
        # Draw vertical lines
        for x in [250, 430, 610, 810, width - 30]:
            draw.line([x, y_pos, x, y_pos + row_height], fill=COLOR_GRID_BORDER, width=1)
 
        t_eff_raw = pi_t.get(eff_k)
        t_lmtd_raw = pi_t.get(lmtd_k)
        
        t_eff = fmt_pct(t_eff_raw)
        y_eff = fmt_pct(pi_y.get(eff_k))
        t_lmtd = fmt_pct(t_lmtd_raw)
        t_flow = fmt_num(pi_t.get(flow_k)) if flow_k and pi_t.get(flow_k) is not None else "—"
 
        draw.text((col_x[0] + 10, y_pos + 12), label, fill=COLOR_TEXT, font=font_body)
        draw.text((col_x[1] + 10, y_pos + 12), t_eff, fill=COLOR_TEXT, font=font_body)
        draw.text((col_x[2] + 10, y_pos + 12), y_eff, fill=COLOR_TEXT_SECONDARY, font=font_body)
        draw.text((col_x[3] + 10, y_pos + 12), t_lmtd, fill=COLOR_TEXT_SECONDARY, font=font_body)
        draw.text((col_x[4] + 10, y_pos + 12), t_flow, fill=COLOR_SUBZONE, font=font_body)
        
        # Add dynamic colored arrows based on comparison
        if t_eff_raw is not None and t_lmtd_raw is not None:
            def get_w(txt):
                try: return draw.textlength(txt, font=font_body)
                except:
                    try: return font_body.getlength(txt)
                    except: return len(txt) * 8
            w_eff = get_w(t_eff)
            w_lmtd = get_w(t_lmtd)
            
            if t_eff_raw > t_lmtd_raw:
                draw.text((col_x[1] + 10 + w_eff + 4, y_pos + 12), "↑", fill="#38a169", font=font_body)
                draw.text((col_x[3] + 10 + w_lmtd + 4, y_pos + 12), "↓", fill="#e53e3e", font=font_body)
            elif t_eff_raw < t_lmtd_raw:
                draw.text((col_x[1] + 10 + w_eff + 4, y_pos + 12), "↓", fill="#e53e3e", font=font_body)
                draw.text((col_x[3] + 10 + w_lmtd + 4, y_pos + 12), "↑", fill="#38a169", font=font_body)
 
        y_pos += row_height
 
    # Draw bottom border
    draw.line([30, y_pos, width - 30, y_pos], fill=COLOR_GRID_BORDER, width=2)
    y_pos += 50
 
    # ════════════════════════════════════════════════════════════════════════════
    # SECTION 2: Bottom Sub-Zones | Efficiency %
    # ════════════════════════════════════════════════════════════════════════════
    draw.rectangle([30, y_pos, width - 30, y_pos + 50], fill=COLOR_SECTION_BG)
    draw.text((50, y_pos + 12), "2. Bottom Sub-Zones | Efficiency %", fill=COLOR_SECTION_TEXT, font=font_section)
    y_pos += 70
 
    # Table header
    headers2 = ["Bucket", "Bottom 1", "Eff %", "Bottom 2", "Eff %"]
    col_widths2 = [200, 200, 150, 200, 150]
    col_x2 = [50, 250, 450, 600, 800]
 
    draw.rectangle([30, y_pos, width - 30, y_pos + 50], fill=COLOR_GRID_HEADER_BG)
    for i, header in enumerate(headers2):
        draw.text((col_x2[i] + 10, y_pos + 15), header, fill=COLOR_GRID_HEADER_TEXT, font=font_header)
    draw.line([30, y_pos + 50, width - 30, y_pos + 50], fill=COLOR_GRID_BORDER, width=2)
    y_pos += 50
 
    # Table rows
    buckets_s2 = [
        ("Fresh", 'fresh_eff'),
        ("1-29 (S2 Concern)", '129_eff'),
        ("1-29 Norm", 'norm_eff'),
        ("30-59", '3059_eff'),
        ("60-89 (S3 Concern)", 's3_eff'),
    ]
 
    for idx, (label, eff_k) in enumerate(buckets_s2):
        if idx % 2 == 0:
            draw.rectangle([30, y_pos, width - 30, y_pos + row_height], fill=COLOR_GRID_ROW_ALT)
        for x in [250, 450, 600, 800, width - 30]:
            draw.line([x, y_pos, x, y_pos + row_height], fill=COLOR_GRID_BORDER, width=1)
 
        b = bottom2_eff(today_m, eff_k)
        b1n = b[0][0] if len(b) > 0 else "—"
        b1v = fmt_pct(b[0][1]) if len(b) > 0 else "—"
        b2n = b[1][0] if len(b) > 1 else "—"
        b2v = fmt_pct(b[1][1]) if len(b) > 1 else "—"
 
        draw.text((col_x2[0] + 10, y_pos + 12), label, fill=COLOR_TEXT, font=font_body)
        draw.text((col_x2[1] + 10, y_pos + 12), b1n, fill=COLOR_SUBZONE, font=font_body)
        draw.text((col_x2[2] + 10, y_pos + 12), b1v, fill=COLOR_TEXT, font=font_body)
        draw.text((col_x2[3] + 10, y_pos + 12), b2n, fill=COLOR_SUBZONE, font=font_body)
        draw.text((col_x2[4] + 10, y_pos + 12), b2v, fill=COLOR_TEXT_SECONDARY, font=font_body)
 
        y_pos += row_height
 
    draw.line([30, y_pos, width - 30, y_pos], fill=COLOR_GRID_BORDER, width=2)
    y_pos += 50
 
    # ════════════════════════════════════════════════════════════════════════════
    # SECTION 3: Bottom Sub-Zones | AOD Flow Value
    # ════════════════════════════════════════════════════════════════════════════
    draw.rectangle([30, y_pos, width - 30, y_pos + 50], fill=COLOR_SECTION_BG)
    draw.text((50, y_pos + 12), "3. Bottom Sub-Zones | AOD Flow Value (Crs.)", fill=COLOR_SECTION_TEXT, font=font_section)
    y_pos += 70
 
    # Table header
    headers3 = ["Bucket", "Bottom 1", "Flow Value", "Bottom 2", "Flow Value"]
    col_x3 = [50, 250, 450, 600, 800]
 
    draw.rectangle([30, y_pos, width - 30, y_pos + 50], fill=COLOR_GRID_HEADER_BG)
    for i, header in enumerate(headers3):
        draw.text((col_x3[i] + 10, y_pos + 15), header, fill=COLOR_GRID_HEADER_TEXT, font=font_header)
    draw.line([30, y_pos + 50, width - 30, y_pos + 50], fill=COLOR_GRID_BORDER, width=2)
    y_pos += 50
 
    # Table rows
    buckets_s3 = [
        ("Fresh", 'fresh_flow'),
        ("1-29 (S2 Concern)", '129_flow'),
        ("30-59", '3059_flow'),
        ("60-89 (S3 Concern)", 's3_flow'),
    ]
 
    for idx, (label, flow_k) in enumerate(buckets_s3):
        if idx % 2 == 0:
            draw.rectangle([30, y_pos, width - 30, y_pos + row_height], fill=COLOR_GRID_ROW_ALT)
        for x in [250, 450, 600, 800, width - 30]:
            draw.line([x, y_pos, x, y_pos + row_height], fill=COLOR_GRID_BORDER, width=1)
 
        b = bottom2_flow(today_m, flow_k)
        b1n = b[0][0] if len(b) > 0 else "—"
        b1v = fmt_num(b[0][1]) if len(b) > 0 else "—"
        b2n = b[1][0] if len(b) > 1 else "—"
        b2v = fmt_num(b[1][1]) if len(b) > 1 else "—"
 
        draw.text((col_x3[0] + 10, y_pos + 12), label, fill=COLOR_TEXT, font=font_body)
        draw.text((col_x3[1] + 10, y_pos + 12), b1n, fill=COLOR_SUBZONE, font=font_body)
        draw.text((col_x3[2] + 10, y_pos + 12), b1v, fill=COLOR_TEXT, font=font_body)
        draw.text((col_x3[3] + 10, y_pos + 12), b2n, fill=COLOR_SUBZONE, font=font_body)
        draw.text((col_x3[4] + 10, y_pos + 12), b2v, fill=COLOR_TEXT_SECONDARY, font=font_body)
 
        y_pos += row_height
 
    draw.line([30, y_pos, width - 30, y_pos], fill=COLOR_GRID_BORDER, width=2)
    y_pos += 80
 
    # ════════════════════════════════════════════════════════════════════════════
    # FOOTER
    # ════════════════════════════════════════════════════════════════════════════
    footer_text = f"Generated on {date.today().strftime('%d %b %Y')} | Collections MIS Report | Confidential"
    draw.text((50, y_pos), footer_text, fill=COLOR_TEXT_SECONDARY, font=font_small)
 
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
 
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
            
            t_eff_str = fmt_pct(t_eff)
            t_lmtd_str = fmt_pct(t_lmtd)
            
            if t_eff is not None and t_lmtd is not None:
                if t_eff > t_lmtd:
                    t_eff_str += ' <span style="color: #38a169; font-weight: bold;">↑</span>'
                    t_lmtd_str += ' <span style="color: #e53e3e; font-weight: bold;">↓</span>'
                elif t_eff < t_lmtd:
                    t_eff_str += ' <span style="color: #e53e3e; font-weight: bold;">↓</span>'
                    t_lmtd_str += ' <span style="color: #38a169; font-weight: bold;">↑</span>'

            html += f"""
<tr>
<td class="label">{label}</td>
<td class="val today">{t_eff_str}</td>
<td class="val">{fmt_pct(y_eff)}</td>
<td class="val">{t_lmtd_str}</td>
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
 
  <div class="report-header">
<div>
<div class="title">DAILY COLLECTIONS UPDATE</div>
<div class="subtitle">PAN INDIA — Zone Efficiency Summary</div>
</div>
<div class="badge">📅 {date_str}</div>
</div>
 
  <div class="report-body">
 
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
 
  </div><div class="report-footer">
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
        t_eff_raw = pi_t.get(eff_k)
        t_lmtd_raw = pi_t.get(lmtd_k)
        
        t_eff_str = fmt_pct(t_eff_raw)
        t_lmtd_str = fmt_pct(t_lmtd_raw)
        
        if t_eff_raw is not None and t_lmtd_raw is not None:
            if t_eff_raw > t_lmtd_raw:
                t_eff_str += " ↑"
                t_lmtd_str += " ↓"
            elif t_eff_raw < t_lmtd_raw:
                t_eff_str += " ↓"
                t_lmtd_str += " ↑"

        rows1.append({
            'Bucket':                   label,
            'Today':                    t_eff_str,
            'Yesterday':                fmt_pct(pi_y.get(eff_k)),
            'MAY-26 LMTD':              t_lmtd_str,
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
                    png_file = create_report_image(
                        today_m,
                        yest_m,
                        report_date
                    )
 
                    st.download_button(
                        label="📷 Download Report Image (PNG)",
                        data=png_file,
                        file_name=f"Collections_Update_{report_date}.png",
                        mime="image/png"
                    )
 
                    html_str = build_html_report(today_m, yest_m, report_date)
                    download_button(html_str, f"Collections_Update_{report_date}.html")
 
            except Exception as e:
                st.error(f"Error: {e}")
                st.exception(e)
 
st.divider()
with st.expander("ℹ️ How to use"):
    st.markdown("""
    1. Export the dashboard as **Excel (.xlsx / .xlsb)** or **CSV** — same column layout.
    2. Upload **today's** file on the left, **yesterday's** on the right.
    3. Set the report date and click **Generate Report**.
    4. Download the **Report Image (PNG)** for sharing or the **Report (HTML)** for email/printing.
    """)