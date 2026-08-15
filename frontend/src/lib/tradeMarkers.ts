export type TradeMarkLabel = "B" | "S" | "CB" | "CS" | "T";

export interface TradeMarkInput {
  label: "B" | "S" | "CB" | "CS";
  price: number;
  qty?: number;
  reason?: string;
  time?: string;
}

export interface MergedTradeMark {
  label: TradeMarkLabel;
  /** 标记放置价格：统一放到 bar 最高价上方，避免盖住 K 线。 */
  price: number;
  count: number;
  /** tooltip 摘要：例如 `2 笔：B x1 @ 3150；CB x1 @ 3155`。 */
  detail: string;
  /** true 表示原始 side 为买入（B/CS），对应红色；false 表示卖出（S/CB），对应绿色。T 由调用方单独用灰色。 */
  buySide: boolean;
}

function groupByLabel(items: TradeMarkInput[]): Map<string, TradeMarkInput[]> {
  const groups = new Map<string, TradeMarkInput[]>();
  for (const item of items) {
    const list = groups.get(item.label) ?? [];
    list.push(item);
    groups.set(item.label, list);
  }
  return groups;
}

/**
 * 合并同一根 K 线上的多笔交易标记。
 * 规则：同类型合并为同类型单字母；类型不唯一则合并为 T（灰色）；多个 T 只保留一个。
 */
export function mergeBarTradeMarks(
  items: TradeMarkInput[],
  barHigh: number,
  barLow: number,
): MergedTradeMark | null {
  if (!items || items.length === 0) return null;
  const labels = new Set(items.map((item) => item.label));
  const label = labels.size === 1 ? [...labels][0] : "T";
  const buySide = label !== "T" && (label === "B" || label === "CS");

  const span = barHigh - barLow;
  const anchor = Math.max(barHigh, ...items.map((item) => item.price));
  const price = span > 0 ? anchor + span * 0.03 : anchor + 1;

  const groups = groupByLabel(items);
  const detailParts: string[] = [];
  for (const [groupLabel, groupItems] of groups) {
    const prices = [...new Set(groupItems.map((item) => item.price))].sort((a, b) => a - b);
    detailParts.push(`${groupLabel} x${groupItems.length} @ ${prices.join("/")}`);
  }
  const detail = `${items.length} 笔：${detailParts.join("；")}`;

  return { label, price, count: items.length, detail, buySide };
}
