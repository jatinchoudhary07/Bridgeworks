export function formatCurrency(amount, currency = 'INR', locale = 'en-IN', options = {}) {
  const value = Number(amount ?? 0);
  if (!Number.isFinite(value)) return '—';

  const currencyDisplay = currency === 'INR' ? 'symbol' : 'code';
  const defaultOptions = {
    style: 'currency',
    currency,
    currencyDisplay,
    minimumFractionDigits: currency === 'INR' ? 2 : 2,
    maximumFractionDigits: currency === 'INR' ? 2 : 2,
  };

  // Merge options and ensure fraction digit constraints are valid for Intl.NumberFormat
  const merged = { ...defaultOptions, ...options };

  // Helper to coerce and clamp integer fraction digits to [0,20]
  const clamp = (v) => {
    const n = Number(v);
    if (!Number.isFinite(n)) return undefined;
    const i = Math.trunc(n);
    if (i < 0) return 0;
    if (i > 20) return 20;
    return i;
  };

  const minFD = clamp(merged.minimumFractionDigits);
  const maxFD = clamp(merged.maximumFractionDigits);

  if (minFD !== undefined) merged.minimumFractionDigits = minFD;
  if (maxFD !== undefined) merged.maximumFractionDigits = maxFD;

  // Ensure minimumFractionDigits <= maximumFractionDigits to avoid RangeError
  if (
    typeof merged.minimumFractionDigits === 'number' &&
    typeof merged.maximumFractionDigits === 'number' &&
    merged.minimumFractionDigits > merged.maximumFractionDigits
  ) {
    merged.minimumFractionDigits = merged.maximumFractionDigits;
  }

  return new Intl.NumberFormat(locale, merged).format(value);
}
