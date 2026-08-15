export type CandleOhlc = [open: number, close: number, low: number, high: number];

/**
 * Extract a valid [open, close, low, high] tuple from an ECharts tooltip item.
 *
 * ECharts candlestick sometimes exposes `params.value` with an extra leading
 * index/x dimension, so taking the first four elements shifts OHLC by one.
 * Prefer `params.data` (our raw [open, close, low, high]) and fall back to the
 * last four elements of `params.value`. Any tuple that violates OHLC ordering
 * is rejected instead of being displayed as a bogus candle.
 */
export function extractCandleOhlc(raw: unknown): CandleOhlc | null {
  if (!Array.isArray(raw)) return null;
  const values = raw.length >= 4 ? raw.slice(-4) : raw;
  if (values.length !== 4) return null;
  const nums = values.map((v) => Number(v));
  if (!nums.every(Number.isFinite)) return null;
  const [open, close, low, high] = nums as CandleOhlc;
  if (high < Math.max(open, close, low)) return null;
  if (low > Math.min(open, close, high)) return null;
  return [open, close, low, high];
}

export function pickCandleOhlc(params: {
  data?: unknown;
  value?: unknown;
}): CandleOhlc | null {
  return extractCandleOhlc(params.data) ?? extractCandleOhlc(params.value);
}
