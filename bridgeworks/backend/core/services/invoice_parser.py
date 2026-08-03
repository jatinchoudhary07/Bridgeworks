"""
invoice_parser.py — Courier Billing Excel Parser
=================================================
Parses Bluedart .xlsb (and future .xlsx) invoice files into a normalised
list of dicts ready for CourierInvoiceLine creation.

Supported couriers:
  - Bluedart (.xlsb)  — CPRODCODE: ACL / APL / AP / AC
  - Future: Delhivery, Ekart (.xlsx)

Business rule:
  All orders are <250g product weight → EXPECTED_SLAB_KG = 0.5
"""
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)

# ─── Business Constraint ────────────────────────────────────────────────────
EXPECTED_SLAB_KG = Decimal('0.5')


# ─── Bluedart column → our field mapping ────────────────────────────────────
BLUEDART_COLUMN_MAP = {
    'CAWBNO':       'awb_number',
    'CCRCRDREF':    'courier_ref',
    'CPRODCODE':    'product_code',
    'CORGAREA':     'origin_area',
    'CDSTAREA':     'dest_area',
    'DESTPINCODE':  'dest_pincode',
    'COMMODITY':    'commodity',
    'NACTWGT':      'actual_weight_kg',
    'NCHRGWT':      'charged_weight_kg',
    'NPCS':         'pieces',
    'NFREIGHT':     'freight',
    'NFSAMT':       'fsc',
    'NCAFAMT':      'caf',
    'NFODCHRG':     'fod_charge',
    'NVALCHGS':     'declared_value_charge',
    'NIDCCHGS':     'idc_charge',
    'NTOTAMOUNT':   'total_billed',
}


def _safe_decimal(val, default=Decimal('0')) -> Decimal:
    """Convert any value to Decimal safely."""
    if val is None:
        return default
    try:
        d = Decimal(str(val))
        return d if d.is_finite() else default
    except (InvalidOperation, ValueError):
        return default


def _safe_str(val) -> str:
    """Convert any value to a clean string."""
    if val is None:
        return ''
    s = str(val).strip()
    # Remove Bluedart's float suffix on numeric fields (e.g. "77708979541.0")
    if s.endswith('.0') and s[:-2].isdigit():
        s = s[:-2]
    return s


def _classify_type(courier_ref: str, awb: str, total_billed: Decimal) -> str:
    """
    Determine shipment type from our internal reference and total sign.

    Patterns observed in JAI359026.xlsb:
      - Forward:  CCRCRDREF = 'JANKI39337'         (no suffix)
      - Return:   CCRCRDREF = 'JANKI38133RET1064'  (ends in RET<n>)
      - Exchange: CCRCRDREF = 'JANKI38543EXC1082'  (ends in EXC<n>)
      - RTO:      CAWBNO or CCRCRDREF ends or starts with 'R'
      - Credit:   NTOTAMOUNT < 0
    """
    ref_upper = courier_ref.upper()
    awb_upper = awb.upper()
    if 'RET' in ref_upper:
        return 'Return'
    if 'EXC' in ref_upper:
        return 'Exchange'
    if awb_upper.endswith('R') or awb_upper.startswith('R') or ref_upper.endswith('R') or ref_upper.startswith('R'):
        return 'RTO'
    if total_billed < 0:
        return 'Credit'
    return 'Forward'


# ─── Bluedart .xlsb parser ──────────────────────────────────────────────────

def parse_bluedart_xlsb(file_path: str) -> list[dict]:
    """
    Parse a Bluedart .xlsb billing file.

    Returns a list of normalised row dicts (field names match CourierInvoiceLine).
    Each dict also includes a raw 'shipment_type' key.
    """
    try:
        import pyxlsb
    except ImportError:
        raise ImportError(
            "pyxlsb is required to parse Bluedart .xlsb files. "
            "Install it inside the venv: pip install pyxlsb"
        )

    raw_rows = []
    with pyxlsb.open_workbook(file_path) as wb:
        with wb.get_sheet(1) as sh:            # Sheet1 is index 1 in pyxlsb
            for row in sh.rows():
                raw_rows.append([c.v for c in row])

    if not raw_rows:
        raise ValueError("Excel file appears empty.")

    headers = [str(h).strip() if h is not None else '' for h in raw_rows[0]]
    data_rows = raw_rows[1:]

    parsed = []
    for i, raw in enumerate(data_rows, start=2):
        try:
            row_dict = {h: raw[j] if j < len(raw) else None
                        for j, h in enumerate(headers)}

            # Build normalised record
            awb = _safe_str(row_dict.get('CAWBNO', ''))
            courier_ref = _safe_str(row_dict.get('CCRCRDREF', ''))
            total_billed = _safe_decimal(row_dict.get('NTOTAMOUNT'))

            efss_val = row_dict.get('EFSS_CHARGE')
            if efss_val is None:
                efss_val = row_dict.get('EFSS', Decimal('0'))

            record = {
                'awb_number':             awb,
                'courier_ref':            courier_ref,
                'product_code':           _safe_str(row_dict.get('CPRODCODE', '')),
                'origin_area':            _safe_str(row_dict.get('CORGAREA', '')),
                'dest_area':              _safe_str(row_dict.get('CDSTAREA', '')),
                'dest_pincode':           _safe_str(row_dict.get('DESTPINCODE', '')),
                'commodity':              _safe_str(row_dict.get('COMMODITY', '')),
                'actual_weight_kg':       _safe_decimal(row_dict.get('NACTWGT')),
                'charged_weight_kg':      _safe_decimal(row_dict.get('NCHRGWT')),
                'pieces':                 int(_safe_decimal(row_dict.get('NPCS', 1))),
                'freight':                _safe_decimal(row_dict.get('NFREIGHT')),
                'fsc':                    _safe_decimal(row_dict.get('NFSAMT')),
                'caf':                    _safe_decimal(row_dict.get('NCAFAMT')),
                'efss':                   _safe_decimal(efss_val),
                'fod_charge':             _safe_decimal(row_dict.get('NFODCHRG')),
                'declared_value_charge':  _safe_decimal(row_dict.get('NVALCHGS')),
                'idc_charge':             _safe_decimal(row_dict.get('NIDCCHGS')),
                'misc_charges':           Decimal('0'),
                'total_billed':           total_billed,
                'shipment_type':          _classify_type(courier_ref, awb, total_billed),
                'expected_weight_kg':     EXPECTED_SLAB_KG,
            }

            if not record['awb_number']:
                logger.warning("Row %d skipped: no AWB number", i)
                continue

            parsed.append(record)

        except Exception as e:
            logger.warning("Row %d parse error: %s", i, e)
            continue

    logger.info("Parsed %d rows from Bluedart xlsb (%d data rows)", len(parsed), len(data_rows))
    return parsed


def parse_bluedart_xlsx(file_path: str) -> list[dict]:
    """
    Parse a Bluedart .xlsx billing file.
    """
    import pandas as pd
    
    df = pd.read_excel(file_path, sheet_name=0)
    df.columns = [str(col).strip().upper() for col in df.columns]
    
    parsed = []
    for idx, row_series in df.iterrows():
        row_dict = row_series.to_dict()
        awb = _safe_str(row_dict.get('CAWBNO', ''))
        if not awb:
            continue
            
        courier_ref = _safe_str(row_dict.get('CCRCRDREF', ''))
        total_billed = _safe_decimal(row_dict.get('NTOTAMOUNT'))
        
        efss_val = row_dict.get('EFSS_CHARGE')
        if efss_val is None:
            efss_val = row_dict.get('EFSS', Decimal('0'))
            
        record = {
            'awb_number':             awb,
            'courier_ref':            courier_ref,
            'product_code':           _safe_str(row_dict.get('CPRODCODE', '')),
            'origin_area':            _safe_str(row_dict.get('CORGAREA', '')),
            'dest_area':              _safe_str(row_dict.get('CDSTAREA', '')),
            'dest_pincode':           _safe_str(row_dict.get('DESTPINCODE', '')),
            'commodity':              _safe_str(row_dict.get('COMMODITY', '')),
            'actual_weight_kg':       _safe_decimal(row_dict.get('NACTWGT')),
            'charged_weight_kg':      _safe_decimal(row_dict.get('NCHRGWT')),
            'pieces':                 int(_safe_decimal(row_dict.get('NPCS', 1))),
            'freight':                _safe_decimal(row_dict.get('NFREIGHT')),
            'fsc':                    _safe_decimal(row_dict.get('NFSAMT')),
            'caf':                    _safe_decimal(row_dict.get('NCAFAMT')),
            'efss':                   _safe_decimal(efss_val),
            'fod_charge':             _safe_decimal(row_dict.get('NFODCHRG')),
            'declared_value_charge':  _safe_decimal(row_dict.get('NVALCHGS')),
            'idc_charge':             _safe_decimal(row_dict.get('NIDCCHGS')),
            'misc_charges':           Decimal('0'),
            'total_billed':           total_billed,
            'shipment_type':          _classify_type(courier_ref, awb, total_billed),
            'expected_weight_kg':     EXPECTED_SLAB_KG,
        }
        parsed.append(record)
        
    logger.info("Parsed %d rows from Bluedart xlsx", len(parsed))
    return parsed


# ─── Dispatcher ─────────────────────────────────────────────────────────────

def parse_invoice_file(file_path: str, courier_partner: str) -> list[dict]:
    """
    Main entry point. Dispatches to the correct courier parser.

    Args:
        file_path:       Absolute path to the uploaded file.
        courier_partner: 'Bluedart', 'Delhivery', 'Ekart', etc.

    Returns:
        List of normalised row dicts.
    """
    partner = courier_partner.strip().lower()

    if partner == 'bluedart':
        if file_path.lower().endswith('.xlsb'):
            return parse_bluedart_xlsb(file_path)
        else:
            return parse_bluedart_xlsx(file_path)

    # Future couriers — raise clear error
    raise NotImplementedError(
        f"No Excel parser implemented for '{courier_partner}'. "
        "Currently supported: Bluedart (.xlsb, .xlsx)"
    )
