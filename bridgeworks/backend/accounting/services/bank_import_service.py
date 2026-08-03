"""
Bank Statement Import Service
Handles CSV/TXT/Excel parsing, rule-based classification, and journal entry creation.
"""

import csv
import hashlib
import io
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db import transaction

from accounting.models import JournalEntry, JournalItem, Ledger

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Classification rules — keyword → suggested ledger name + type
# Add / adjust rules as needed without changing any other code.
# ---------------------------------------------------------------------------
CLASSIFICATION_RULES = [
    # Keywords           Ledger name (will be get_or_created)   Type
    (['facebook', 'meta', 'instagram', 'google ads', 'ad spend', 'advertising'],
     'Marketing Expense', 'expense'),
    (['salary', 'salaries', 'payroll', 'staff payment'],
     'Salary Expense', 'expense'),
    (['rent', 'lease', 'office rent'],
     'Rent Expense', 'expense'),
    (['electricity', 'power', 'utility', 'water bill'],
     'Utilities Expense', 'expense'),
    (['travel', 'flight', 'hotel', 'cab', 'uber', 'ola'],
     'Travel Expense', 'expense'),
    (['software', 'subscription', 'saas', 'licence', 'license'],
     'Software Expense', 'expense'),
    (['tax', 'gst', 'tds', 'income tax'],
     'Tax Expense', 'expense'),
    (['interest', 'bank charges', 'bank fee'],
     'Bank Charges', 'expense'),
    (['purchase', 'vendor', 'supplier'],
     'Purchases', 'expense'),
]

# Ledger names used for income / fallback
INCOME_LEDGER_NAME = 'Sales / Income'
FALLBACK_EXPENSE_LEDGER_NAME = 'Miscellaneous Expense'


def _get_or_create_ledger(name: str, ledger_type: str) -> Ledger:
    """Return ledger by name, creating it if absent."""
    ledger, _ = Ledger.objects.get_or_create(
        name=name,
        defaults={'type': ledger_type},
    )
    return ledger


def classify_description(description: str):
    """
    Return (ledger_name, type) for a given transaction description.
    Checks keyword rules first; falls back based on amount sign.
    """
    desc_lower = description.lower()
    for keywords, ledger_name, tx_type in CLASSIFICATION_RULES:
        if any(kw in desc_lower for kw in keywords):
            return ledger_name, tx_type
    return None, None  # caller decides based on amount sign


def _make_hash(date_str: str, amount: str, description: str) -> str:
    raw = f"{date_str}|{amount}|{description}".strip().lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:64]


# ---------------------------------------------------------------------------
# HELPERS — shared row extraction logic
# ---------------------------------------------------------------------------

def _extract_rows_from_reader(reader) -> list[dict]:
    """
    Given a csv.DictReader (or any iterable of dicts with normalised headers),
    extract and return parsed transaction rows.
    """
    if reader.fieldnames is None:
        raise ValueError('File appears to be empty or has no header row.')

    headers = {h.strip().lower(): h for h in reader.fieldnames if h}

    def _col(*names):
        for n in names:
            if n in headers:
                return headers[n]
        return None

    date_col   = _col('date', 'transaction date', 'txn date', 'value date')
    desc_col   = _col('description', 'narration', 'particulars', 'details', 'remarks')
    debit_col  = _col('debit', 'withdrawal', 'withdrawal amt', 'dr', 'debit amount')
    credit_col = _col('credit', 'deposit', 'deposit amt', 'cr', 'credit amount')
    amount_col = _col('amount', 'transaction amount')

    if not date_col or not desc_col:
        raise ValueError(
            'File must have at least "Date" and "Description" columns. '
            f'Found: {list(headers.keys())}'
        )
    if not debit_col and not credit_col and not amount_col:
        raise ValueError('File must have either Debit/Credit columns or an Amount column.')

    rows = []
    for raw_row in reader:
        raw_row = {k: (v or '').strip() for k, v in raw_row.items() if k}
        date_str    = raw_row.get(date_col, '').strip()
        description = raw_row.get(desc_col, '').strip()
        if not date_str or not description:
            continue

        parsed_date = None
        for fmt in ('%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%m/%d/%Y', '%d %b %Y', '%d-%b-%Y'):
            try:
                parsed_date = datetime.strptime(date_str, fmt).date()
                break
            except ValueError:
                continue
        if not parsed_date:
            logger.warning('Could not parse date "%s" — skipping row.', date_str)
            continue

        def _decimal(val: str) -> Decimal:
            cleaned = val.replace(',', '').replace(' ', '').strip()
            if not cleaned:
                return Decimal('0')
            try:
                return Decimal(cleaned)
            except InvalidOperation:
                return Decimal('0')

        if amount_col:
            amount = _decimal(raw_row.get(amount_col, '0'))
        else:
            debit  = _decimal(raw_row.get(debit_col or '',  '0'))
            credit = _decimal(raw_row.get(credit_col or '', '0'))
            amount = credit - debit

        if amount == 0:
            continue

        rows.append({
            'date':        parsed_date.isoformat(),
            'description': description,
            'amount':      float(amount),
        })

    return rows


# ---------------------------------------------------------------------------
# FILE PARSING  (CSV / TXT / Excel)
# ---------------------------------------------------------------------------

def parse_file(file_bytes: bytes, file_type: str = 'csv') -> list[dict]:
    """
    Parse a bank-statement file.  `file_type` is one of: csv | txt | xlsx | xls | pdf

    Returns list of dicts: { date, description, amount (float, negative=out) }
    """
    file_type = (file_type or 'csv').lower().strip()

    if file_type in ('csv', 'txt'):
        return _parse_delimited(file_bytes)
    if file_type in ('xlsx', 'xls', 'excel'):
        return _parse_excel(file_bytes)
    if file_type == 'pdf':
        return _parse_pdf(file_bytes)
    raise ValueError(f'Unsupported file type: {file_type}. Supported: csv, txt, xlsx, pdf.')


def _parse_delimited(file_bytes: bytes) -> list[dict]:
    """Parse CSV or TXT (auto-detects delimiter: comma, tab, pipe, semicolon)."""
    text = file_bytes.decode('utf-8-sig', errors='replace')
    sample = text[:4096]

    # Sniff delimiter
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=',\t|;')
    except csv.Error:
        dialect = csv.excel   # fallback to comma

    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    return _extract_rows_from_reader(reader)


def _parse_excel(file_bytes: bytes) -> list[dict]:
    """Parse XLS / XLSX files using openpyxl."""
    try:
        import openpyxl  # noqa: PLC0415
    except ImportError:
        raise ValueError(
            'openpyxl is required to parse Excel files. '
            'Install it with: pip install openpyxl'
        )

    wb = openpyxl.load_workbook(filename=io.BytesIO(file_bytes), read_only=True, data_only=True)
    ws = wb.active

    rows_iter = ws.iter_rows(values_only=True)

    # First row = headers
    try:
        header_row = next(rows_iter)
    except StopIteration:
        raise ValueError('Excel file appears to be empty.')

    # Build a fake DictReader by constructing dicts manually
    headers = [str(h).strip() if h is not None else '' for h in header_row]

    class _FakeDictReader:
        """Wraps an iterable of value-tuples to look like csv.DictReader."""
        def __init__(self, rows, fieldnames):
            self.fieldnames = fieldnames
            self._rows = rows

        def __iter__(self):
            for row in self._rows:
                yield {headers[i]: (str(row[i]).strip() if row[i] is not None else '')
                       for i in range(min(len(headers), len(row)))}

    fake_reader = _FakeDictReader(rows_iter, headers)
    return _extract_rows_from_reader(fake_reader)


def _parse_pdf(file_bytes: bytes) -> list[dict]:
    """
    Parse a PDF bank statement using pdfplumber.

    Strategy:
    1. Extract all tables from every page.
    2. Find the table whose header row best matches expected column names
       (Date, Description, Debit, Credit / Amount).
    3. Use _extract_rows_from_reader on that table (converted to DictReader-like).
    4. If no structured table found, fall back to line-by-line text heuristics.
    """
    try:
        import pdfplumber  # noqa: PLC0415
    except ImportError:
        raise ValueError(
            'pdfplumber is required to parse PDF files. '
            'Install it with: pip install pdfplumber'
        )

    KNOWN_HEADERS = {
        'date', 'transaction date', 'txn date', 'value date',
        'description', 'narration', 'particulars', 'details',
        'debit', 'credit', 'withdrawal', 'deposit', 'amount',
        'dr', 'cr', 'withdrawal amt', 'deposit amt',
    }

    def _score_header_row(row):
        """Return how many cells match known header names."""
        return sum(1 for cell in row if cell and cell.strip().lower() in KNOWN_HEADERS)

    all_tables = []  # list of (score, header_row, data_rows)

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            for table in (tables or []):
                if not table or len(table) < 2:
                    continue
                # Try each of the first 5 rows as a potential header
                for hi in range(min(5, len(table))):
                    row = [str(c or '').strip() for c in table[hi]]
                    score = _score_header_row(row)
                    if score >= 2:
                        data_rows = table[hi + 1:]
                        all_tables.append((score, row, data_rows))
                        break

    if not all_tables:
        raise ValueError(
            'No recognisable transaction table found in this PDF. '
            'Make sure the PDF contains a table with Date, Description, and Debit/Credit columns.'
        )

    # Pick the table with the best header match
    all_tables.sort(key=lambda x: -x[0])
    _, header_row, data_rows = all_tables[0]

    # Build a fake DictReader
    class _PDFDictReader:
        def __init__(self, headers, rows):
            self.fieldnames = headers
            self._rows = rows

        def __iter__(self):
            for row in self._rows:
                row = [str(c or '').strip() for c in row]
                # Pad short rows
                while len(row) < len(self.fieldnames):
                    row.append('')
                yield {self.fieldnames[i]: row[i] for i in range(len(self.fieldnames))}

    reader = _PDFDictReader(header_row, data_rows)
    return _extract_rows_from_reader(reader)


# ---------------------------------------------------------------------------
# LEGACY ALIAS — kept so any existing callers still work
# ---------------------------------------------------------------------------

def parse_csv(file_bytes: bytes) -> list[dict]:
    return _parse_delimited(file_bytes)


# ---------------------------------------------------------------------------
# PREVIEW (no DB writes)
# ---------------------------------------------------------------------------

def build_preview(rows: list[dict], bank_account_id: int) -> list[dict]:
    """
    Attach suggested_ledger_id + type to each parsed row.
    Does NOT write anything to the database.
    """
    # Pre-fetch all ledgers to avoid N+1
    all_ledgers = {l.name: l for l in Ledger.objects.all()}

    def _resolve_ledger(name: str, ltype: str) -> Ledger | None:
        if name in all_ledgers:
            return all_ledgers[name]
        # Will be created on confirm
        return None

    preview = []
    for row in rows:
        ledger_name, tx_type = classify_description(row['description'])
        amount = row['amount']

        if tx_type is None:
            if amount < 0:
                ledger_name = FALLBACK_EXPENSE_LEDGER_NAME
                tx_type = 'expense'
            else:
                ledger_name = INCOME_LEDGER_NAME
                tx_type = 'income'

        ledger = _resolve_ledger(ledger_name, 'expense' if tx_type == 'expense' else 'income')

        import_hash = _make_hash(row['date'], str(amount), row['description'])
        duplicate = JournalEntry.objects.filter(import_hash=import_hash).exists()

        preview.append({
            'date': row['date'],
            'description': row['description'],
            'amount': amount,
            'suggested_ledger_id': ledger.id if ledger else None,
            'suggested_ledger_name': ledger_name,
            'type': tx_type,
            'import_hash': import_hash,
            'is_duplicate': duplicate,
        })

    return preview


# ---------------------------------------------------------------------------
# CONFIRM (actual DB writes)
# ---------------------------------------------------------------------------

def confirm_import(transactions: list[dict], bank_account_id: int, org_id: str = '') -> dict:
    """
    Create one JournalEntry per transaction.

    Each item in `transactions`:
      {
        date, description, amount (float),
        ledger_id (int),
        department (str, optional),
        import_hash (str)
      }

    Returns { created: int, skipped_duplicates: int, errors: list[str] }
    """
    try:
        bank_ledger = Ledger.objects.get(pk=bank_account_id, org_id=org_id)
    except Ledger.DoesNotExist:
        raise ValueError(f'Bank ledger id={bank_account_id} not found.')

    created_count = 0
    skipped_count = 0
    errors = []

    with transaction.atomic():
        for item in transactions:
            import_hash = item.get('import_hash', '')
            amount = Decimal(str(item.get('amount', 0)))

            if amount == 0:
                errors.append(f'Row "{item.get("description")}" has zero amount — skipped.')
                continue

            ledger_id = item.get('ledger_id')
            if not ledger_id:
                errors.append(f'Row "{item.get("description")}" has no ledger — skipped.')
                continue

            # Duplicate guard
            if import_hash and JournalEntry.objects.filter(org_id=org_id, import_hash=import_hash).exists():
                skipped_count += 1
                continue

            try:
                counter_ledger = Ledger.objects.get(pk=ledger_id, org_id=org_id)
            except Ledger.DoesNotExist:
                errors.append(f'Ledger id={ledger_id} not found — row skipped.')
                continue

            abs_amount = abs(amount)
            description = item.get('description', '')
            department = item.get('department', '') or None

            entry = JournalEntry.objects.create(
                org_id=org_id,
                date=item['date'],
                description=description,
                import_hash=import_hash or None,
            )

            if amount < 0:
                # Money OUT: Debit expense/counter ledger, Credit bank
                JournalItem.objects.create(
                    org_id=org_id,
                    entry=entry, ledger=counter_ledger,
                    debit=abs_amount, credit=Decimal('0'),
                    department=department, notes=description,
                )
                JournalItem.objects.create(
                    org_id=org_id,
                    entry=entry, ledger=bank_ledger,
                    debit=Decimal('0'), credit=abs_amount,
                    department=department, notes=description,
                )
            else:
                # Money IN: Debit bank, Credit income/counter ledger
                JournalItem.objects.create(
                    org_id=org_id,
                    entry=entry, ledger=bank_ledger,
                    debit=abs_amount, credit=Decimal('0'),
                    department=department, notes=description,
                )
                JournalItem.objects.create(
                    org_id=org_id,
                    entry=entry, ledger=counter_ledger,
                    debit=Decimal('0'), credit=abs_amount,
                    department=department, notes=description,
                )

            created_count += 1

    return {
        'created': created_count,
        'skipped_duplicates': skipped_count,
        'errors': errors,
    }

