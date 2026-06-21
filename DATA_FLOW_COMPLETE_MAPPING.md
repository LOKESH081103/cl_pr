# 📊 DHC Automation — Complete Data Flow & Mapping Guide

## 🎯 High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         4 INPUT FILES (MONTHLY)                              │
└─────────────────────────────────────────────────────────────────────────────┘

    ┌────────────────┐   ┌──────────────────┐   ┌──────────────┐   ┌─────────────┐
    │  DCR.xlsb      │   │ To_be_Disabled   │   │ Employee     │   │ Prior DHC   │
    │                │   │ .xlsb            │   │ Master.xlsx  │   │ Working.xlsx│
    │ Sheet1: 17K    │   │                  │   │              │   │             │
    │ receipts       │   │ - CIF Level      │   │ Mobile       │   │ Look Up     │
    │                │   │   Disable (93K)  │   │ Numbers (19K)│   │ Master (5K) │
    │ Sheet2: 116K   │   │ - Agr Level      │   │              │   │             │
    │ agreement      │   │   Disable (15K)  │   │              │   │             │
    │ master         │   │                  │   │              │   │             │
    └────────────────┘   └──────────────────┘   └──────────────┘   └─────────────┘
           │                      │                     │                  │
           │                      │                     │                  │
           │◄─────────────────────┼─────────────────────┼──────────────────┤
           │                      │                     │                  │
           ▼                      ▼                     ▼                  ▼
    ┌──────────────────────────────────────────────────────────────────────────┐
    │                    DATA TRANSFORMATION LAYER (ETL)                        │
    │                                                                            │
    │  1. Load all 4 sources into pandas DataFrames                            │
    │  2. Apply mappings (VLOOKUP replacements via .merge)                     │
    │  3. Create 11 derived columns for DCR tab                                │
    │  4. Filter for RTGS & compute ageing                                     │
    │  5. Build 5 aggregated summary tables                                    │
    │                                                                            │
    └──────────────────────────────────────────────────────────────────────────┘
           │
           ▼
    ┌────────────────────────────────────────────────────────────┐
    │           5 OUTPUT SUMMARY SHEETS (Excel)                   │
    │                                                              │
    │  1. Receipt made summary     (6-8 rows)                    │
    │  2. RTGS Summary            (45-60 rows)                   │
    │  3. Cash Mode Validat       (0-100 rows)                   │
    │  4. Delay in RCPTING        (45-60 rows)                   │
    │  5. RCPT CXN                (10-50 rows)                   │
    │                                                              │
    └────────────────────────────────────────────────────────────┘
```

---

## 📥 INPUT FILES BREAKDOWN

### **FILE 1: DCR.xlsb (Daily Collection Report)**

#### Sheet1: Individual Receipts (17,256 rows in your file)
```
COLUMNS (73 total):
├── Primary Keys
│   ├── Receipt No
│   ├── AGREEMENTNO (link to agreement master)
│   └── MOBILENO
│
├── Transaction Details
│   ├── TXN DATE IN PL TAB (when customer paid)
│   ├── RECEIPT ENTER DATE (when receipt was entered into system)
│   ├── AMOUNTPAID
│   ├── RECEIPTTYPE (OD, FC, Part Payment, Settlement, Sale/EMD)
│   ├── RECEIPT CAT (OD, OTHER OD, -)
│   └── RECEIPT SOURCE (BBPS, CCP, CCP - Bitly, etc.)
│
├── Payment Method
│   ├── MODEOFPAYMENT (RTGS, AIRTEL, CASH, CHEQUE, DD, ONLINE_PAYMENT)
│   └── STATUS IN TAB (B, C, D, NA, X → maps to Bounced, Cleared, Deposit, Pending, Cxn)
│
├── Geography
│   ├── ZONE NEW (EAST, NORTH, SOUTH, WEST → broad 4-way)
│   ├── Sub Zone (EAST_1, EAST_2, NORTH_1, NORTH_2, NORTH_3, SOUTH_1, SOUTH_2, WEST_1, WEST_2)
│   ├── SUB REGION (state-level: DELHI_1, TAMIL_NADU_5, MUMBAI_3, etc.)
│   ├── MAIN REGION (state: DELHI, TAMIL_NADU, MUMBAI & GOA, etc.)
│   └── BRANCH NAME (individual branch)
│
├── Customer Info
│   ├── PAYERNAME
│   └── (other customer details)
│
└── More columns (total 73, mostly used internally)
```

**KEY POINT**: Sheet1 is the **source of all receipt-level data**. Every row = 1 receipt transaction.

---

#### Sheet2: Agreement Master (116,629 rows)
```
PURPOSE: Lookup table for agreement-level attributes

COLUMNS (4 selected for use):
├── AGREEMENTNO (Primary Key)
├── OPENING_DPD (Days Past Due as of month-start)
├── OPNG_SLAB_TYPE (Slab label: "0 DPD", "1-29", "30-59", "60-89", "90-180", "180+")
└── OPENING_SLAB (Numeric: 0, 1-29, 30-59, etc.)

EXAMPLE ROWS:
   AGREEMENTNO          | OPENING_DPD | OPNG_SLAB_TYPE | OPENING_SLAB
   ─────────────────────┼─────────────┼────────────────┼──────────────
   XCMFDHE00001153262   |      0      |   0 DPD        |      0
   X0HEMHE00004006029   |      0      |   0 DPD        |      0
   HE02GAW00000001984   |     15      |   1-29         |     15
   XCMFCHE00002902671   |    180      |   180+         |    180

USAGE: Merged into DCR Sheet1 by AGREEMENTNO to refresh "Slab" info each month
```

---

### **FILE 2: To_be_Disabled.xlsb (Compliance Lists)**

#### Sheet: "CIF Level Disable" (93,669 rows)
```
PURPOSE: Mark which CIFs (customers) are NOT allowed to pay via cash/Airtel

COLUMNS (2 used):
├── CIF_NO (Customer ID)
└── Status ("Not Required", "To be Disabled", "CIF Level > 1.95 L")

EXAMPLE:
   CIF_NO  | Status
   ────────┼──────────────────────
   452     | Not Required
   821     | To be Disabled
   1200    | CIF Level > 1.95 L

USAGE: 
  - Merged with DCR by CIF to flag "CIF LEVEL" status in output
  - Used in "Cash Mode Validat Summary" to find compliance violations
```

---

#### Sheet: "Agreement Level Disble" (15,839 rows)
```
PURPOSE: Mark which Agreements are NOT allowed to pay via cash/Airtel

COLUMNS (2 used):
├── AGREEMENTNO (Agreement ID)
└── Status ("CIF Level > 1.95 L", "Case Level > 1.95 L", "Product Level > 1.95 L")

EXAMPLE:
   AGREEMENTNO          | Status
   ──────────────────────┼─────────────────────────
   HE01MHE00000036568    | CIF Level > 1.95 L
   X0HEMHE00004006029    | Case Level > 1.95 L
   HE01MHE00000117491    | Product Level > 1.95 L

USAGE:
  - Merged with DCR by AGREEMENTNO to flag "Ag Level cash mode" status
  - Used in "Cash Mode Validat Summary" to find compliance violations
```

---

### **FILE 3: CIFCL_CBSL_List.xlsx (Employee Master)**

```
PURPOSE: List of employee/agent mobile numbers (for agent-vs-customer flag)

COLUMNS (1 used):
└── Mobile Number (string, ~19,048 unique numbers)

EXAMPLE:
   Mobile Number
   ──────────────
   9010295862
   9356861616
   9962688677
   9773177785

USAGE:
  - Converted to Python set for fast lookup
  - Merged with DCR to flag "Mob Num VS Emp Mob Num" column:
    • If MOBILENO is in employee set → TRUE (receipt entered by agent)
    • If MOBILENO is NOT in employee set → FALSE (receipt entered by customer)
```

---

### **FILE 4: DHC_Working_from_Previous_Month.xlsx (Carried-Forward Master)**

```
PURPOSE: Carry forward CIF/Zone/Sub Region mappings from last month
         (avoids re-mapping agreements seen before)

SHEET: "Look Up" (Columns J:N, ~5,236 active rows)

COLUMNS (5 used):
├── AGREEMENTNO (Primary Key)
├── CIF_NO (Customer ID — blank if new agreement)
├── ZONE_NEW (EAST, NORTH, SOUTH, WEST — broad zone)
├── SUB_REGION (state-level: DELHI_1, TAMIL_NADU_5, etc.)
└── OPENING_SLAB (Numeric slab from prior month)

EXAMPLE:
   AGREEMENTNO          | CIF_NO  | ZONE_NEW | SUB_REGION      | OPENING_SLAB
   ──────────────────────┼─────────┼──────────┼─────────────────┼──────────────
   XCMFDHE00001153262    | 722077  | NORTH    | DELHI_4         | 0
   XCMFDHE00001178793    | 4000548 | NORTH    | DELHI_3         | 0
   HE02GAW00000001984    | 6201883 | WEST     | MADHYA_PRADESH_2| 15

USAGE:
  - Merged with this month's DCR to carry forward CIF/Zone for known agreements
  - NEW agreements (not in this file) = "NEEDS_CIF_MAPPING" = TRUE
  - Next month, this file becomes the input "Previous DHC Working"
```

---

## 🔄 TRANSFORMATION LOGIC (ETL)

### **STEP 1: Load All Data**

```python
# Load DCR
receipts (Sheet1)      → 17,256 rows × 73 columns
dcr_master (Sheet2)    → 116,629 rows × 4 columns (AGREEMENTNO lookup)

# Load compliance
cif_disable            → 93,669 rows × 2 columns
agr_disable            → 15,839 rows × 2 columns

# Load employee
mobiles                → 19,048 unique mobile numbers (set)

# Load prior master
prior_master           → 5,236 rows × 5 columns
```

---

### **STEP 2: Build Lookup Master**

```
Purpose: Create refreshed AGREEMENTNO → CIF/Zone/Sub Region/Slab mapping

INPUT:
  prior_master (5,236 known agreements)  +  dcr_master (116,629 all agreements)

LOGIC:
  For EVERY agreement in THIS MONTH's DCR (116,629 rows):
    ├─ If AGREEMENTNO found in prior_master
    │  └─ KEEP: CIF_NO, ZONE_NEW, SUB_REGION from prior month
    │
    ├─ REFRESH for EVERYONE:
    │  └─ OPENING_SLAB, OPENING_SLAB_LABEL from this month's DCR Sheet2
    │
    └─ If AGREEMENTNO NOT found in prior_master
       └─ FLAG: NEEDS_CIF_MAPPING = TRUE ⚠️

OUTPUT: lookup_master (116,629 rows × 7 columns)
  ├── AGREEMENTNO
  ├── CIF_NO (blank for 111,393 new agreements ⚠️)
  ├── ZONE_NEW (blank for 111,393 new agreements ⚠️)
  ├── SUB_REGION (blank for 111,393 new agreements ⚠️)
  ├── OPENING_SLAB_LABEL (refreshed)
  ├── OPENING_SLAB (refreshed)
  └── NEEDS_CIF_MAPPING (TRUE/FALSE flag)

KEY: 111,393 agreements are BRAND NEW this month — CIF mapping must be manual
```

---

### **STEP 3: Build DCR Tab (Derived Columns)**

```
Starting Point: receipts (17,256 rows × 73 columns)

Merge #1: LEFT-JOIN receipts + lookup_master
  ├─ ON: AGREEMENTNO
  └─ ADD: CIF_NO, ZONE_NEW, SUB_REGION, OPENING_SLAB, NEEDS_CIF_MAPPING

Merge #2: LEFT-JOIN + agr_disable
  ├─ ON: AGREEMENTNO
  └─ ADD: "Ag Level cash mode" (Agreement-level disable status)

Merge #3: LEFT-JOIN + cif_disable
  ├─ ON: CIF_NO
  └─ ADD: "CIF LEVEL" (CIF-level disable status)

CREATE 11 DERIVED COLUMNS:

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 1: "CIF"                                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     CIF_NO from lookup_master merge                                 │
│ FORMULA:    CIF = CIF_NO                                                    │
│ VALUES:     722077, 4000548, 6201883, ... (or blank for new agreements)     │
│ PURPOSE:    Unique customer identifier                                      │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 2: "Unique Mob number"                                               │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     MOBILENO from DCR Sheet1                                        │
│ FORMULA:    COUNT(MOBILENO) partitioned by MOBILENO                         │
│             = How many times does THIS mobile number appear in full DCR?    │
│ VALUES:     1, 2, 5, 15, ... (receipt count per mobile)                    │
│ PURPOSE:    Flag if a mobile appears many times (suspicious/active)         │
│ EXAMPLE:    Mobile 9010295862 used in 3 receipts → value = 3               │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 3: "Mob Num VS Emp Mob Num"                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     MOBILENO (DCR) vs mobiles set (Employee Master)                 │
│ FORMULA:    IF MOBILENO IN employee_mobiles_set THEN TRUE ELSE FALSE        │
│ VALUES:     TRUE or FALSE                                                   │
│ PURPOSE:    Flag if receipt was entered on agent's phone vs customer's      │
│ EXAMPLE:                                                                    │
│   Receipt 1: MOBILENO = 9010295862 (IN employee set) → TRUE                │
│   Receipt 2: MOBILENO = 9999999999 (NOT in employee set) → FALSE           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 4: "Mode"                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     MODEOFPAYMENT from DCR Sheet1                                   │
│ FORMULA:    MAP(MODEOFPAYMENT, {                                            │
│               'RTGS' → 'RTGS',                                              │
│               'AIRTEL'/'CASH' → 'AIRTEL / CASH',                            │
│               'CHEQUE'/'DD' → 'CHQ / DD',                                   │
│               'ONLINE_PAYMENT' → 'ONLINE_PAYMENT'                           │
│             })                                                              │
│ VALUES:     RTGS, AIRTEL / CASH, CHQ / DD, ONLINE_PAYMENT                  │
│ PURPOSE:    Normalized payment mode for reporting                           │
│ SOURCE TAB: Static mapping table (MODE_MAP dict in etl.py)                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 5: "Status"                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     STATUS IN TAB from DCR Sheet1                                   │
│ FORMULA:    MAP(STATUS IN TAB, {                                            │
│               'B' → 'Bounced',                                              │
│               'C' → 'Cleared',                                              │
│               'D' → 'Deposit',                                              │
│               'NA' → 'Pending',                                             │
│               'X' → 'Cxn'  (Cancellation)                                   │
│             })                                                              │
│ VALUES:     Bounced, Cleared, Deposit, Pending, Cxn                        │
│ PURPOSE:    Expanded status labels for reporting                            │
│ SOURCE TAB: Static mapping table (STATUS_MAP dict in etl.py)                │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 6: "Receipt Source"                                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     RECEIPTSOURCE from DCR Sheet1                                   │
│ FORMULA:    MAP(RECEIPTSOURCE, {                                            │
│               'BBPS' → 'BBPS',                                              │
│               'CCP'/'CCP - QR'/'CCP - Bitly' → normalized,                  │
│               'CHOLAONE DIRECT' → 'CHOLAONE DIRECT'                         │
│             })                                                              │
│ VALUES:     BBPS, CCP - QR, CCP - Bitly, CHOLAONE DIRECT, ...              │
│ PURPOSE:    Channel where receipt was submitted (online portal, app, etc.)  │
│ SOURCE TAB: Static mapping table (RECEIPT_SOURCE_MAP dict in etl.py)        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 7: "Zone"                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     ZONE NEW from DCR Sheet1                                        │
│ FORMULA:    Zone = ZONE NEW                                                 │
│ VALUES:     EAST, NORTH, SOUTH, WEST (broad 4-way zones)                   │
│ PURPOSE:    Geographic grouping (highest level)                             │
│ NOTE:       RTGS/Delay summaries actually use SUB ZONE (EAST_1, NORTH_2...) │
│             but this column stores the broad zone for reference             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 8: "Sub Region"                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     SUB REGION from DCR Sheet1                                      │
│ FORMULA:    Sub Region = SUB REGION                                         │
│ VALUES:     DELHI_1, DELHI_2, TAMIL_NADU_5, MUMBAI_3, BIHAR, ...           │
│ PURPOSE:    State-level geographic grouping                                 │
│ NOTE:       Used in "Cash Mode Validat Summary" pivot rows                  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 9: "Slab"                                                            │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     OPENING_SLAB from DCR Sheet2 (refreshed via lookup_master)      │
│ FORMULA:    Slab = OPENING_SLAB (refreshed this month)                      │
│ VALUES:     0, 1-29, 30-59, 60-89, 90-180, 180+, Fresh, ...                │
│ PURPOSE:    Aging bucket for agreement (DPD — Days Past Due)                │
│ NOTE:       This is the SLAB column already in DCR Sheet1; we don't rename  │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 10: "Ag Level cash mode"                                             │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     Agreement Level Disable list (To_be_Disabled.xlsb Sheet2)       │
│ FORMULA:    LEFT-JOIN DCR + agr_disable ON AGREEMENTNO                      │
│ VALUES:     "CIF Level > 1.95 L", "Case Level > 1.95 L", "Product..." or   │
│             (blank if not on disable list)                                  │
│ PURPOSE:    Flag: This agreement NOT allowed to pay via cash/Airtel        │
│ COMPLIANCE: Used to identify violations in "Cash Mode Validat Summary"      │
│ EXAMPLE:                                                                    │
│   Agreement HE01MHE00000036568:                                            │
│     - Is on disable list with status "CIF Level > 1.95 L"                  │
│     - If it paid via CASH → VIOLATION                                      │
│     - If it paid via ONLINE → OK                                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN 11: "CIF LEVEL"                                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     CIF Level Disable list (To_be_Disabled.xlsb Sheet1)             │
│ FORMULA:    LEFT-JOIN DCR + cif_disable ON CIF_NO                           │
│ VALUES:     "Not Required", "To be Disabled", "CIF Level > 1.95 L" or      │
│             (blank if CIF unknown or not on disable list)                   │
│ PURPOSE:    Flag: This CIF (customer) NOT allowed to pay via cash/Airtel   │
│ COMPLIANCE: Used to identify violations in "Cash Mode Validat Summary"      │
│ EXAMPLE:                                                                    │
│   CIF 722077:                                                              │
│     - Is on disable list with status "To be Disabled"                      │
│     - If it paid via AIRTEL → VIOLATION                                    │
│     - If it paid via RTGS → OK                                             │
└─────────────────────────────────────────────────────────────────────────────┘

OUTPUT: dcr_tab (17,256 rows × 87 columns)
  └─ Original 73 columns + 11 new derived + 3 carry-forward columns
```

---

### **STEP 4: Build RTGS Tab**

```
Starting Point: dcr_tab (17,256 rows × 87 columns)

FILTER: Keep only rows where MODEOFPAYMENT = 'RTGS'
  └─ Result: rtgs_tab (1,879 rows × 90 columns)

CREATE 3 NEW COLUMNS (RTGS-specific):

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN A: "Ageing"                                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     TXN DATE IN PL TAB, RECEIPT ENTER DATE (both from DCR Sheet1)   │
│ FORMULA:    Ageing (days) = RECEIPT ENTER DATE - TXN DATE IN PL TAB         │
│ VALUES:     0, 1, 2, 5, 15, 30, 180, ... (number of days)                  │
│ PURPOSE:    How long between transaction & receipt entry (delay)            │
│ EXAMPLE:                                                                    │
│   TXN DATE: 2026-06-01                                                      │
│   ENTER DATE: 2026-06-05                                                    │
│   Ageing = 4 days                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN B: "TAT" (Turn-Around Time Bucket)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     Ageing column (derived above)                                   │
│ FORMULA:    IF Ageing < 4 days THEN "< 4 Days"                             │
│             ELSE IF Ageing < 11 days THEN "5 - 10 Days"                    │
│             ELSE "> 10 Days"                                                │
│ VALUES:     < 4 Days, 5 - 10 Days, > 10 Days                               │
│ PURPOSE:    Categorize ageing into reporting buckets                        │
│ EXAMPLE:                                                                    │
│   Ageing = 2 days → TAT = "< 4 Days"                                       │
│   Ageing = 8 days → TAT = "5 - 10 Days"                                    │
│   Ageing = 30 days → TAT = "> 10 Days"                                     │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│ COLUMN C: "Receipt Type"                                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│ SOURCE:     RECEIPTTYPE, RECEIPT CAT (both from DCR Sheet1)                 │
│ FORMULA:    First, try to map RECEIPTTYPE:                                  │
│               IF RECEIPTTYPE IN ("FC", "Part Payment", "Settlement",       │
│                                   "Sale/EMD receipt") THEN map to standard │
│             If RECEIPTTYPE not mapped, fallback to RECEIPT CAT:             │
│               IF RECEIPT CAT = "OD" THEN "OD"                               │
│               IF RECEIPT CAT = "OTHER OD" THEN "OTHER OD"                   │
│                                                                              │
│             MAPPING DICT (RECEIPT_TYPE_MAP):                                │
│               "OD" → "OD" (Interest/Charges)                                │
│               "FC" → "Settlement" (Foreclosure)                             │
│               "Part Payment" → "Part Payment"                               │
│               "Settlement" → "Settlement"                                   │
│               "Sale/EMD receipt" → "Settlement"                             │
│                                                                              │
│ VALUES:     OD, Settlement, Part Payment, OTHER OD                          │
│ PURPOSE:    Categorize receipt type for KPI tracking                        │
│ EXAMPLE:                                                                    │
│   RECEIPTTYPE = "FC" → Receipt Type = "Settlement"                         │
│   RECEIPTTYPE = "OD" → Receipt Type = "OD"                                 │
│   RECEIPT_CAT = "OTHER OD" (no RECEIPTTYPE) → Receipt Type = "OTHER OD"    │
└─────────────────────────────────────────────────────────────────────────────┘

OUTPUT: rtgs_tab (1,879 rows × 90 columns)
  └─ All 87 from dcr_tab + 3 new RTGS columns (Ageing, TAT, Receipt Type)
```

---

## 📊 OUTPUT SUMMARY SHEETS (5 tables)

### **SUMMARY 1: Receipt made summary**

```
BUILT FROM: dcr_tab (17,256 rows — FULL MONTH, all modes)

STRUCTURE: 2 Side-by-Side Pivot Tables

┌─────────────────────────────────────────────────────────────────────┐
│ LEFT PIVOT: Updated/Pending Receipts                                │
├─────────────────────────────────────────────────────────────────────┤
│ ROW GROUPS:                                                         │
│  ├─ UPDATED (receipts with RECEIPT STATUS = "Updated")             │
│  │  ├─ AIRTEL / CASH                                               │
│  │  ├─ CHQ / DD                                                    │
│  │  ├─ ONLINE_PAYMENT                                              │
│  │  └─ RTGS                                                        │
│  │                                                                  │
│  └─ PENDING (receipts with RECEIPT STATUS = "Updation Pending")    │
│     ├─ AIRTEL / CASH                                               │
│     ├─ CHQ / DD                                                    │
│     ├─ ONLINE_PAYMENT                                              │
│     └─ RTGS                                                        │
│                                                                     │
│ COLUMN HEADERS:  Cleared  |  Deposit  |  Pending  |  GRAND TOTAL  │
│                                                                     │
│ VALUES: COUNT of receipts in each cell                             │
│                                                                     │
│ EXAMPLE:                                                            │
│   UPDATED/AIRTEL / CASH/Cleared = 5000 (receipts)                 │
│   UPDATED/RTGS/Cleared = 500 (receipts)                           │
│   PENDING/AIRTEL / CASH/Pending = 100 (receipts)                  │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│ RIGHT PIVOT: Updated/Bounced or Cancelled                           │
├─────────────────────────────────────────────────────────────────────┤
│ ROW GROUPS:                                                         │
│  ├─ UPDATED (receipts with RECEIPT STATUS = "Updated")             │
│  │  ├─ AIRTEL / CASH                                               │
│  │  ├─ CHQ / DD                                                    │
│  │  ├─ ONLINE_PAYMENT                                              │
│  │  └─ RTGS                                                        │
│  │                                                                  │
│  └─ BOUNCED/CANCELLED (RECEIPT STATUS = "Bounced-or-Cancelled")   │
│     ├─ AIRTEL / CASH                                               │
│     ├─ CHQ / DD                                                    │
│     ├─ ONLINE_PAYMENT                                              │
│     └─ RTGS                                                        │
│                                                                     │
│ COLUMN HEADERS:  Cleared  |  Deposit  |  Bounced  |  Cxn  |  TOTAL│
│                                                                     │
│ VALUES: COUNT of receipts in each cell                             │
│                                                                     │
│ EXAMPLE:                                                            │
│   UPDATED/AIRTEL / CASH/Bounced = 15 (bad receipts)               │
│   BOUNCED/RTGS/Cxn = 5 (cancelled receipts)                       │
└─────────────────────────────────────────────────────────────────────┘

CALCULATION:
  For each combination of (RECEIPT STATUS, Mode):
    → COUNT receipts WHERE Status = {Cleared, Deposit, Bounced, Pending, Cxn}
    → Sum to get GRAND TOTAL per mode
    → Sum to get GRAND TOTAL per status group
    → Sum all for OVERALL GRAND TOTAL
```

---

### **SUMMARY 2: RTGS Summary**

```
BUILT FROM: rtgs_tab (1,879 rows — RTGS MODE ONLY)

STRUCTURE: 2 Sections (Side-by-Side)

┌──────────────────────────────────────────────────────────────────────┐
│ SECTION A: Online Payment Sources (Left Mini-Block)                  │
├──────────────────────────────────────────────────────────────────────┤
│ ROWS: Each receipt source (BBPS, CCP - QR, CCP - Bitly, etc.)       │
│ COLUMN: Receipt Count (number of online receipts per source)        │
│ TOTAL: Sum of all online payments this month                        │
│                                                                      │
│ DATA PULLED FROM: Full dcr_tab (not just RTGS)                      │
│ FILTER: Mode = "ONLINE_PAYMENT"                                     │
│ AGGREGATION: COUNT receipts GROUP BY RECEIPTSOURCE                  │
│                                                                      │
│ EXAMPLE:                                                             │
│   BBPS → 3,050 receipts                                             │
│   CCP - QR → 2,392 receipts                                         │
│   CCP - Bitly → 2,275 receipts                                      │
│   GRAND TOTAL: 11,942 online receipts                               │
└──────────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────────┐
│ SECTION B: Zone × Receipt Type × TAT Matrix (Main Block)             │
├──────────────────────────────────────────────────────────────────────┤
│ ROWS: 9 Sub Zones + Receipt Types (4 per zone) + Subtotals          │
│                                                                      │
│ SUB ZONES (9):                                                       │
│   EAST_1, EAST_2, NORTH_1, NORTH_2, NORTH_3, SOUTH_1, SOUTH_2,    │
│   WEST_1, WEST_2                                                    │
│                                                                      │
│ FOR EACH ZONE:                                                       │
│   ├─ [Zone Name] SUBTOTAL                                           │
│   ├─   ├─ OD (EMI Interest/Charges)                                 │
│   │   ├─ Settlement (Foreclosure)                                   │
│   │   ├─ Part Payment                                               │
│   │   └─ OTHER OD (Other charges)                                   │
│   │                                                                 │
│   └─ [Zone Name] SUBTOTAL row                                      │
│                                                                      │
│ COLUMNS (3 TAT buckets × 2 metrics):                                │
│                                                                      │
│   < 4 Days          | 5 - 10 Days       | > 10 Days                │
│   Count | Value(Cr) | Count | Value(Cr) | Count | Value(Cr) | TOTAL│
│   ──────┼──────────┼────────┼──────────┼────────┼───────────┼─────│
│                                                                      │
│ VALUE = Sum of AMOUNTPAID / 10,000,000 (in Crores)                 │
│ COUNT = Number of receipts in bucket                                │
│                                                                      │
│ EXAMPLE (for NORTH_1 zone):                                        │
│   NORTH_1 Subtotal:                                                │
│     < 4 Days: Count=50, Value=2.50 Cr                              │
│     5-10 Days: Count=20, Value=1.20 Cr                             │
│     > 10 Days: Count=5, Value=0.30 Cr                              │
│                                                                      │
│   NORTH_1/OD (Receipt Type breakdown):                              │
│     < 4 Days: Count=40, Value=2.00 Cr                              │
│     5-10 Days: Count=15, Value=0.90 Cr                             │
│     > 10 Days: Count=3, Value=0.20 Cr                              │
│                                                                      │
│ GRAND TOTAL: Sum of all zones, receipt types, TAT buckets          │
└──────────────────────────────────────────────────────────────────────┘

CALCULATION LOGIC:
  1. Filter rtgs_tab to keep only RTGS-mode receipts (already filtered)
  2. For each Sub Zone:
     a. Calculate subtotal across all Receipt Types & TAT buckets
     b. For each Receipt Type within that zone:
        - Count receipts & sum amounts in each TAT bucket
  3. Group by TAT bucket:
     - < 4 Days: Ageing < 4
     - 5-10 Days: 4 ≤ Ageing < 11
     - > 10 Days: Ageing ≥ 11
  4. Roll up to grand total
```

---

### **SUMMARY 3: Cash Mode Validat Summary**

```
BUILT FROM: dcr_tab (17,256 rows — FULL MONTH)

PURPOSE: Compliance Check — Find customers on DISABLE LIST who paid via CASH

FILTER LOGIC:
  Keep rows WHERE:
    └─ Mode = "AIRTEL / CASH"  AND
       └─ (Ag Level cash mode IS NOT NULL  OR  CIF LEVEL IS NOT NULL)

RESULT: 10–100 rows typically (violations only)

STRUCTURE: CIF × Zone × Sub Region × Slab × Daily Breakdown

ROWS: Each unique CIF found in violations

COLUMNS:
  ├─ CIF (Customer ID from lookup_master)
  ├─ Zone2 (ZONE NEW from lookup_master)
  ├─ Sub Region2 (SUB REGION from lookup_master)
  ├─ Slab (OPENING_SLAB from lookup_master)
  └─ Date columns (one per date with violation, e.g., 2026-06-01, 2026-06-02, ...)
  └─ Grand Total (sum across all dates)

VALUES IN CELLS: Amount paid (in rupees)

EXAMPLE:
  CIF      | Zone  | Sub Region    | Slab     | 2026-06-01 | 2026-06-02 | Grand Total
  ─────────┼───────┼───────────────┼──────────┼────────────┼────────────┼────────────
  8818578  | SOUTH | TELANGANA_2   | 60-89    |      —     |      —     | 297,000
  12416558 | WEST  | MADHYA_PRADESH| 60-89    |      —     |      —     | 295,000
  9612002  | WEST  | MUMBAI_3      | 30-59    |  94,337    |  92,405    | 259,049

INTERPRETATION:
  "CIF 8818578 is on the disable list (Slab 60-89, high risk).
   It paid ₹297,000 via Cash/Airtel despite restrictions.
   VIOLATION — follow up needed."

CALCULATION:
  1. Find all receipts with Mode = "AIRTEL / CASH"
  2. Filter to those with Ag Level cash mode or CIF LEVEL status (disabled)
  3. PIVOT_TABLE:
     └─ INDEX: [CIF, Zone, Sub Region, Slab]
     └─ COLUMNS: RECEIPT ENTER DATE (normalized to date only)
     └─ VALUES: SUM(AMOUNTPAID)
  4. Add Grand Total column = SUM across all date columns
```

---

### **SUMMARY 4: Delay in RCPTING Summary**

```
BUILT FROM: dcr_tab (17,256 rows — FULL MONTH, all modes)

PURPOSE: Identify receipts with aging delays (how long to enter into system)

STRUCTURE: Same as RTGS Summary (Zone × Receipt Type × TAT)
          BUT uses FULL month data (not RTGS-filtered)

DIFFERENCE FROM RTGS SUMMARY:
  ├─ RTGS Summary = RTGS receipts only (1,879 rows)
  └─ Delay Summary = ALL receipts (17,256 rows)
                    Shows aging for cash/check/online too

COLUMNS: Same 3 TAT buckets × 2 metrics (Count, Value Cr)

EXAMPLE INTERPRETATION:
  "NORTH_1 zone, OD receipts, > 10 days old = 5 receipts worth ₹0.30 Cr
   These are old receipts not yet entered — slowest processing."

TAT BUCKETS (based on Ageing):
  < 4 Days: Receipts processed within 3 days (ideal)
  5-10 Days: Receipts processed in 1–2 weeks (acceptable)
  > 10 Days: Receipts processed > 10 days old (delay issue)

CALCULATION (same as RTGS):
  1. For each receipt: Ageing = RECEIPT ENTER DATE - TXN DATE
  2. Bucket Ageing into TAT bucket
  3. Group by Zone, Receipt Type, TAT
  4. Count receipts & sum amounts per bucket
  5. Calculate subtotals & grand total
```

---

### **SUMMARY 5: RCPT CXN (Cancelled Receipts)**

```
BUILT FROM: dcr_tab (17,256 rows — FULL MONTH)

PURPOSE: Register of cancelled receipts (for manual review & remarks)

FILTER: Keep rows WHERE Status = "Cxn" (Cancellation)

RESULT: 10–50 rows typically (cancelled receipts)

STRUCTURE: Flat table (one row per cancelled receipt)

COLUMNS (11):
  ├─ ReceiptNo (Receipt ID from DCR)
  ├─ ReceiptDate (RECEIPT ENTER DATE formatted as DD/MM/YYYY)
  ├─ Amount (AMOUNTPAID)
  ├─ ReceiptStatus (always = "Cancelled")
  ├─ ReceiptType (mapped from RECEIPTTYPE or RECEIPT CAT)
  ├─ PaymentMode (from Mode column)
  ├─ Zone (from Zone column)
  ├─ AgreementNo (from AGREEMENTNO)
  ├─ CustomerName (from PAYERNAME)
  ├─ ReceiptCreatedDate (RECEIPT ENTER DATE formatted as DD/MM/YYYY)
  ├─ Status (always = "Duplicate Receipt")
  └─ Remarks (BLANK — you fill this in manually ⚠️)

EXAMPLE:
  ReceiptNo | ReceiptDate | Amount    | Type        | Mode | Zone  | Remarks
  ──────────┼─────────────┼───────────┼─────────────┼──────┼───────┼──────────────
  RCP001    | 05/06/2026  | 25,000    | Settlement  | RTGS | NORTH | Duplicate
  RCP002    | 06/06/2026  | 50,000    | OD          | CASH | SOUTH | Customer request
  RCP003    | 07/06/2026  | 15,500    | Part Pmt    | CHQ  | WEST  | Bank error

WHY BLANK REMARKS?
  This is a JUDGMENT CALL — why was this receipt cancelled?
  ├─ Duplicate (customer paid twice)
  ├─ Customer request (wrong amount, wrong customer)
  ├─ Bank error (cheque bounce, RTGS reversal)
  ├─ System correction (data entry error)
  └─ Other reason

Only YOUR MAM can determine the reason — so the Remarks column is left blank
for her to fill in during her review. This is NOT automated.
```

---

## 🗺️ COMPLETE DATA LINEAGE MAP

```
┌────────────────────────────────────────────────────────────────────────────┐
│ SOURCE 1: DCR.xlsb                                                          │
├────────────────────────────────────────────────────────────────────────────┤
│ Sheet1: Raw Receipts (17,256 rows × 73 cols)                               │
│  ├─ Primary: Receipt No, AGREEMENTNO, MOBILENO                            │
│  ├─ Transaction: AMOUNTPAID, MODEOFPAYMENT, STATUS IN TAB, RECEIPTTYPE    │
│  ├─ Dates: TXN DATE, RECEIPT ENTER DATE (→ used for Ageing)               │
│  ├─ Geography: ZONE NEW, Sub Zone, SUB REGION, MAIN REGION, BRANCH NAME   │
│  └─ Source: RECEIPTSOURCE                                                  │
│                                                                             │
│ Sheet2: Agreement Master (116,629 rows × 4 cols)                           │
│  └─ Lookup: AGREEMENTNO → OPENING_DPD, OPNG_SLAB_TYPE, OPENING_SLAB       │
│                                                                             │
│ USAGE:                                                                      │
│  ├─ Sheet1 → Base for dcr_tab (17,256 receipts)                           │
│  ├─ Sheet2 → Refresh Slab for lookup_master (116,629 agreements)          │
│  └─ Sheet1 dates → Compute Ageing & TAT (for RTGS tab)                    │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ SOURCE 2: To_be_Disabled.xlsb                                              │
├────────────────────────────────────────────────────────────────────────────┤
│ Sheet: CIF Level Disable (93,669 rows)                                     │
│  └─ Lookup: CIF_NO → "Not Required" / "To be Disabled" / "CIF Level..."   │
│                                                                             │
│ Sheet: Agreement Level Disble (15,839 rows)                                │
│  └─ Lookup: AGREEMENTNO → "CIF Level..." / "Case Level..." / "Product..." │
│                                                                             │
│ USAGE:                                                                      │
│  ├─ CIF disable → Merged with dcr_tab (add "CIF LEVEL" column)           │
│  ├─ Agreement disable → Merged with dcr_tab (add "Ag Level cash mode")    │
│  └─ Both → Filter "Cash Mode Validat Summary" (show violations)            │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ SOURCE 3: Employee Master .xlsx                                            │
├────────────────────────────────────────────────────────────────────────────┤
│ Sheet1: Mobile Numbers (19,048 unique)                                     │
│  └─ Lookup: Mobile Number → Employee/Agent flag                           │
│                                                                             │
│ USAGE:                                                                      │
│  └─ Convert to Python set → Fast lookup in dcr_tab                        │
│     └─ Add "Mob Num VS Emp Mob Num" column (TRUE if agent, FALSE if cust.)│
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ SOURCE 4: Previous DHC Working.xlsx                                        │
├────────────────────────────────────────────────────────────────────────────┤
│ Look Up sheet, cols J:N (5,236 known agreements)                           │
│  └─ Lookup: AGREEMENTNO → CIF_NO, ZONE_NEW, SUB_REGION, OPENING_SLAB      │
│                                                                             │
│ USAGE:                                                                      │
│  ├─ Merge with DCR Sheet2 → Build lookup_master (116,629 agreements)      │
│  │   ├─ Known agreements (5,236): Carry forward CIF/Zone                  │
│  │   └─ New agreements (111,393): Leave CIF/Zone blank, flag ⚠️            │
│  │                                                                          │
│  └─ Merge with dcr_tab → Add CIF, ZONE_NEW, SUB_REGION, OPENING_SLAB      │
└────────────────────────────────────────────────────────────────────────────┘

                              ↓ TRANSFORMATIONS ↓

┌────────────────────────────────────────────────────────────────────────────┐
│ INTERMEDIATE: lookup_master (116,629 rows × 7 cols)                        │
├────────────────────────────────────────────────────────────────────────────┤
│ PURPOSE: Cumulative agreement master (refreshed each month)                │
│                                                                             │
│ COLS:                                                                       │
│  ├─ AGREEMENTNO (from DCR Sheet2)                                         │
│  ├─ CIF_NO (from prior_master if known, BLANK for 111,393 new)            │
│  ├─ ZONE_NEW (from prior_master if known, BLANK for 111,393 new)          │
│  ├─ SUB_REGION (from prior_master if known, BLANK for 111,393 new)        │
│  ├─ OPENING_SLAB_LABEL (from DCR Sheet2, refreshed)                       │
│  ├─ OPENING_SLAB (from DCR Sheet2, refreshed)                             │
│  └─ NEEDS_CIF_MAPPING (TRUE for 111,393 new, FALSE for 5,236 known)       │
│                                                                             │
│ NEXT: Merged into dcr_tab to enrich receipt-level data with agreement info│
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ INTERMEDIATE: dcr_tab (17,256 rows × 87 cols)                              │
├────────────────────────────────────────────────────────────────────────────┤
│ PURPOSE: Enriched receipt data (all 17K receipts + 11 derived columns)     │
│                                                                             │
│ 73 original + 11 derived + 3 carried-forward = 87 cols:                    │
│  ├─ Original 73 from DCR Sheet1                                            │
│  │                                                                          │
│  ├─ Derived (NEW):                                                         │
│  │  ├─ CIF (from lookup_master)                                           │
│  │  ├─ Unique Mob number (COUNT partitioned)                              │
│  │  ├─ Mob Num VS Emp Mob Num (employee set lookup)                       │
│  │  ├─ Mode (MODEOFPAYMENT mapped)                                        │
│  │  ├─ Status (STATUS IN TAB mapped)                                      │
│  │  ├─ Receipt Source (RECEIPTSOURCE mapped)                              │
│  │  ├─ Zone (from lookup_master)                                          │
│  │  ├─ Sub Region (from lookup_master)                                    │
│  │  ├─ Slab (from lookup_master)                                          │
│  │  ├─ Ag Level cash mode (from agr_disable merge)                        │
│  │  └─ CIF LEVEL (from cif_disable merge)                                 │
│  │                                                                          │
│  └─ Carried forward (for next month):                                      │
│     ├─ CIF_NO                                                              │
│     ├─ NEEDS_CIF_MAPPING                                                   │
│     └─ ZONE_NEW, SUB_REGION                                                │
│                                                                             │
│ USED BY:                                                                    │
│  ├─ Summary 1: Receipt made summary (full 17K receipts)                   │
│  ├─ Summary 3: Cash Mode Validat (filtered to violations)                 │
│  ├─ Summary 4: Delay in RCPTING (full 17K receipts)                       │
│  └─ Summary 5: RCPT CXN (filtered to Status = "Cxn")                      │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ INTERMEDIATE: rtgs_tab (1,879 rows × 90 cols)                              │
├────────────────────────────────────────────────────────────────────────────┤
│ PURPOSE: RTGS-only subset with ageing & TAT metrics                        │
│                                                                             │
│ SOURCE: Filter dcr_tab where MODEOFPAYMENT = 'RTGS'                       │
│                                                                             │
│ 87 (from dcr_tab) + 3 new = 90 cols:                                       │
│  ├─ All 87 from dcr_tab                                                    │
│  ├─ Ageing (RECEIPT ENTER DATE - TXN DATE IN PL TAB, in days)             │
│  ├─ TAT (bucketed Ageing: < 4 Days / 5-10 Days / > 10 Days)               │
│  └─ Receipt Type (RECEIPTTYPE/RECEIPT CAT mapped)                          │
│                                                                             │
│ USED BY:                                                                    │
│  └─ Summary 2: RTGS Summary (with online payment breakdown from dcr_tab)   │
└────────────────────────────────────────────────────────────────────────────┘

                              ↓ AGGREGATIONS ↓

┌────────────────────────────────────────────────────────────────────────────┐
│ OUTPUT 1: Receipt made summary (6-8 rows × 5+ cols)                        │
├────────────────────────────────────────────────────────────────────────────┤
│ SOURCE: dcr_tab (17,256 rows)                                              │
│ LOGIC: PIVOT_TABLE(dcr_tab, index=[RECEIPT STATUS, Mode],                 │
│                            columns=Status,                                 │
│                            values=COUNT)                                   │
│ RESULT: 2 side-by-side tables (Updated/Pending vs Bounced/Cancelled)      │
│ EXPORT: Excel with merged headers, subtotals, formatting                   │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ OUTPUT 2: RTGS Summary (45-60 rows × 10 cols)                              │
├────────────────────────────────────────────────────────────────────────────┤
│ SOURCE: rtgs_tab (1,879 rows) + dcr_tab (online payment sources)           │
│ LOGIC: PIVOT_TABLE(rtgs_tab, index=[Sub Zone, Receipt Type],              │
│                            columns=TAT,                                    │
│                            values=COUNT & SUM(AMOUNTPAID))                 │
│ RESULT: Zone × Receipt Type × TAT matrix with subtotals                    │
│ EXPORT: Excel with online payment mini-block + main matrix                 │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ OUTPUT 3: Cash Mode Validat Summary (0-100 rows × 15+ cols)                │
├────────────────────────────────────────────────────────────────────────────┤
│ SOURCE: dcr_tab (17,256 rows, filtered to violations)                      │
│ FILTER: Mode = "AIRTEL / CASH" AND                                        │
│         (Ag Level cash mode IS NOT NULL OR CIF LEVEL IS NOT NULL)         │
│ LOGIC: PIVOT_TABLE(filtered, index=[CIF, Zone, Sub Region, Slab],         │
│                            columns=RECEIPT ENTER DATE (date only),         │
│                            values=SUM(AMOUNTPAID))                         │
│ RESULT: CIF × Date breakdown of violations                                 │
│ EXPORT: Excel with Grand Total column, daily date columns                  │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ OUTPUT 4: Delay in RCPTING Summary (45-60 rows × 10 cols)                  │
├────────────────────────────────────────────────────────────────────────────┤
│ SOURCE: dcr_tab (17,256 rows — FULL MONTH)                                 │
│ LOGIC: Add Ageing & TAT columns (same as rtgs_tab)                        │
│        PIVOT_TABLE(dcr_tab, index=[Sub Zone, Receipt Type],                │
│                            columns=TAT,                                    │
│                            values=COUNT & SUM(AMOUNTPAID))                 │
│ RESULT: Full-month Zone × Receipt Type × TAT matrix (all modes)            │
│ EXPORT: Excel, same format as RTGS Summary                                 │
│ DIFFERENCE: Includes cash/check, not just RTGS                             │
└────────────────────────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────────────────────────┐
│ OUTPUT 5: RCPT CXN (10-50 rows × 11 cols)                                  │
├────────────────────────────────────────────────────────────────────────────┤
│ SOURCE: dcr_tab (17,256 rows, filtered)                                    │
│ FILTER: Status = "Cxn" (Cancellation)                                     │
│ LOGIC: SELECT [ReceiptNo, ReceiptDate, Amount, Type, Mode, Zone, ...]     │
│        & ADD blank Remarks column for manual input                         │
│ RESULT: Flat table of cancelled receipts ready for review                  │
│ EXPORT: Excel with empty Remarks column                                    │
└────────────────────────────────────────────────────────────────────────────┘
```

---

## 📋 QUICK REFERENCE TABLE

| Data Element | Source | How Mapped | Output Column(s) | Used In |
|---|---|---|---|---|
| Receipt No, Amount, Date | DCR Sheet1 | Direct copy | Receipt No, Amount, ReceiptDate | All outputs |
| AGREEMENTNO | DCR Sheet1 | Direct copy | AGREEMENTNO | All (primary key) |
| MOBILENO | DCR Sheet1 | Direct copy + set lookup | Mob Num VS Emp Mob Num | RCPT CXN |
| MODEOFPAYMENT | DCR Sheet1 | MAP dict | Mode | All (Receipt made, RTGS, Delay, Cash Mode, RCPT CXN) |
| STATUS IN TAB | DCR Sheet1 | MAP dict (B→Bounced, C→Cleared, etc.) | Status | Receipt made, RCPT CXN |
| RECEIPTTYPE | DCR Sheet1 | MAP dict + fallback | Receipt Type | RTGS, Delay, RCPT CXN |
| RECEIPTSOURCE | DCR Sheet1 | MAP dict | Receipt Source | RCPT CXN |
| Sub Zone, SUB REGION | DCR Sheet1 | Direct copy | Zone, Sub Region | All |
| OPENING_SLAB | DCR Sheet2 | VLOOKUP via merge | Slab | Cash Mode Validat, RCPT CXN, lookup_master |
| CIF_NO | Prior DHC Working | Merge (carry-forward) | CIF | Cash Mode Validat, dcr_tab |
| ZONE_NEW | Prior DHC Working | Merge (carry-forward) | Zone | Cash Mode Validat, dcr_tab |
| SUB_REGION | Prior DHC Working | Merge (carry-forward) | Sub Region | Cash Mode Validat, dcr_tab |
| CIF LEVEL Status | To_be_Disabled Sheet1 | Merge on CIF_NO | CIF LEVEL | Cash Mode Validat Summary |
| Ag Level Status | To_be_Disabled Sheet2 | Merge on AGREEMENTNO | Ag Level cash mode | Cash Mode Validat Summary |
| Employee Mobiles | Employee Master | Set lookup | Mob Num VS Emp Mob Num | dcr_tab |
| Ageing (days) | Computed (TXN DATE - ENTER DATE) | Date math | Ageing | RTGS tab, Delay Summary |
| TAT Bucket | Computed (Ageing) | IF-ELSE buckets | TAT | RTGS Summary, Delay Summary |

---

**Print this guide and show your mam! 🎯**

Every column, every mapping, every formula is documented above.
