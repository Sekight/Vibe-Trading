export type TradeAction = "open" | "close";
export type TradeDirection = "long" | "short";
export type TradeKind = "long_open" | "short_open" | "long_close" | "short_close";

export interface TradeActionInfo {
  action: TradeAction;
  direction: TradeDirection;
  kind: TradeKind;
}

export interface TradeMarkerStyle {
  label: "B" | "S" | "CB" | "CS";
  /** true 表示原始 side 为买入（多开/空平），对应图表红色；false 为卖出（空开/多平），对应绿色。 */
  buySide: boolean;
}

export function tradeMarkerStyle(marker: {
  side?: string;
  action?: string;
  direction?: string;
}): TradeMarkerStyle {
  const side = String(marker.side || "").toUpperCase();
  const direction = marker.direction || (side === "BUY" ? "long" : "short");
  const isClose = marker.action === "close";
  const label = isClose ? (direction === "long" ? "CB" : "CS") : (direction === "long" ? "B" : "S");
  return { label, buySide: side === "BUY" };
}

function toNumber(value: unknown): number | null {
  if (value == null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * Classify a trade-log row as open/close + long/short.
 *
 * trades.csv writes entry rows with pnl/holding_bars/holding_days = 0 and exit
 * rows with a realized pnl or positive holding bars. Long entries are `buy`,
 * short entries are `sell`; long exits are `sell` and short exits are `buy`.
 * This model is market-agnostic and can be reused for futures, crypto, forex,
 * etc. as long as the row keeps side + pnl/holding fields.
 */
export function tradeActionInfo(row: {
  side?: string;
  pnl?: unknown;
  holding_bars?: unknown;
  holding_days?: unknown;
}): TradeActionInfo | null {
  const side = String(row.side || "").trim().toLowerCase();
  if (side !== "buy" && side !== "sell") return null;
  const pnl = toNumber(row.pnl);
  const holdingBars = toNumber(row.holding_bars);
  const holdingDays = toNumber(row.holding_days);
  const isClose =
    (pnl != null && pnl !== 0) ||
    (holdingBars != null && holdingBars > 0) ||
    (holdingDays != null && holdingDays > 0);
  if (isClose) {
    const direction: TradeDirection = side === "sell" ? "long" : "short";
    return { action: "close", direction, kind: `${direction}_close` as TradeKind };
  }
  const direction: TradeDirection = side === "buy" ? "long" : "short";
  return { action: "open", direction, kind: `${direction}_open` as TradeKind };
}
