import { describe, expect, it } from "vitest";
import { extractCandleOhlc, pickCandleOhlc } from "@/lib/candleOhlc";

describe("extractCandleOhlc", () => {
  it("extracts a valid 4-element tuple", () => {
    expect(extractCandleOhlc([3150, 3115, 3094, 3161])).toEqual([3150, 3115, 3094, 3161]);
  });

  it("ignores a leading index/x dimension from ECharts value", () => {
    expect(extractCandleOhlc([64, 3150, 3115, 3094, 3161])).toEqual([3150, 3115, 3094, 3161]);
  });

  it("rejects tuples that violate OHLC ordering", () => {
    expect(extractCandleOhlc([3150, 3115, 3200, 3094])).toBeNull();
    expect(extractCandleOhlc([3150, 3115, 3094, 3000])).toBeNull();
  });

  it("rejects non-arrays and short arrays", () => {
    expect(extractCandleOhlc(null)).toBeNull();
    expect(extractCandleOhlc([3150, 3115])).toBeNull();
  });
});

describe("pickCandleOhlc", () => {
  it("prefers params.data over a shifted params.value", () => {
    const params = {
      data: [3150, 3115, 3094, 3161],
      value: [64, 3150, 3115, 3094, 3161],
    };
    expect(pickCandleOhlc(params)).toEqual([3150, 3115, 3094, 3161]);
  });

  it("falls back to value when data is not an array", () => {
    expect(pickCandleOhlc({ data: { value: 1 }, value: [64, 3150, 3115, 3094, 3161] })).toEqual([3150, 3115, 3094, 3161]);
  });

  it("returns null when both are invalid", () => {
    expect(pickCandleOhlc({ data: null, value: [1, 2] })).toBeNull();
  });
});
