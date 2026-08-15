/** 图表可视窗口与图表设置的纯计算/类型定义（多标的共享），与 ECharts 解耦便于单测。 */
import type { KlinePeriod } from "./resample";

export interface ZoomWindow {
  start: number;
  end: number;
}

export type Sub = "vol" | "macd" | "rsi" | "kdj" | "atr";
export type Overlay = "ma5" | "ma10" | "ma20" | "ma60" | "ema12" | "ema26" | "boll";

/** 多标的共用的图表设置（RunDetail 级共享状态）；可视窗口走 ref（拖动不触发重渲染）。 */
export interface ChartView {
  sub: Sub;
  overlays: Overlay[];
  period: KlinePeriod | null;
}

export const DEFAULT_CHART_VIEW: ChartView = {
  sub: "vol",
  overlays: ["ma5", "ma20"],
  period: null,
};

/** 默认显示最后 250 根 K 线。 */
export const DEFAULT_VISIBLE_BARS = 250;

/** 无历史窗口时，显示数据末尾 DEFAULT_VISIBLE_BARS 根的起始百分比。 */
export function defaultZoomStart(barCount: number): number {
  if (barCount <= DEFAULT_VISIBLE_BARS) return 0;
  return Math.max(0, 100 - (DEFAULT_VISIBLE_BARS / barCount) * 100);
}

/**
 * 计算 dataZoom 的 start/end 百分比。
 * 有当前/共享窗口时沿用其百分比（夹取到 [0,100] 且 end ≥ start），否则用默认窗口。
 */
export function resolveZoom(
  window: ZoomWindow | null | undefined,
  barCount: number,
): { start: number; end: number } {
  const fallbackStart = defaultZoomStart(barCount);
  if (!window || typeof window.start !== "number" || typeof window.end !== "number") {
    return { start: fallbackStart, end: 100 };
  }
  const start = Math.min(Math.max(window.start, 0), 100);
  const end = Math.max(Math.min(window.end, 100), start);
  return { start, end };
}
