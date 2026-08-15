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
});

describe("availablePeriods", () => {
  it("limits daily runs to 1D and above", () => {
    expect(availablePeriods("1D")).toEqual(["1D", "1W", "1M", "1Y"]);
  });

  it("keeps all periods for 5m runs", () => {
    expect(availablePeriods("5m")).toHaveLength(9);
  });
});
