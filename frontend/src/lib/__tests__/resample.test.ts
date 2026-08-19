import { describe, expect, it } from "vitest";
import type { PriceBar } from "@/lib/api";
import { availablePeriods, resampleBars } from "@/lib/resample";

function bar(time: string, o: number, h: number, l: number, c: number, tradeDate?: string, v = 1): PriceBar {
  return { time, open: o, high: h, low: l, close: c, volume: v, trade_date: tradeDate };
}

describe("resampleBars", () => {
  it("aggregates 1D by trade_date and keeps the night-session open", () => {
    const bars = [
      bar("2025-08-29 21:00:00", 3150, 3161, 3150, 3153, "2025-09-01", 100),
      bar("2025-08-29 21:05:00", 3154, 3157, 3150, 3151, "2025-09-01", 50),
      bar("2025-09-01 09:00:00", 3124, 3125, 3113, 3116, "2025-09-01", 80),
      bar("2025-09-01 14:55:00", 3118, 3120, 3115, 3115, "2025-09-01", 40),
    ];
    const out = resampleBars(bars, "1D");
    expect(out).toHaveLength(1);
    expect(out[0].time).toBe("2025-09-01");
    expect(out[0].open).toBe(3150);
    expect(out[0].close).toBe(3115);
    expect(out[0].high).toBe(3161);
    expect(out[0].low).toBe(3113);
    expect(out[0].volume).toBe(270);
  });

  it("sorts unsorted input before aggregating", () => {
    const bars = [
      bar("2025-09-01 10:00:00", 10, 12, 9, 11, "2025-09-01"),
      bar("2025-09-01 09:00:00", 8, 9, 7, 8, "2025-09-01"),
    ];
    const out = resampleBars(bars, "1D");
    expect(out[0].open).toBe(8);
  });

  it("normalizes numeric strings", () => {
    const bars = [
      { time: "2025-09-01", open: "3150", high: "3161", low: "3094", close: "3115", volume: "100", trade_date: "2025-09-01" },
    ] as unknown as PriceBar[];
    const out = resampleBars(bars, "1D");
    expect(out[0].open).toBe(3150);
    expect(out[0].high).toBe(3161);
  });

  it("aggregates 4h bars by natural clock buckets", () => {
    const bars = [
      bar("2025-09-01 09:00:00", 10, 12, 9, 11, undefined, 1),
      bar("2025-09-01 10:00:00", 11, 14, 10, 13, undefined, 2),
      bar("2025-09-01 12:00:00", 13, 15, 12, 14, undefined, 3),
      bar("2025-09-01 15:00:00", 14, 16, 13, 15, undefined, 4),
    ];
    const out = resampleBars(bars, "4h");

    expect(out.map((item) => item.time)).toEqual([
      "2025-09-01 08:00:00",
      "2025-09-01 12:00:00",
    ]);
    expect(out[0]).toMatchObject({ open: 10, high: 14, low: 9, close: 13, volume: 3 });
    expect(out[1]).toMatchObject({ open: 13, high: 16, low: 12, close: 15, volume: 7 });
  });
});

describe("availablePeriods", () => {
  it("limits daily runs to 1D and above", () => {
    expect(availablePeriods("1D")).toEqual(["1D", "1W", "1M", "1Y"]);
  });

  it("offers 4h at the same level as 1D for smaller or equal intraday runs", () => {
    expect(availablePeriods("1H")).toEqual(["1h", "2h", "4h", "1D", "1W", "1M", "1Y"]);
    expect(availablePeriods("2H")).toEqual(["2h", "4h", "1D", "1W", "1M", "1Y"]);
    expect(availablePeriods("4H")).toEqual(["4h", "1D", "1W", "1M", "1Y"]);
  });

  it("keeps 4h out of daily runs because daily data cannot be downsampled", () => {
    expect(availablePeriods("1D")).not.toContain("4h");
  });

  it("keeps all valid periods for 5m runs", () => {
    expect(availablePeriods("5m")).toEqual(["5m", "15m", "20m", "1h", "2h", "4h", "1D", "1W", "1M", "1Y"]);
  });
});
