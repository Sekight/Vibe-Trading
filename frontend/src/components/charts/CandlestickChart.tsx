import { useEffect, useRef, useState, useMemo, useCallback } from "react";
import i18n from "@/i18n";
import { cn } from "@/lib/utils";
import { ChevronDown } from "lucide-react";
import type { PriceBar, TradeMarker, IndicatorPoint } from "@/lib/api";
import { calcMA, calcBOLL, calcMACD, calcRSI, calcKDJ, calcEMA } from "@/lib/indicators";
import { getChartTheme } from "@/lib/chart-theme";
import { abbreviateNum } from "@/lib/formatters";
import { pickCandleOhlc } from "@/lib/candleOhlc";
import { tradeMarkerStyle } from "@/lib/tradeActions";
import { mergeBarTradeMarks } from "@/lib/tradeMarkers";
import { availablePeriods, periodKeyOf, periodKeyOfDate, resampleBars, tradeDateOfTime, type KlinePeriod } from "@/lib/resample";
import { resolveZoom, type ChartView, type Overlay, type Sub, type ZoomWindow } from "@/lib/chartWindow";
import { echarts, CHART_GROUP, connectCharts } from "@/lib/echarts";
import { useThemeDark } from "@/lib/theme-store";

const OVERLAY_OPTIONS: { id: Overlay; label: string; group: string }[] = [
  { id: "ma5", label: "MA5", group: "MA" },
  { id: "ma10", label: "MA10", group: "MA" },
  { id: "ma20", label: "MA20", group: "MA" },
  { id: "ma60", label: "MA60", group: "MA" },
  { id: "ema12", label: "EMA12", group: "MA" },
  { id: "ema26", label: "EMA26", group: "MA" },
  { id: "boll", label: "BOLL", group: "Channel" },
];

const OVERLAY_COLORS = ["#f59e0b", "#8b5cf6", "#3b82f6", "#ec4899", "#10b981", "#f97316", "#6366f1"];

interface Props {
  data: PriceBar[];
  markers?: TradeMarker[];
  indicators?: Record<string, IndicatorPoint[]>;
  height?: number;
  baseInterval?: string;
  sub: Sub;
  overlays: Overlay[];
  period: KlinePeriod | null;
  window: ZoomWindow | null;
  onViewChange: (patch: Partial<ChartView>) => void;
}

export function CandlestickChart({ data, markers, indicators, height = 500, baseInterval, sub, overlays, period, window: zoomWindow, onViewChange }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  void indicators; // 周期切换后只显示前端重算指标，隐藏后端 indicator_series。
  const chartRef = useRef<ReturnType<typeof echarts.init> | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const dark = useThemeDark();

  const periods = useMemo(() => availablePeriods(baseInterval), [baseInterval]);
  const effectivePeriod = period ?? periods[0] ?? "5m";
  const overlaySet = useMemo(() => new Set(overlays), [overlays]);

  const toggleOverlay = useCallback((id: Overlay) => {
    const next = overlaySet.has(id) ? overlays.filter((o) => o !== id) : [...overlays, id];
    onViewChange({ overlays: next });
  }, [overlays, overlaySet, onViewChange]);

  // 基础周期直接使用原始 bar；切换周期时前端按时间戳/trade_date 聚合。
  const visibleData = useMemo(() => {
    if (effectivePeriod.toLowerCase() === String(baseInterval || "").toLowerCase()) return data;
    return resampleBars(data, effectivePeriod);
  }, [data, effectivePeriod, baseInterval]);

  const baseData = useMemo(() => {
    const dates = visibleData.map(d => d.time);
    const closes = visibleData.map(d => d.close);
    const highs = visibleData.map(d => d.high);
    const lows = visibleData.map(d => d.low);
    const opens = visibleData.map(d => d.open);
    const candle = visibleData.map(d => [d.open, d.close, d.low, d.high]);
    return { dates, closes, highs, lows, opens, candle };
  }, [visibleData]);

  const indicatorCache = useMemo(() => ({
    ma5: calcMA(baseData.closes, 5),
    ma10: calcMA(baseData.closes, 10),
    ma20: calcMA(baseData.closes, 20),
    ma60: calcMA(baseData.closes, 60),
    ema12: calcEMA(baseData.closes, 12),
    ema26: calcEMA(baseData.closes, 26),
    boll: calcBOLL(baseData.closes, 20, 2),
    macd: calcMACD(baseData.closes),
    rsi: calcRSI(baseData.closes),
    kdj: calcKDJ(baseData.highs, baseData.lows, baseData.closes),
  }), [baseData]);

  useEffect(() => {
    if (!containerRef.current || visibleData.length === 0) return;
    const chart = echarts.init(containerRef.current);
    chart.group = CHART_GROUP;
    connectCharts();
    chartRef.current = chart;

    // 用户缩放/滑动时上报当前可视窗口，RunDetail 级共享，供同组新图加入与 setOption 回写沿用。
    const onZoom = (params: any) => {
      const item = params?.batch && params.batch.length > 0 ? params.batch[0] : params;
      if (item && typeof item.start === "number" && typeof item.end === "number") {
        onViewChange({ window: { start: item.start, end: item.end } });
      }
    };
    chart.on("datazoom", onZoom);

    let resizeFrame: number | null = null;
    const ro = new ResizeObserver(() => {
      if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
      resizeFrame = requestAnimationFrame(() => {
        resizeFrame = null;
        chart.resize();
      });
    });
    ro.observe(containerRef.current);
    return () => {
      ro.disconnect();
      if (resizeFrame !== null) cancelAnimationFrame(resizeFrame);
      chart.off("datazoom", onZoom);
      chart.dispose();
      chartRef.current = null;
    };
  }, [visibleData.length === 0, dark]);

  useEffect(() => {
    const chart = chartRef.current;
    if (!chart || visibleData.length === 0) return;

    const t = getChartTheme();
    const { dates, closes, opens, candle } = baseData;

    const overlaySeries: any[] = [];
    const legendNames: string[] = ["K"];
    let colorIdx = 0;

    const overlayMap: Record<string, { name: string; data: (number | null)[] }> = {
      ma5: { name: "MA5", data: indicatorCache.ma5 },
      ma10: { name: "MA10", data: indicatorCache.ma10 },
      ma20: { name: "MA20", data: indicatorCache.ma20 },
      ma60: { name: "MA60", data: indicatorCache.ma60 },
      ema12: { name: "EMA12", data: indicatorCache.ema12 },
      ema26: { name: "EMA26", data: indicatorCache.ema26 },
    };

    for (const [key, { name, data: lineData }] of Object.entries(overlayMap)) {
      if (overlaySet.has(key as Overlay)) {
        overlaySeries.push({ name, type: "line", data: lineData, xAxisIndex: 0, yAxisIndex: 0, symbol: "none", lineStyle: { color: OVERLAY_COLORS[colorIdx], width: 1 } });
        legendNames.push(name);
        colorIdx++;
      }
    }

    if (overlaySet.has("boll")) {
      const boll = indicatorCache.boll;
      overlaySeries.push(
        { name: "BOLL+", type: "line", data: boll.upper, xAxisIndex: 0, yAxisIndex: 0, symbol: "none", lineStyle: { color: t.bollColor, width: 0.8, type: "dashed" } },
        { name: "BOLL", type: "line", data: boll.mid, xAxisIndex: 0, yAxisIndex: 0, symbol: "none", lineStyle: { color: t.bollColor, width: 1 } },
        { name: "BOLL-", type: "line", data: boll.lower, xAxisIndex: 0, yAxisIndex: 0, symbol: "none", lineStyle: { color: t.bollColor, width: 0.8, type: "dashed" } },
      );
      legendNames.push("BOLL");
    }

    const rawMarks: any[] = (markers || []).map(m => {
      let idx = dates.indexOf(m.time);
      if (idx < 0) {
        const isMinute = effectivePeriod === "5m" || effectivePeriod === "15m" || effectivePeriod === "20m" || effectivePeriod === "1h" || effectivePeriod === "2h";
        const hasTradeDate = visibleData.some(d => d.trade_date);
        const markerKey = isMinute ? periodKeyOf(m.time, effectivePeriod) : periodKeyOfDate(hasTradeDate ? tradeDateOfTime(m.time) : m.time.slice(0, 10), effectivePeriod);
        idx = dates.indexOf(markerKey);
      }
      if (idx < 0) return null;
      const markerStyle = tradeMarkerStyle(m);
      return { idx, markerStyle, side: m.side, price: m.price, qty: m.qty, reason: m.reason };
    }).filter(Boolean);

    const groupedMarks = new Map<number, any[]>();
    for (const raw of rawMarks) {
      const list = groupedMarks.get(raw.idx) ?? [];
      list.push(raw);
      groupedMarks.set(raw.idx, list);
    }
    const marks: any[] = [];
    for (const [idx, list] of groupedMarks) {
      const bar = visibleData[idx];
      if (list.length === 1) {
        const raw = list[0];
        marks.push({
          coord: [dates[idx], raw.price],
          value: raw.markerStyle.label,
          name: [`${raw.side} @ ${raw.price}`, raw.qty ? `Qty: ${raw.qty}` : "", raw.reason || ""].filter(Boolean).join("\n"),
          itemStyle: { color: raw.markerStyle.buySide ? t.upColor : t.downColor },
          label: { color: "#fff", fontSize: 10, fontWeight: "bold" as const },
        });
      } else {
        const merged = mergeBarTradeMarks(
          list.map((raw: any) => ({ label: raw.markerStyle.label, price: raw.price, qty: raw.qty, reason: raw.reason })),
          bar.high,
          bar.low,
        );
        if (!merged) continue;
        marks.push({
          coord: [dates[idx], merged.price],
          value: merged.label,
          name: merged.detail,
          itemStyle: { color: merged.label === "T" ? "#9ca3af" : (merged.buySide ? t.upColor : t.downColor) },
          label: { color: "#fff", fontSize: 10, fontWeight: "bold" as const },
        });
      }
    }

    const vol = visibleData.map((d, i) => ({
      value: d.volume,
      itemStyle: { color: closes[i] >= opens[i] ? t.volumeUp : t.volumeDown },
    }));

    let subSeries: any[] = [];
    let subYAxis: any = { scale: true, gridIndex: 1, splitLine: { lineStyle: { color: t.gridColor } }, axisLabel: { color: t.textColor, fontSize: 10 } };

    if (sub === "vol") {
      subSeries = [{ name: "Vol", type: "bar", data: vol, xAxisIndex: 1, yAxisIndex: 1 }];
      subYAxis = { ...subYAxis, axisLabel: { ...subYAxis.axisLabel, formatter: (v: number) => abbreviateNum(v) } };
      legendNames.push("Vol");
    } else if (sub === "macd") {
      const m = indicatorCache.macd;
      subSeries = [
        { name: "DIF", type: "line", data: m.dif, xAxisIndex: 1, yAxisIndex: 1, symbol: "none", lineStyle: { width: 1, color: t.infoColor } },
        { name: "DEA", type: "line", data: m.signal, xAxisIndex: 1, yAxisIndex: 1, symbol: "none", lineStyle: { width: 1, color: t.warningColor } },
        { name: "MACD", type: "bar", data: m.histogram.map(v => ({ value: v ?? 0, itemStyle: { color: (v ?? 0) >= 0 ? t.upColor : t.downColor } })), xAxisIndex: 1, yAxisIndex: 1 },
      ];
      legendNames.push("DIF", "DEA", "MACD");
    } else if (sub === "rsi") {
      subSeries = [{ name: "RSI", type: "line", data: indicatorCache.rsi, xAxisIndex: 1, yAxisIndex: 1, symbol: "none", lineStyle: { width: 1.5, color: t.infoColor } }];
      subYAxis = { ...subYAxis, min: 0, max: 100 };
      legendNames.push("RSI");
    } else {
      const kdj = indicatorCache.kdj;
      subSeries = [
        { name: "%K", type: "line", data: kdj.k, xAxisIndex: 1, yAxisIndex: 1, symbol: "none", lineStyle: { width: 1, color: t.infoColor } },
        { name: "%D", type: "line", data: kdj.d, xAxisIndex: 1, yAxisIndex: 1, symbol: "none", lineStyle: { width: 1, color: t.warningColor } },
        { name: "%J", type: "line", data: kdj.j, xAxisIndex: 1, yAxisIndex: 1, symbol: "none", lineStyle: { width: 1, color: "#a855f7" } },
      ];
      legendNames.push("%K", "%D", "%J");
    }

    const zoom = resolveZoom(zoomWindow, visibleData.length);

    chart.setOption({
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis", axisPointer: { type: "cross" },
        backgroundColor: t.tooltipBg, borderColor: t.tooltipBorder,
        textStyle: { color: t.tooltipText, fontSize: 11 },
        formatter: (params: any) => {
          if (!Array.isArray(params) || !params.length) return "";
          let html = `<b>${params[0].axisValue}</b>`;
          for (const p of params) {
            if (p.seriesName === "K") {
              const ohlc = pickCandleOhlc({ data: p.data, value: p.value });
              if (!ohlc) continue;
              const [open, close, low, high] = ohlc;
              const chg = close - open;
              const pct = open ? ((chg / open) * 100).toFixed(2) : "0.00";
              const clr = chg >= 0 ? t.upColor : t.downColor;
              html += `<br/>O: ${open.toFixed(2)}&nbsp; H: ${high.toFixed(2)}`;
              html += `<br/>L: ${low.toFixed(2)}&nbsp; C: <span style="color:${clr}"><b>${close.toFixed(2)}</b> ${chg >= 0 ? "+" : ""}${chg.toFixed(2)} (${chg >= 0 ? "+" : ""}${pct}%)</span>`;
            } else if (p.seriesName === "Vol") {
              html += `<br/>Vol: ${abbreviateNum(Number(p.value))}`;
            } else if (p.value != null) {
              html += `<br/>${p.marker} ${p.seriesName}: ${Number(p.value).toFixed(2)}`;
            }
          }
          return html;
        },
      },
      toolbox: {
        feature: { saveAsImage: { title: "Save" }, dataZoom: { title: { zoom: "Zoom", back: "Reset" } }, restore: { title: "Reset" } },
        right: 8, top: 0, iconStyle: { borderColor: t.textColor },
      },
      legend: { data: legendNames, textStyle: { color: t.textColor, fontSize: 10 }, right: 80, top: 2, type: "scroll", itemWidth: 12, itemHeight: 8, itemGap: 8 },
      grid: [
        { left: 8, right: 8, top: 36, height: "55%", containLabel: true },
        { left: 8, right: 8, top: "66%", height: "22%", containLabel: true },
      ],
      xAxis: [
        { type: "category", data: dates, gridIndex: 0, axisLine: { lineStyle: { color: t.axisColor } }, axisLabel: { color: t.textColor, fontSize: 10 }, boundaryGap: true },
        { type: "category", data: dates, gridIndex: 1, axisLine: { lineStyle: { color: t.axisColor } }, axisLabel: { show: false }, boundaryGap: true },
      ],
      yAxis: [
        { scale: true, gridIndex: 0, splitLine: { lineStyle: { color: t.gridColor } }, axisLabel: { color: t.textColor, fontSize: 10 } },
        subYAxis,
      ],
      dataZoom: [
        { type: "inside", xAxisIndex: [0, 1], start: zoom.start, end: zoom.end },
        { type: "slider", xAxisIndex: [0, 1], bottom: 4, height: 20, labelFormatter: (val: string) => val },
      ],
      series: [
        {
          name: "K", type: "candlestick", data: candle, xAxisIndex: 0, yAxisIndex: 0,
          itemStyle: { color: t.upColor, color0: t.downColor, borderColor: t.upColor, borderColor0: t.downColor },
          markPoint: marks.length > 0 ? { data: marks, symbolSize: 28, tooltip: { formatter: (p: { name?: string; value?: string }) => p.name || p.value || "" } } : undefined,
        },
        ...overlaySeries,
        ...subSeries,
      ],
    }, true);
  }, [visibleData, markers, baseData, indicatorCache, sub, overlays, period, dark]);

  if (visibleData.length === 0) {
    return <div className="text-muted-foreground text-sm p-4">{i18n.t("charts.noPriceData")}</div>;
  }

  return (
    <div>
      <div className="flex items-center gap-2 mb-1 flex-wrap">
        <div className="flex gap-0.5 flex-wrap">
          {periods.map((p) => (
            <button key={p} onClick={() => onViewChange({ period: p })} className={cn("px-1.5 py-0.5 rounded text-[10px] font-mono transition-colors", effectivePeriod === p ? "bg-primary/15 text-primary font-medium" : "text-muted-foreground/50 hover:text-muted-foreground")}>{p}</button>
          ))}
        </div>

        <div className="w-px h-3 bg-border/40" />

        <div className="relative">
          <button
            onClick={() => setShowMenu(!showMenu)}
            className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            Indicators ({overlaySet.size}) <ChevronDown className="h-3 w-3" />
          </button>
          {showMenu && (
            <div className="absolute top-full left-0 mt-1 z-50 bg-card border rounded-lg shadow-lg p-2 min-w-[160px]" onMouseLeave={() => setShowMenu(false)}>
              {["MA", "Channel"].map(group => (
                <div key={group}>
                  <p className="text-[9px] text-muted-foreground/50 uppercase tracking-wider px-1 pt-1">{group}</p>
                  {OVERLAY_OPTIONS.filter(o => o.group === group).map(o => (
                    <label key={o.id} className="flex items-center gap-2 px-1 py-0.5 rounded hover:bg-muted/30 cursor-pointer">
                      <input type="checkbox" checked={overlaySet.has(o.id)} onChange={() => toggleOverlay(o.id)} className="h-3 w-3 rounded accent-primary" />
                      <span className="text-xs">{o.label}</span>
                    </label>
                  ))}
                </div>
              ))}
              <div className="border-t mt-1 pt-1">
                <button onClick={() => { onViewChange({ overlays: [] }); setShowMenu(false); }} className="text-[10px] text-muted-foreground hover:text-foreground px-1 py-0.5 w-full text-left rounded hover:bg-muted/30">
                  Bare K (clear all)
                </button>
              </div>
            </div>
          )}
        </div>

        <div className="w-px h-3 bg-border/40" />

        <div className="flex gap-0.5">
          {(["vol", "macd", "rsi", "kdj"] as const).map((id) => (
            <button key={id} onClick={() => onViewChange({ sub: id })} className={cn("px-1.5 py-0.5 rounded text-[10px] font-mono uppercase transition-colors", sub === id ? "bg-primary/15 text-primary font-medium" : "text-muted-foreground/50 hover:text-muted-foreground")}>{id}</button>
          ))}
        </div>
      </div>
      <div ref={containerRef} style={{ height }} />
    </div>
  );
}
