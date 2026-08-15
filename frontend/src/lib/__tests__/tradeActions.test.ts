import { describe, expect, it } from "vitest";
import { tradeActionInfo, tradeMarkerStyle } from "@/lib/tradeActions";

describe("tradeActionInfo", () => {
  it("classifies long open", () => {
    expect(tradeActionInfo({ side: "buy", pnl: 0, holding_bars: 0 })).toEqual({
      action: "open", direction: "long", kind: "long_open",
    });
  });

  it("classifies short open", () => {
    expect(tradeActionInfo({ side: "sell", pnl: 0, holding_bars: 0 })).toEqual({
      action: "open", direction: "short", kind: "short_open",
    });
  });

  it("classifies long close (sell exit)", () => {
    expect(tradeActionInfo({ side: "sell", pnl: 330, holding_bars: 50 })).toEqual({
      action: "close", direction: "long", kind: "long_close",
    });
  });

  it("classifies short close (buy exit)", () => {
    expect(tradeActionInfo({ side: "buy", pnl: -1400, holding_bars: 13 })).toEqual({
      action: "close", direction: "short", kind: "short_close",
    });
  });

  it("treats breakeven exits as close via holding_bars", () => {
    expect(tradeActionInfo({ side: "sell", pnl: 0, holding_bars: 5 })).toEqual({
      action: "close", direction: "long", kind: "long_close",
    });
  });

  it("falls back to holding_days for legacy runs", () => {
    expect(tradeActionInfo({ side: "buy", pnl: "0", holding_days: "3" })).toEqual({
      action: "close", direction: "short", kind: "short_close",
    });
  });

  it("returns null for invalid side", () => {
    expect(tradeActionInfo({ side: "hold" })).toBeNull();
  });
});

describe("tradeMarkerStyle", () => {
  it("maps long open to red B", () => {
    expect(tradeMarkerStyle({ side: "BUY", action: "open", direction: "long" })).toEqual({ label: "B", buySide: true });
  });
  it("maps short open to green S", () => {
    expect(tradeMarkerStyle({ side: "SELL", action: "open", direction: "short" })).toEqual({ label: "S", buySide: false });
  });
  it("maps long close to green CB", () => {
    expect(tradeMarkerStyle({ side: "SELL", action: "close", direction: "long" })).toEqual({ label: "CB", buySide: false });
  });
  it("maps short close to red CS", () => {
    expect(tradeMarkerStyle({ side: "BUY", action: "close", direction: "short" })).toEqual({ label: "CS", buySide: true });
  });
  it("falls back to side when action/direction missing", () => {
    expect(tradeMarkerStyle({ side: "BUY" })).toEqual({ label: "B", buySide: true });
    expect(tradeMarkerStyle({ side: "SELL" })).toEqual({ label: "S", buySide: false });
  });
});
