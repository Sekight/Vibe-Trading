import type { PriceBar } from "@/lib/api";

export type KlinePeriod = "5m" | "15m" | "20m" | "1h" | "2h" | "4h" | "1D" | "1W" | "1M" | "1Y";

export const KLINE_PERIODS: KlinePeriod[] = [
  "5m",
  "15m",
  "20m",
  "1h",
  "2h",
  "4h",
  "1D",
  "1W",
  "1M",
  "1Y",
];

const PERIOD_MINUTES: Partial<Record<KlinePeriod, number>> = {
  "5m": 5,
  "15m": 15,
  "20m": 20,
  "1h": 60,
  "2h": 120,
  "4h": 240,
};

export function isIntradayPeriod(period: KlinePeriod): boolean {
  return PERIOD_MINUTES[period] != null;
}

function parseTime(time: string): Date {
  const normalized = time.includes("T") ? time : time.replace(" ", "T");
  const parsed = new Date(normalized);
  return Number.isNaN(parsed.getTime()) ? new Date(normalized.slice(0, 10) + "T00:00:00") : parsed;
}

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function formatDate(d: Date): string {
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
}

function formatMinute(d: Date): string {
  return `${formatDate(d)} ${pad(d.getHours())}:${pad(d.getMinutes())}:00`;
}

function isoWeekStart(datePart: string): string {
  const d = new Date(`${datePart}T00:00:00`);
  const day = d.getDay();
  const diff = day === 0 ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  return formatDate(d);
}

export function periodKeyOfDate(datePart: string, period: KlinePeriod): string {
  if (period === "1D") return datePart;
  if (period === "1W") return isoWeekStart(datePart);
  if (period === "1M") return datePart.slice(0, 7);
  return datePart.slice(0, 4);
}

export function tradeDateOfTime(time: string): string {
  if (time.length > 10 && Number(time.slice(11, 13)) >= 21) {
    const d = new Date(`${time.slice(0, 10)}T00:00:00`);
    d.setDate(d.getDate() + 1);
    return formatDate(d);
  }
  return time.slice(0, 10);
}

export function periodKeyOf(time: string, period: KlinePeriod): string {
  const minutes = PERIOD_MINUTES[period];
  if (minutes != null) {
    const d = parseTime(time);
    const total = d.getHours() * 60 + d.getMinutes();
    const bucket = Math.floor(total / minutes) * minutes;
    const start = new Date(d);
    start.setHours(0, bucket, 0, 0);
    return formatMinute(start);
  }
  return periodKeyOfDate(time.slice(0, 10), period);
}

export function resampleBars(bars: PriceBar[], period: KlinePeriod): PriceBar[] {
  if (bars.length === 0) return [];
  const ordered = bars.map((bar) => ({
    ...bar,
    open: Number(bar.open),
    high: Number(bar.high),
    low: Number(bar.low),
    close: Number(bar.close),
    volume: Number(bar.volume) || 0,
    trade_date: bar.trade_date || undefined,
  })).sort((a, b) => a.time.localeCompare(b.time));
  const grouped = new Map<string, PriceBar>();
  for (const bar of ordered) {
    const minutes = PERIOD_MINUTES[period];
    const key = minutes != null ? periodKeyOf(bar.time, period) : periodKeyOfDate(bar.trade_date || bar.time.slice(0, 10), period);
    const current = grouped.get(key);
    if (!current) {
      grouped.set(key, { ...bar, time: key, high: bar.high, low: bar.low });
      continue;
    }
    current.high = Math.max(current.high, bar.high);
    current.low = Math.min(current.low, bar.low);
    current.close = bar.close;
    current.volume += bar.volume;
    current.trade_date = bar.trade_date ?? current.trade_date;
  }
  return [...grouped.values()].sort((a, b) => a.time.localeCompare(b.time));
}

export function availablePeriods(baseInterval?: string): KlinePeriod[] {
  const base = String(baseInterval || "5m").toLowerCase();
  const baseMinutes: number | null = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "20m": 20,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "1d": null,
  }[base] ?? null;
  if (baseMinutes == null) return ["1D", "1W", "1M", "1Y"];
  return KLINE_PERIODS.filter((period) => {
    const minutes = PERIOD_MINUTES[period];
    if (minutes == null) return true;
    return minutes >= baseMinutes;
  });
}
