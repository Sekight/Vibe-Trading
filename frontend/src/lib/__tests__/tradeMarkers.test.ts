import { describe, expect, it } from "vitest";
import { mergeBarTradeMarks, type TradeMarkInput } from "@/lib/tradeMarkers";

function item(label: TradeMarkInput["label"], price: number, qty?: number): TradeMarkInput {
  return { label, price, qty };
}

describe("mergeBarTradeMarks", () => {
  it("merges same-type marks into one label", () => {
    const merged = mergeBarTradeMarks([item("B", 3150), item("B", 3152)], 3160, 3100);
    expect(merged?.label).toBe("B");
    expect(merged?.count).toBe(2);
    expect(merged?.buySide).toBe(true);
    expect(merged?.detail).toContain("B x2 @ 3150/3152");
  });

  it("merges B+CB into T", () => {
    const merged = mergeBarTradeMarks([item("B", 3150), item("CB", 3155)], 3160, 3100);
    expect(merged?.label).toBe("T");
    expect(merged?.buySide).toBe(false);
    expect(merged?.detail).toContain("B x1 @ 3150");
    expect(merged?.detail).toContain("CB x1 @ 3155");
  });

  it("merges S+CS into T", () => {
    const merged = mergeBarTradeMarks([item("S", 3160), item("CS", 3155)], 3160, 3100);
    expect(merged?.label).toBe("T");
  });

  it("merges any mixed labels into T", () => {
    for (const labels of [
      ["B", "S"],
      ["B", "CS"],
      ["S", "CB"],
      ["B", "CB", "S"],
    ] as const) {
      const merged = mergeBarTradeMarks(labels.map((label, i) => item(label, 3150 + i)), 3160, 3100);
      expect(merged?.label).toBe("T");
    }
  });

  it("places the merged mark above the bar high", () => {
    const merged = mergeBarTradeMarks([item("B", 3150), item("CB", 3155)], 3160, 3100);
    expect(merged?.price).toBeGreaterThan(3160);
  });

  it("returns null for empty input", () => {
    expect(mergeBarTradeMarks([], 3160, 3100)).toBeNull();
  });
});
