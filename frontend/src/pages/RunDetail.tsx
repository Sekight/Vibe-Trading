import i18n from '@/i18n';
import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useParams, useNavigate } from "react-router";
import {
  AlertTriangle,
  ArrowLeft,
  BarChart3,
  CheckCircle2,
  Code2,
  Copy,
  Database,
  Download,
  FileCheck2,
  Fingerprint,
  List,
  Loader2,
  ShieldCheck,
  XCircle,
  CircleSlash,
  ChartScatter,
  FileText,
} from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { DEFAULT_CHART_VIEW, type ChartView, type ZoomWindow } from "@/lib/chartWindow";
import { api, type BacktestMetrics, type RunAnalysis, type RunAnalysisCharts, type RunCard, type RunData, type ValidationData } from "@/lib/api";
import ReactMarkdown from "react-markdown";
import rehypeHighlight from "rehype-highlight";
import remarkGfm from "remark-gfm";
import { CandlestickChart } from "@/components/charts/CandlestickChart";
import { tradeActionInfo, type TradeKind } from "@/lib/tradeActions";
import { EquityChart } from "@/components/charts/EquityChart";
import { MetricsCard } from "@/components/chat/MetricsCard";
import { ValidationPanel } from "@/components/charts/ValidationPanel";
import { Skeleton, SkeletonMetrics, SkeletonChart } from "@/components/common/Skeleton";
import { ErrorBoundary } from "@/components/common/ErrorBoundary";
import { getChartTheme } from "@/lib/chart-theme";
import { echarts } from "@/lib/echarts";
import { useThemeDark } from "@/lib/theme-store";
import type { EChartsCoreOption } from "echarts/core";

const rehypePlugins = [rehypeHighlight];
const remarkPlugins = [remarkGfm];

const analysisProseClassName =
  "prose prose-sm dark:prose-invert max-w-none text-[15px] leading-relaxed " +
  "prose-p:text-[15px] prose-p:leading-[1.75] prose-p:my-3 " +
  "prose-headings:font-sans prose-headings:font-semibold prose-headings:text-foreground " +
  "prose-h1:text-2xl prose-h1:mt-6 prose-h1:mb-3 " +
  "prose-h2:text-xl prose-h2:mt-6 prose-h2:mb-3 " +
  "prose-h3:text-lg prose-h3:mt-5 prose-h3:mb-2 " +
  "prose-h4:text-base prose-h4:mt-5 prose-h4:mb-2 " +
  "prose-li:my-1.5 prose-ul:my-3 prose-ol:my-3 prose-table:my-4 " +
  "prose-blockquote:my-4 prose-code:font-mono prose-pre:my-4 prose-hr:my-6";

type Tab = "chart" | "analysisCharts" | "analysis" | "trades" | "runCard" | "code" | "validation";
type ChartPayload = Pick<RunData, "price_series" | "indicator_series" | "trade_markers">;
type ChartCache = Record<string, ChartPayload>;
type ChartLoadProgress = { done: number; total: number };

function downloadCsv(filename: string, csvContent: string) {
  const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function escapeCsvField(value: unknown): string {
  const str = String(value ?? "");
  if (str.includes(",") || str.includes('"') || str.includes("\n")) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function buildTradesCsv(trades: Array<Record<string, string>>): string {
  if (trades.length === 0) return "";
  const keys = [...new Set(trades.flatMap(Object.keys))];
  const header = keys.map(escapeCsvField).join(",");
  const rows = trades.map(tr => keys.map(k => escapeCsvField(tr[k])).join(","));
  return [header, ...rows].join("\n");
}

function buildMetricsCsv(metrics: BacktestMetrics): string {
  const header = "metric,value";
  const rows = Object.entries(metrics).map(([k, v]) => `${escapeCsvField(k)},${escapeCsvField(v)}`);
  return [header, ...rows].join("\n");
}

function cacheFromRun(run: RunData | null, requestedSymbol?: string): ChartCache {
  if (!run?.price_series) return {};
  const cache: ChartCache = {};
  const markerRows = run.trade_markers || [];
  for (const [symbol, bars] of Object.entries(run.price_series)) {
    cache[symbol] = {
      price_series: { [symbol]: bars },
      indicator_series: run.indicator_series?.[symbol] ? { [symbol]: run.indicator_series[symbol] } : {},
      trade_markers: markerRows.filter((marker) => !marker.code || marker.code === symbol),
    };
  }
  if (requestedSymbol && !cache[requestedSymbol]) {
    cache[requestedSymbol] = { price_series: {}, indicator_series: {}, trade_markers: [] };
  }
  return cache;
}

function yieldToBrowser(): Promise<void> {
  return new Promise((resolve) => {
    window.setTimeout(resolve, 0);
  });
}

export function RunDetail() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [run, setRun] = useState<RunData | null>(null);
  const [code, setCode] = useState<Record<string, string>>({});
  const [tab, setTab] = useState<Tab>("chart");
  const [chartView, setChartView] = useState<ChartView>(DEFAULT_CHART_VIEW);
  // 可视窗口走 run 级 ref：拖动只更新 ref 不触发重渲染（避免与 setOption 打架），run 切换时重置。
  const chartWindowRef = useRef<ZoomWindow | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedSymbol, setSelectedSymbol] = useState("");
  const [chartPickerSymbol, setChartPickerSymbol] = useState("");
  const [selectedSymbols, setSelectedSymbols] = useState<string[]>([]);
  const [chartCache, setChartCache] = useState<ChartCache>({});
  const [chartLoadingSymbols, setChartLoadingSymbols] = useState<Record<string, boolean>>({});
  const [bulkChartLoading, setBulkChartLoading] = useState(false);
  const [bulkChartProgress, setBulkChartProgress] = useState<ChartLoadProgress>({ done: 0, total: 0 });
  const chartCacheRef = useRef<ChartCache>({});
  const cancelBulkChartLoadRef = useRef(false);
  const runGenerationRef = useRef(0);

  const hasValidation = !!run?.validation;
  const hasRunCard = !!run?.run_card;
  const TABS: { id: Tab; label: string; icon: typeof BarChart3; hidden?: boolean }[] = [
    { id: "chart", label: i18n.t("runDetail.chart"), icon: BarChart3 },
    { id: "analysisCharts", label: i18n.t("runDetail.analysisCharts"), icon: ChartScatter },
    { id: "analysis", label: i18n.t("runDetail.analysis"), icon: FileText },
    { id: "trades", label: i18n.t("runDetail.trades"), icon: List },
    { id: "runCard", label: i18n.t("runDetail.runCard"), icon: FileCheck2, hidden: !hasRunCard },
    { id: "code", label: i18n.t("runDetail.code"), icon: Code2 },
    { id: "validation", label: i18n.t("runDetail.validation"), icon: ShieldCheck, hidden: !hasValidation },
  ];

  useEffect(() => {
    const generation = ++runGenerationRef.current;
    cancelBulkChartLoadRef.current = true;
    setRun(null);
    setCode({});
    setTab("chart");
    setChartView(DEFAULT_CHART_VIEW);
    chartWindowRef.current = null;
    setLoading(true);
    setSelectedSymbol("");
    setChartPickerSymbol("");
    setSelectedSymbols([]);
    chartCacheRef.current = {};
    setChartCache({});
    setChartLoadingSymbols({});
    setBulkChartLoading(false);
    setBulkChartProgress({ done: 0, total: 0 });

    if (!runId) {
      setLoading(false);
      return;
    }

    const requestedRunId = runId;
    Promise.all([
      api.getRun(requestedRunId, { chart_payload: "summary" }).catch(() => null),
      api.getRunCode(requestedRunId).catch(() => ({})),
    ]).then(([r, c]) => {
      if (runGenerationRef.current !== generation) return;
      setRun(r);
      setCode(c || {});
      const firstSymbol = r?.chart_symbols?.[0] || Object.keys(r?.price_series || {})[0] || "";
      setSelectedSymbol(firstSymbol);
      setChartPickerSymbol(firstSymbol);
      setSelectedSymbols(firstSymbol ? [firstSymbol] : []);
      const initialCache = cacheFromRun(r, firstSymbol);
      chartCacheRef.current = initialCache;
      setChartCache(initialCache);
      if (firstSymbol && !initialCache[firstSymbol]?.price_series?.[firstSymbol]?.length) {
        void loadChartSymbol(firstSymbol, requestedRunId, generation);
      }
    }).finally(() => {
      if (runGenerationRef.current === generation) setLoading(false);
    });

    return () => {
      cancelBulkChartLoadRef.current = true;
      if (runGenerationRef.current === generation) runGenerationRef.current += 1;
    };
  }, [runId]);

  if (loading) {
    return (
      <div className="p-8 space-y-4">
        <Skeleton className="h-6 w-48" />
        <SkeletonMetrics />
        <SkeletonChart height={400} />
      </div>
    );
  }
  if (!run) return (
    <div className="p-8 space-y-2">
      <p className="text-red-500 font-medium">{i18n.t("runDetail.runNotFound")}</p>
      <p className="text-sm text-muted-foreground">
        {i18n.t("runDetail.runNotFoundDesc")}
      </p>
      <button
        onClick={() => navigate(-1)}
        className="text-sm text-primary hover:underline inline-flex items-center gap-1.5"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> {i18n.t("runDetail.goBack")}
      </button>
    </div>
  );

  const ok = run.status === "success";
  const cancelled = run.status === "cancelled";

  async function loadChartSymbol(
    symbol: string,
    requestedRunId = runId,
    generation = runGenerationRef.current,
  ) {
    if (!requestedRunId || !symbol || runGenerationRef.current !== generation) return;
    if (chartCacheRef.current[symbol]?.price_series?.[symbol]?.length) return;
    setChartLoadingSymbols((prev) => ({ ...prev, [symbol]: true }));
    try {
      const nextRun = await api.getRun(requestedRunId, { chart_symbol: symbol });
      if (runGenerationRef.current !== generation) return;
      const nextCache = cacheFromRun(nextRun, symbol);
      const mergedCache = { ...chartCacheRef.current, ...nextCache };
      chartCacheRef.current = mergedCache;
      setChartCache(mergedCache);
      setRun((prev) => prev ? {
        ...prev,
        chart_symbols: nextRun.chart_symbols?.length ? nextRun.chart_symbols : prev.chart_symbols,
        equity_curve: nextRun.equity_curve?.length ? nextRun.equity_curve : prev.equity_curve,
        trade_log: nextRun.trade_log?.length ? nextRun.trade_log : prev.trade_log,
      } : nextRun);
    } finally {
      if (runGenerationRef.current === generation) {
        setChartLoadingSymbols((prev) => {
          const next = { ...prev };
          delete next[symbol];
          return next;
        });
      }
    }
  }

  async function handleAddChartSymbol(symbol: string) {
    if (!symbol) return;
    setSelectedSymbol(symbol);
    setChartPickerSymbol(symbol);
    setSelectedSymbols((prev) => prev.includes(symbol) ? prev : [...prev, symbol]);
    await loadChartSymbol(symbol);
  }

  async function handleCurrentChartOnly(symbol: string) {
    if (!symbol) return;
    setSelectedSymbol(symbol);
    setChartPickerSymbol(symbol);
    setSelectedSymbols([symbol]);
    await loadChartSymbol(symbol);
  }

  function handleRemoveChartSymbol(symbol: string) {
    const nextSymbols = selectedSymbols.filter((item) => item !== symbol);
    setSelectedSymbols(nextSymbols);
    if (selectedSymbol === symbol) {
      const fallback = nextSymbols[0] || run?.chart_symbols?.[0] || "";
      setSelectedSymbol(fallback);
      setChartPickerSymbol(fallback);
    }
  }

  async function handleLoadAllChartSymbols() {
    const symbols = run?.chart_symbols || [];
    if (symbols.length === 0 || bulkChartLoading) return;
    const generation = runGenerationRef.current;
    const requestedRunId = runId;
    cancelBulkChartLoadRef.current = false;
    setBulkChartLoading(true);
    setBulkChartProgress({ done: 0, total: symbols.length });
    try {
      for (let index = 0; index < symbols.length; index += 1) {
        if (cancelBulkChartLoadRef.current || runGenerationRef.current !== generation) break;
        const symbol = symbols[index];
        setSelectedSymbol(symbol);
        setChartPickerSymbol(symbol);
        setSelectedSymbols((prev) => prev.includes(symbol) ? prev : [...prev, symbol]);
        await loadChartSymbol(symbol, requestedRunId, generation);
        if (runGenerationRef.current !== generation) break;
        setBulkChartProgress({ done: index + 1, total: symbols.length });
        await yieldToBrowser();
      }
    } finally {
      if (runGenerationRef.current === generation) setBulkChartLoading(false);
    }
  }

  function handleCancelLoadAllCharts() {
    cancelBulkChartLoadRef.current = true;
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border/60 p-4 space-y-3">
        <div className="flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="p-1 rounded-md hover:bg-muted/60 transition-colors text-muted-foreground hover:text-foreground"
            title={i18n.t("runDetail.goBack")}
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          {ok ? (
            <>
              <CheckCircle2 className="h-5 w-5 text-success" aria-hidden="true" />
              <span className="sr-only">{t("swarm.status.completed")}</span>
            </>
          ) : cancelled ? (
            <>
              <CircleSlash className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
              <span className="sr-only">{t("swarm.status.cancelled")}</span>
            </>
          ) : (
            <>
              <XCircle className="h-5 w-5 text-danger" aria-hidden="true" />
              <span className="sr-only">{t("swarm.status.failed")}</span>
            </>
          )}
          <h1 className="font-mono text-2xl font-semibold">{runId}</h1>
          {run.elapsed_seconds && <span className="text-xs text-muted-foreground">{run.elapsed_seconds.toFixed(1)}s</span>}
        </div>
        {run.prompt && <p className="text-sm text-muted-foreground">{run.prompt}</p>}
        {run.metrics && <MetricsCard metrics={run.metrics as Record<string, number>} />}

        <div className="flex flex-wrap items-center gap-1">
          <div role="tablist" className="flex flex-wrap items-center gap-1">
            {TABS.filter(tabItem => !tabItem.hidden).map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                role="tab"
                aria-selected={tab === id}
                onClick={() => setTab(id)}
                className={cn(
                  "flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm transition-colors",
                  tab === id ? "bg-primary/10 text-primary font-medium" : "text-muted-foreground hover:bg-muted/60"
                )}
              >
                <Icon className="h-3.5 w-3.5" aria-hidden="true" /> {label}
              </button>
            ))}
          </div>

          <div className="ml-auto flex flex-wrap gap-1">
            {run.trade_log && run.trade_log.length > 0 && (
              <button
                onClick={() => downloadCsv(`trades_${runId}.csv`, buildTradesCsv(run.trade_log!))}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs text-muted-foreground hover:bg-muted/60 transition-colors"
                title={i18n.t("runDetail.downloadTradesCsv")}
              >
                <Download className="h-3.5 w-3.5" /> {i18n.t("runDetail.downloadTradesCsv")}
              </button>
            )}
            {run.metrics && (
              <button
                onClick={() => downloadCsv(`metrics_${runId}.csv`, buildMetricsCsv(run.metrics!))}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs text-muted-foreground hover:bg-muted/60 transition-colors"
                title={i18n.t("runDetail.downloadMetricsCsv")}
              >
                <Download className="h-3.5 w-3.5" /> {i18n.t("runDetail.downloadMetricsCsv")}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-auto">
        <ErrorBoundary>
          {/* ChartTab 保持挂载：切换标签不卸载图表，保留副图/指标/周期与可视窗口；非图表标签时隐藏 */}
          <div className={tab === "chart" ? "" : "hidden"}>
            <ChartTab
              run={run}
              chartPickerSymbol={chartPickerSymbol}
              selectedSymbols={selectedSymbols}
              chartCache={chartCache}
              loadingSymbols={chartLoadingSymbols}
              bulkLoading={bulkChartLoading}
              bulkProgress={bulkChartProgress}
              chartView={chartView}
              onChartViewChange={setChartView}
              chartWindowRef={chartWindowRef}
              onPickSymbol={setChartPickerSymbol}
              onAddSymbol={handleAddChartSymbol}
              onCurrentOnly={handleCurrentChartOnly}
              onRemoveSymbol={handleRemoveChartSymbol}
              onLoadAll={handleLoadAllChartSymbols}
              onCancelLoadAll={handleCancelLoadAllCharts}
            />
          </div>
          {tab === "analysisCharts" && runId && <AnalysisChartsTab runId={runId} />}
          {tab === "analysis" && runId && <AnalysisTab runId={runId} />}
          {tab === "trades" && <TradesTab run={run} />}
          {tab === "validation" && run.validation && <ValidationPanel data={run.validation} />}
          {tab === "runCard" && run.run_card && <RunCardTab card={run.run_card} />}
          {tab === "code" && <CodeTab code={code} />}
        </ErrorBoundary>
      </div>
    </div>
  );
}

function RunCardTab({ card }: { card: RunCard }) {
  const backtest = card.backtest || {};
  const reproducibility = card.reproducibility || {};
  const metrics = card.metrics || {};
  const artifacts = card.artifacts || [];
  const warnings = card.warnings || [];
  const dataSources = card.data_sources || [];

  return (
    <div className="p-4 space-y-4">
      <div className="grid gap-3 md:grid-cols-4">
        <RunCardStat label={i18n.t("runDetail.schema")} value={card.schema_version || i18n.t("runDetail.unknown" as any)} />
        <RunCardStat label={i18n.t("runDetail.generated")} value={formatRunCardValue(card.generated_at)} />
        <RunCardStat label={i18n.t("runDetail.dataSources")} value={dataSources.length ? dataSources.join(", ") : i18n.t("runDetail.noneRecorded" as any)} />
        <RunCardStat label={i18n.t("runDetail.warnings")} value={String(warnings.length)} tone={warnings.length ? "warning" : "normal"} />
      </div>

      {warnings.length > 0 && (
        <section className="rounded-xl border border-warning/25 bg-warning/5 p-4 shadow-sm">
          <div className="mb-2 flex items-center gap-2 text-sm font-medium text-warning">
            <AlertTriangle className="h-4 w-4" />
            {i18n.t("runDetail.warnings")}
          </div>
          <ul className="space-y-1 text-xs text-muted-foreground">
            {warnings.map((warning, index) => <li key={index}>{warning}</li>)}
          </ul>
        </section>
      )}

      <div className="grid gap-4 xl:grid-cols-2">
        <RunCardPanel title={i18n.t("runDetail.backtestSummary")} icon={Database}>
          <KeyValueTable data={backtest} empty={i18n.t("runDetail.noBacktestSummary")} />
        </RunCardPanel>
        <RunCardPanel title={i18n.t("runDetail.reproducibility")} icon={Fingerprint}>
          <KeyValueTable data={reproducibility} empty={i18n.t("runDetail.noReproducibilityHashes")} monospaceValues />
        </RunCardPanel>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <RunCardPanel title={i18n.t("runDetail.metrics")} icon={BarChart3}>
          <KeyValueTable data={metrics} empty={i18n.t("runDetail.noScalarMetrics")} />
        </RunCardPanel>
        <RunCardPanel title={i18n.t("runDetail.validationPayload")} icon={ShieldCheck}>
          {card.validation ? (
            hasStructuredValidation(card.validation) ? (
              <ValidationPanel data={card.validation as unknown as ValidationData} compact />
            ) : (
              <pre className="max-h-80 overflow-auto rounded-md bg-muted/40 p-3 text-xs leading-relaxed">
                {JSON.stringify(card.validation, null, 2)}
              </pre>
            )
          ) : (
            <p className="text-sm text-muted-foreground">{i18n.t("runDetail.noValidationPayload")}</p>
          )}
        </RunCardPanel>
      </div>

      <RunCardPanel title={i18n.t("runDetail.artifactChecksums")} icon={FileCheck2}>
        {artifacts.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b bg-muted/40 text-left text-[11px] uppercase tracking-wide text-muted-foreground [&_th]:font-medium">
                  <th className="py-2 ps-4 pr-4">{i18n.t("runDetail.path")}</th>
                  <th className="py-2 pr-4">{i18n.t("runDetail.size")}</th>
                  <th className="py-2">{i18n.t("runDetail.sha256")}</th>
                </tr>
              </thead>
              <tbody>
                {artifacts.map((artifact) => (
                  <tr key={`${artifact.path}-${artifact.sha256}`} className="border-b last:border-0 hover:bg-muted/40">
                    <td className="py-2 ps-4 pr-4 font-mono text-xs">{artifact.path}</td>
                    <td className="py-2 pr-4 font-mono tabular-nums text-muted-foreground">{formatBytes(artifact.size_bytes)}</td>
                    <td className="py-2 font-mono text-xs text-muted-foreground">{shortHash(artifact.sha256)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{i18n.t("runDetail.noArtifactChecksums")}</p>
        )}
      </RunCardPanel>
    </div>
  );
}

function RunCardStat({ label, value, tone = "normal" }: { label: string; value: string; tone?: "normal" | "warning" }) {
  return (
    <div className="rounded-xl border border-border/60 bg-card p-4 shadow-sm">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div className={cn("mt-1 truncate text-sm font-medium", tone === "warning" ? "text-warning" : "")}>{value}</div>
    </div>
  );
}

function RunCardPanel({ title, icon: Icon, children }: { title: string; icon: typeof FileCheck2; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-border/60 bg-card p-4 shadow-sm">
      <div className="mb-3 flex items-center gap-2 text-sm font-semibold">
        <Icon className="h-4 w-4 text-muted-foreground" />
        {title}
      </div>
      {children}
    </section>
  );
}

function KeyValueTable({ data, empty, monospaceValues = false }: { data: Record<string, unknown>; empty: string; monospaceValues?: boolean }) {
  const entries = Object.entries(data).filter(([, value]) => value !== undefined && value !== null && value !== "");
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">{empty}</p>;
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full table-fixed text-sm">
        <tbody>
          {entries.map(([key, value]) => (
            <tr key={key} className="border-b last:border-0 hover:bg-muted/40">
              <td className="w-36 py-2 ps-4 pr-4 align-top text-muted-foreground">{key}</td>
              <td className={cn("py-2 align-top", monospaceValues ? "break-all font-mono text-xs" : "break-words text-right tabular-nums")}>{formatRunCardValue(value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function hasStructuredValidation(value: unknown): boolean {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return Boolean(v.monte_carlo || v.bootstrap || v.walk_forward);
}

function formatRunCardValue(value: unknown): string {
  if (Array.isArray(value)) return value.join(", ");
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(4);
  if (typeof value === "object" && value !== null) return JSON.stringify(value);
  return String(value ?? "");
}

function formatBytes(value: number): string {
  if (!Number.isFinite(value)) return "-";
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function shortHash(value: string): string {
  return value.length > 16 ? `${value.slice(0, 12)}...${value.slice(-6)}` : value;
}

function ChartTab({
  run,
  chartPickerSymbol,
  selectedSymbols,
  chartCache,
  loadingSymbols,
  bulkLoading,
  bulkProgress,
  chartView,
  onChartViewChange,
  chartWindowRef,
  onPickSymbol,
  onAddSymbol,
  onCurrentOnly,
  onRemoveSymbol,
  onLoadAll,
  onCancelLoadAll,
}: {
  run: RunData;
  chartPickerSymbol: string;
  selectedSymbols: string[];
  chartCache: ChartCache;
  loadingSymbols: Record<string, boolean>;
  bulkLoading: boolean;
  bulkProgress: ChartLoadProgress;
  chartView: ChartView;
  onChartViewChange: (patch: React.SetStateAction<ChartView>) => void;
  chartWindowRef: React.MutableRefObject<ZoomWindow | null>;
  onPickSymbol: (symbol: string) => void;
  onAddSymbol: (symbol: string) => void | Promise<void>;
  onCurrentOnly: (symbol: string) => void | Promise<void>;
  onRemoveSymbol: (symbol: string) => void;
  onLoadAll: () => void | Promise<void>;
  onCancelLoadAll: () => void;
}) {
  const chartSymbols = run.chart_symbols || Object.keys(run.price_series || {});
  // markers 用 useMemo 稳定引用：避免窗口拖动等无关重渲染时 .filter 生成新数组，
  // 触发 CandlestickChart 的 setOption 效应重跑（拖动被打断的回归根因）。
  const chartEntries = useMemo(() => selectedSymbols
    .filter((symbol) => (chartCache[symbol]?.price_series?.[symbol] || []).length > 0)
    .map((symbol) => ({
      symbol,
      bars: chartCache[symbol]?.price_series?.[symbol] || [],
      markers: chartCache[symbol]?.trade_markers?.filter((m) => m.code === symbol),
    })),
  [selectedSymbols, chartCache]);
  const hasEquity = run.equity_curve && run.equity_curve.length > 0;
  const progressPercent = bulkProgress.total > 0 ? Math.round((bulkProgress.done / bulkProgress.total) * 100) : 0;

  if (chartSymbols.length === 0 && chartEntries.length === 0 && !hasEquity) {
    return (
      <div className="p-8 text-center text-muted-foreground space-y-2">
        <p className="text-sm">{i18n.t("runDetail.noChartData")}</p>
        <p className="text-xs">{i18n.t("runDetail.noChartDataDesc")}</p>
      </div>
    );
  }

  return (
    <div className="p-4 space-y-4">
      {chartSymbols.length > 0 && (
        <div className="rounded-xl border border-border/60 bg-card p-4 shadow-sm">
          <div className="flex flex-wrap items-center gap-2">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="chart-symbol-select">
              {i18n.t("runDetail.symbol")}
            </label>
            <select
              id="chart-symbol-select"
              value={chartPickerSymbol}
              onChange={(event) => onPickSymbol(event.target.value)}
              className="h-8 rounded-md border border-border/60 bg-background px-2 text-sm"
            >
              {chartSymbols.map((symbol) => (
                <option key={symbol} value={symbol}>{symbol}</option>
              ))}
            </select>
            <button
              onClick={() => onCurrentOnly(chartPickerSymbol)}
              className="rounded-md border border-border/60 px-3 py-1.5 text-xs font-medium hover:bg-muted/60"
              disabled={!chartPickerSymbol || !!loadingSymbols[chartPickerSymbol]}
            >
              {loadingSymbols[chartPickerSymbol] ? <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" /> : null}
              {i18n.t("runDetail.showOnly")}
            </button>
            <button
              onClick={() => onAddSymbol(chartPickerSymbol)}
              className="rounded-md border border-border/60 px-3 py-1.5 text-xs font-medium hover:bg-muted/60"
              disabled={!chartPickerSymbol || !!loadingSymbols[chartPickerSymbol]}
            >
              {i18n.t("runDetail.addSymbol")}
            </button>
            <button
              onClick={() => void onLoadAll()}
              className="rounded-md border border-border/60 px-3 py-1.5 text-xs font-medium hover:bg-muted/60"
              disabled={bulkLoading}
            >
              {bulkLoading ? <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" /> : null}
              {i18n.t("runDetail.loadAll")}
            </button>
            {bulkLoading && (
              <button
                onClick={onCancelLoadAll}
                className="rounded-md border border-border/60 px-3 py-1.5 text-xs font-medium hover:bg-muted/60"
              >
                {i18n.t("runDetail.cancelLoad")}
              </button>
            )}
          </div>
          {selectedSymbols.length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2">
              {selectedSymbols.map((symbol) => (
                <button
                  key={symbol}
                  onClick={() => onRemoveSymbol(symbol)}
                  className="rounded-md bg-muted/40 px-2 py-1 text-xs hover:bg-muted/60"
                >
                  {symbol} x
                </button>
              ))}
            </div>
          )}
          {bulkLoading && (
            <div className="mt-3 space-y-1">
              <div className="flex justify-between text-xs text-muted-foreground">
                <span>{i18n.t("runDetail.loadingCharts")}</span>
                <span>{bulkProgress.done}/{bulkProgress.total}</span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-muted">
                <div className="h-full bg-primary transition-all" style={{ width: `${progressPercent}%` }} />
              </div>
            </div>
          )}
        </div>
      )}
      {chartEntries.length === 0 && (
        <div className="rounded-xl border border-dashed border-border/60 bg-card p-5 text-center text-sm text-muted-foreground shadow-sm">
          {Object.keys(loadingSymbols).length > 0 ? i18n.t("runDetail.loadingSelectedChart") : i18n.t("runDetail.pickSymbolToLoad")}
        </div>
      )}
      {chartEntries.map(({ symbol, bars, markers }) => (
        <div key={symbol}>
          <h3 className="text-sm font-semibold text-muted-foreground mb-1">{symbol}</h3>
          <CandlestickChart data={bars} markers={markers} indicators={chartCache[symbol]?.indicator_series?.[symbol]} height={500} baseInterval={String((run.run_card?.backtest as Record<string, unknown> | undefined)?.interval ?? "")} sub={chartView.sub} overlays={chartView.overlays} period={chartView.period} windowRef={chartWindowRef} onViewChange={(patch) => onChartViewChange((prev) => ({ ...prev, ...patch }))} />
        </div>
      ))}
      {hasEquity && (
        <div>
          <h3 className="text-sm font-semibold text-muted-foreground mb-1">{i18n.t("runDetail.equityDrawdown")}</h3>
          <EquityChart data={run.equity_curve!} height={280} />
        </div>
      )}
    </div>
  );
}

const TRADES_PAGE_SIZE = 100;


function parseTradeNumber(value?: string): number | null {
  if (value == null || value === "") return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function isAShareCode(code?: string): boolean {
  return !!code && /\.(SH|SZ|BJ)$/i.test(code.trim());
}

function tradeLots(tr: Record<string, string>, qty: number | null): number | null {
  if (tr.lots != null && tr.lots !== "") {
    const lots = parseTradeNumber(tr.lots);
    if (lots != null) return lots;
  }
  return qty != null && isAShareCode(tr.code) ? qty / 100 : null;
}

function tradePositionWeight(
  tr: Record<string, string>,
  run: RunData,
  qty: number | null,
  price: number | null,
): number | null {
  if (tr.position_weight != null && tr.position_weight !== "") {
    const weight = parseTradeNumber(tr.position_weight);
    if (weight != null) return weight;
  }
  if (qty == null || price == null) return null;
  const ts = tr.time || tr.timestamp;
  if (!ts) return null;
  const point = (run.equity_curve || []).find((p) => p.time === ts);
  if (!point) return null;
  const equity = Number(point.equity);
  if (!Number.isFinite(equity) || equity <= 0) return null;
  return (qty * price) / equity;
}

function signedNumberClass(value: number | null): string {
  if (value == null || value === 0) return "text-muted-foreground";
  return value > 0 ? "text-success" : "text-danger";
}

function formatSigned(value: number, suffix = ""): string {
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}${suffix}`;
}

function TradesTab({ run }: { run: RunData }) {
  const trades = run.trade_log || [];
  const [sideFilter, setSideFilter] = useState<"" | TradeKind>("");
  const [symbolFilter, setSymbolFilter] = useState("");
  const [visibleCount, setVisibleCount] = useState(TRADES_PAGE_SIZE);
  if (trades.length === 0) return <div className="p-8 text-muted-foreground text-sm">{i18n.t("runDetail.noTrades")}</div>;

  const kindOf = (tr: Record<string, string>): TradeKind | null => tradeActionInfo(tr)?.kind ?? null;
  const symbols = [...new Set(trades.map((tr) => tr.code).filter(Boolean))];
  const hasPnl = trades.some((tr) => parseTradeNumber(tr.pnl) != null);
  const hasCommission = trades.some((tr) => (tr.commission ?? "") !== "");
  const hasReturnPct = trades.some((tr) => parseTradeNumber(tr.return_pct) != null);
  const hasHoldingDays = trades.some((tr) => (tr.holding_days ?? "") !== "");
  const hasHoldingBars = trades.some((tr) => (tr.holding_bars ?? "") !== "");
  const hasLots = trades.some((tr) => tradeLots(tr, parseTradeNumber(tr.qty)) != null);
  const hasWeight = trades.some((tr) => (
    tradePositionWeight(tr, run, parseTradeNumber(tr.qty), parseTradeNumber(tr.price)) != null
  ));

  const filtered = trades.filter((tr) => (
    (!sideFilter || kindOf(tr) === sideFilter)
    && (!symbolFilter || tr.code === symbolFilter)
  ));
  const longOpen = filtered.filter((tr) => kindOf(tr) === "long_open").length;
  const shortOpen = filtered.filter((tr) => kindOf(tr) === "short_open").length;
  const longClose = filtered.filter((tr) => kindOf(tr) === "long_close").length;
  const shortClose = filtered.filter((tr) => kindOf(tr) === "short_close").length;
  const totalPnl = hasPnl
    ? filtered.reduce((sum, tr) => sum + (parseTradeNumber(tr.pnl) ?? 0), 0)
    : null;
  const visible = filtered.slice(0, visibleCount);
  const remaining = filtered.length - visible.length;

  const sideChips: { id: "" | TradeKind; label: string }[] = [
    { id: "", label: i18n.t("runDetail.sideAll") },
    { id: "long_open", label: i18n.t("runDetail.sideLongOpen") },
    { id: "short_open", label: i18n.t("runDetail.sideShortOpen") },
    { id: "long_close", label: i18n.t("runDetail.sideLongClose") },
    { id: "short_close", label: i18n.t("runDetail.sideShortClose") },
  ];

  return (
    <div className="p-4 space-y-3">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 text-xs text-muted-foreground">
        <span className="font-medium text-foreground">{i18n.t("runDetail.tradesCount", { count: filtered.length })}</span>
        <span>{i18n.t("runDetail.sideLongOpen")} {longOpen} · {i18n.t("runDetail.sideShortOpen")} {shortOpen} · {i18n.t("runDetail.sideLongClose")} {longClose} · {i18n.t("runDetail.sideShortClose")} {shortClose}</span>
        {totalPnl != null && (
          <span className="inline-flex items-center gap-1">
            {i18n.t("runDetail.totalPnl")}
            <span className={cn("font-mono font-medium tabular-nums", signedNumberClass(totalPnl))}>
              {formatSigned(totalPnl)}
            </span>
          </span>
        )}
        <div className="ms-auto flex flex-wrap items-center gap-1.5">
          <div className="flex gap-1" role="group">
            {sideChips.map((chip) => (
              <button
                key={chip.id || "all"}
                type="button"
                onClick={() => { setSideFilter(chip.id); setVisibleCount(TRADES_PAGE_SIZE); }}
                className={cn(
                  "rounded-full border px-2.5 py-1 transition-colors",
                  sideFilter === chip.id
                    ? "border-primary/30 bg-primary/10 font-medium text-primary"
                    : "border-border/60 hover:bg-muted/60",
                )}
              >
                {chip.label}
              </button>
            ))}
          </div>
          {symbols.length > 1 && (
            <select
              value={symbolFilter}
              onChange={(event) => { setSymbolFilter(event.target.value); setVisibleCount(TRADES_PAGE_SIZE); }}
              className="h-7 rounded-md border border-border/60 bg-background px-2 text-xs"
              aria-label={i18n.t("runDetail.symbol")}
            >
              <option value="">{i18n.t("runDetail.allSymbols")}</option>
              {symbols.map((symbol) => (
                <option key={symbol} value={symbol}>{symbol}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      <div className="overflow-x-auto rounded-xl border border-border/60 bg-card shadow-sm">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/40 text-left text-[11px] uppercase tracking-wide text-muted-foreground [&_th]:font-medium">
              <th className="py-2 ps-4 pr-4">{i18n.t("runDetail.time")}</th>
              <th className="py-2 pr-4">{i18n.t("runDetail.code2")}</th>
              <th className="py-2 pr-4">{i18n.t("runDetail.side")}</th>
              <th className="py-2 pr-4 text-right">{i18n.t("runDetail.price")}</th>
              <th className="py-2 pr-4 text-right">{i18n.t("runDetail.qty")}</th>
              {hasLots && <th className="py-2 pr-4 text-right">{i18n.t("runDetail.lots")}</th>}
              {hasWeight && <th className="py-2 pr-4 text-right">{i18n.t("runDetail.positionWeight")}</th>}
              {hasPnl && <th className="py-2 pr-4 text-right">{i18n.t("runDetail.pnl")}</th>}
              {hasReturnPct && <th className="py-2 pr-4 text-right">{i18n.t("runDetail.returnPct")}</th>}
              {hasCommission && <th className="py-2 pr-4 text-right">{i18n.t("runDetail.commission")}</th>}
              {hasHoldingDays && <th className="py-2 pr-4 text-right">{i18n.t("runDetail.holdingDays")}</th>}
              {hasHoldingBars && <th className="py-2 pr-4 text-right">{i18n.t("runDetail.holdingBars")}</th>}
              <th className="py-2">{i18n.t("runDetail.reason")}</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((tr, i) => {
              const kind = kindOf(tr);
              const pnl = parseTradeNumber(tr.pnl);
              const returnPct = parseTradeNumber(tr.return_pct);
              const price = parseTradeNumber(tr.price);
              const qty = parseTradeNumber(tr.qty);
              return (
                <tr key={i} className={cn("border-b last:border-0 hover:bg-muted/40", i % 2 === 1 && "bg-muted/10")}>
                  <td className="py-2 ps-4 pr-4 font-mono text-xs">{tr.time || tr.timestamp}</td>
                  <td className="py-2 pr-4 font-mono text-xs">{tr.code}</td>
                  <td className="py-2 pr-4">
                    <span className={cn(
                      "inline-block rounded-full px-2 py-0.5 text-xs font-medium",
                      (kind === "long_open" || kind === "short_close") && "bg-danger/10 text-danger",
                      (kind === "short_open" || kind === "long_close") && "bg-success/10 text-success",
                      !kind && "bg-muted text-muted-foreground",
                    )}>
                      {kind === "long_open" ? i18n.t("runDetail.sideLongOpen") : kind === "short_open" ? i18n.t("runDetail.sideShortOpen") : kind === "long_close" ? i18n.t("runDetail.sideLongClose") : kind === "short_close" ? i18n.t("runDetail.sideShortClose") : tr.side}
                    </span>
                  </td>
                  <td className="py-2 pr-4 text-right font-mono tabular-nums">{tr.price}</td>
                  <td className="py-2 pr-4 text-right font-mono tabular-nums">{tr.qty}</td>
                  {hasLots && (
                    <td className="py-2 pr-4 text-right font-mono tabular-nums">
                      {(() => {
                        const lots = tradeLots(tr, qty);
                        return lots != null ? lots.toFixed(2) : "—";
                      })()}
                    </td>
                  )}
                  {hasWeight && (
                    <td className="py-2 pr-4 text-right font-mono tabular-nums">
                      {(() => {
                        const weight = tradePositionWeight(tr, run, qty, price);
                        return weight != null ? `${(weight * 100).toFixed(2)}%` : "—";
                      })()}
                    </td>
                  )}
                  {hasPnl && (
                    <td className={cn("py-2 pr-4 text-right font-mono tabular-nums", signedNumberClass(pnl))}>
                      {pnl != null ? formatSigned(pnl) : "—"}
                    </td>
                  )}
                  {hasReturnPct && (
                    <td className={cn("py-2 pr-4 text-right font-mono tabular-nums", signedNumberClass(returnPct))}>
                      {returnPct != null ? formatSigned(returnPct, "%") : "—"}
                    </td>
                  )}
                  {hasCommission && (
                    <td className="py-2 pr-4 text-right font-mono tabular-nums text-muted-foreground">
                      {(() => {
                        const commission = parseTradeNumber(tr.commission);
                        return commission != null ? commission.toLocaleString(undefined, { maximumFractionDigits: 2 }) : "—";
                      })()}
                    </td>
                  )}
                  {hasHoldingDays && (
                    <td className="py-2 pr-4 text-right font-mono tabular-nums text-muted-foreground">{tr.holding_days ?? "—"}</td>
                  )}
                  {hasHoldingBars && (
                    <td className="py-2 pr-4 text-right font-mono tabular-nums text-muted-foreground">{tr.holding_bars ?? "—"}</td>
                  )}
                  <td className="py-2 text-xs text-muted-foreground">{tr.reason}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {remaining > 0 && (
        <div className="flex justify-center">
          <button
            type="button"
            onClick={() => setVisibleCount((count) => count + TRADES_PAGE_SIZE)}
            className="rounded-full border border-border/60 px-4 py-1.5 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
          >
            {i18n.t("runDetail.showMore", { count: Math.min(remaining, TRADES_PAGE_SIZE) })}
          </button>
        </div>
      )}
    </div>
  );
}

function CodeTab({ code }: { code: Record<string, string> }) {
  const files = Object.entries(code);
  const [active, setActive] = useState(files[0]?.[0] || "");
  if (files.length === 0) return <div className="p-8 text-muted-foreground text-sm">{i18n.t("runDetail.noCodeFiles")}</div>;

  const activeCode = code[active] || "";
  const lineCount = activeCode ? activeCode.split("\n").length : 0;
  const copyActive = () => {
    navigator.clipboard.writeText(activeCode).then(
      () => toast.success(i18n.t("runDetail.codeCopied")),
      () => {},
    );
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 p-2 border-b border-border/60">
        <div className="flex min-w-0 flex-wrap gap-1">
          {files.map(([name]) => (
            <button key={name} onClick={() => setActive(name)} className={cn("px-3 py-1 rounded text-xs font-mono", active === name ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-muted/60")}>{name}</button>
          ))}
        </div>
        <div className="ms-auto flex shrink-0 items-center gap-2">
          <span className="text-[10px] tabular-nums text-muted-foreground">
            {i18n.t("runDetail.codeLines", { count: lineCount })}
          </span>
          <button
            type="button"
            onClick={copyActive}
            className="flex items-center gap-1 rounded-md border border-border/60 px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-muted/60 hover:text-foreground"
          >
            <Copy className="h-3 w-3" /> {i18n.t("runDetail.copyCode")}
          </button>
        </div>
      </div>
      <div className="flex-1 overflow-auto p-3 text-xs leading-relaxed bg-muted/20 [&_pre]:m-0 [&_pre]:bg-transparent [&_code]:text-xs">
        <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>
          {`\`\`\`python\n${activeCode}\n\`\`\``}
        </ReactMarkdown>
      </div>
    </div>
  );
}

const ANALYSIS_RED = "#dc2626";
const ANALYSIS_GREEN = "#16a34a";

const ANALYSIS_CHART_ORDER: Array<{ key: keyof RunAnalysisCharts["charts"]; titleKey: string }> = [
  { key: "equity_return", titleKey: "runDetail.chartEquityReturn" },
  { key: "drawdown", titleKey: "runDetail.chartDrawdown" },
  { key: "pnl_scatter", titleKey: "runDetail.chartPnlScatter" },
  { key: "monthly_heatmap", titleKey: "runDetail.chartMonthlyHeatmap" },
  { key: "pnl_vs_holding", titleKey: "runDetail.chartPnlVsHolding" },
  { key: "mae_mfe", titleKey: "runDetail.chartMaeMfe" },
  { key: "holding_buckets", titleKey: "runDetail.chartHoldingBuckets" },
];

function AnalysisChartsTab({ runId }: { runId: string }) {
  const [data, setData] = useState<RunAnalysisCharts | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pngUrls, setPngUrls] = useState<Record<string, string>>({});
  const generationRef = useRef(0);

  useEffect(() => {
    const generation = ++generationRef.current;
    setLoading(true);
    setError(null);
    setData(null);
    setPngUrls({});
    api.getRunAnalysisCharts(runId)
      .then(async (charts) => {
        if (generationRef.current !== generation) return;
        setData(charts);
        if (charts.available && charts.pngs.length > 0) {
          const urls: Record<string, string> = {};
          await Promise.all(charts.pngs.map(async (png) => {
            try {
              urls[png.key] = await api.fetchRunAnalysisPng(runId, png.filename);
            } catch {
              // PNG is a fallback; keep the slot empty when it cannot load.
            }
          }));
          if (generationRef.current === generation) setPngUrls(urls);
        }
      })
      .catch((err) => {
        if (generationRef.current === generation) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (generationRef.current === generation) setLoading(false);
      });
    return () => { generationRef.current += 1; };
  }, [runId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> {i18n.t("runDetail.loadingAnalysisCharts")}
      </div>
    );
  }
  if (error) return <div className="p-8 text-sm text-red-500">{error}</div>;
  if (!data || !data.available) {
    return (
      <div className="p-8 space-y-1">
        <p className="font-medium text-sm">{i18n.t("runDetail.noAnalysisCharts")}</p>
        <p className="text-sm text-muted-foreground">{i18n.t("runDetail.noAnalysisChartsDesc")}</p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 p-4 lg:grid-cols-2">
      {ANALYSIS_CHART_ORDER.map(({ key, titleKey }) => (
        <AnalysisChartCard key={key} chartKey={key} title={i18n.t(titleKey as any)} payload={data.charts} pngUrl={pngUrls[key]} benchmarkLabel={data.benchmark_label ?? undefined} />
      ))}
    </div>
  );
}

function AnalysisChartCard({
  chartKey,
  title,
  payload,
  pngUrl,
  benchmarkLabel,
}: {
  chartKey: keyof RunAnalysisCharts["charts"];
  title: string;
  payload: RunAnalysisCharts["charts"];
  pngUrl?: string;
  benchmarkLabel?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const dark = useThemeDark();
  const points = payload[chartKey];
  const hasData = Array.isArray(points) && points.length > 0;
  const [heatGranularity, setHeatGranularity] = useState<"day" | "week" | "month">(
    (payload.heatmap_default as "day" | "week" | "month" | undefined) ?? "month"
  );

  useEffect(() => {
    if (!ref.current || !hasData) return;
    const t = getChartTheme();
    const chart = echarts.init(ref.current);
    const nameTextStyle = { color: t.textColor, fontSize: 10, fontWeight: 500 };
    const axis = {
      axisLine: { lineStyle: { color: t.axisColor } },
      axisLabel: { color: t.textColor, fontSize: 10 },
      nameTextStyle,
      nameGap: 18,
    };
    const valueAxis = {
      type: "value",
      splitLine: { lineStyle: { color: t.gridColor } },
      axisLabel: { color: t.textColor, fontSize: 10 },
      nameTextStyle,
      nameGap: 18,
    };
    const tooltip = {
      backgroundColor: t.tooltipBg,
      borderColor: t.tooltipBorder,
      textStyle: { color: t.tooltipText, fontSize: 11 },
    };
    const grid = { left: 18, right: 18, top: 44, bottom: 56, containLabel: true };
    const middleName = { nameLocation: "middle" as const, nameGap: 24 };

    let option: EChartsCoreOption = {};
    if (chartKey === "equity_return" && Array.isArray(points)) {
      const rows = points as Array<{ date: string; value: number; benchmark?: number | null }>;
      const hasBenchmark = rows.some((r) => r.benchmark != null);
      const benchmarkName = benchmarkLabel || i18n.t("runDetail.chartBenchmark" as any);
      option = {
        grid, tooltip: { ...tooltip, trigger: "axis" },
        legend: hasBenchmark ? { top: 0, textStyle: { color: t.textColor, fontSize: 10 } } : undefined,
        xAxis: { type: "category", name: i18n.t("runDetail.chartAxisDate" as any), data: rows.map((r) => r.date), ...axis, ...middleName },
        yAxis: { ...valueAxis, name: i18n.t("runDetail.chartAxisCumReturn" as any) },
        series: [
          {
            type: "line", name: i18n.t("runDetail.chartStrategy" as any), data: rows.map((r) => r.value), showSymbol: false, smooth: true,
            lineStyle: { color: t.infoColor, width: 2 },
            areaStyle: { color: `${t.infoColor}22` },
          },
          ...(hasBenchmark ? [{
            type: "line", name: benchmarkName, data: rows.map((r) => r.benchmark ?? null), showSymbol: false, smooth: true,
            lineStyle: { color: t.warningColor, width: 1.6 }, z: 3,
          }] : []),
        ],
      };
    } else if (chartKey === "drawdown" && Array.isArray(points)) {
      const rows = points as Array<{ date: string; value: number; benchmark?: number | null }>;
      const hasBenchmark = rows.some((r) => r.benchmark != null);
      const benchmarkName = benchmarkLabel || i18n.t("runDetail.chartBenchmark" as any);
      option = {
        grid, tooltip: { ...tooltip, trigger: "axis" },
        legend: hasBenchmark ? { top: 0, textStyle: { color: t.textColor, fontSize: 10 } } : undefined,
        xAxis: { type: "category", name: i18n.t("runDetail.chartAxisDate" as any), data: rows.map((r) => r.date), ...axis, ...middleName },
        yAxis: { ...valueAxis, name: i18n.t("runDetail.chartAxisDrawdown" as any), inverse: true, nameLocation: "start" },
        series: [
          {
            type: "line", name: i18n.t("runDetail.chartStrategy" as any), data: rows.map((r) => r.value), showSymbol: false,
            lineStyle: { color: ANALYSIS_RED, width: 1.4 },
            areaStyle: { color: `${ANALYSIS_RED}44` },
          },
          ...(hasBenchmark ? [{
            type: "line", name: benchmarkName, data: rows.map((r) => r.benchmark ?? null), showSymbol: false,
            lineStyle: { color: t.warningColor, width: 1.4 }, z: 3,
          }] : []),
        ],
      };
    } else if (chartKey === "pnl_scatter" && Array.isArray(points)) {
      const rows = points as Array<{ index: number; entry_ts?: string; code?: string; return_pct?: number; win: boolean }>;
      option = {
        grid, tooltip: { ...tooltip, trigger: "item" },
        xAxis: { ...valueAxis, name: i18n.t("runDetail.chartAxisTradeIndex" as any), ...middleName },
        yAxis: { ...valueAxis, name: i18n.t("runDetail.chartAxisTradePnl" as any) },
        series: [{
          type: "scatter",
          data: rows.map((r) => ({
            value: [r.index, r.return_pct ?? 0],
            itemStyle: { color: r.win ? ANALYSIS_RED : ANALYSIS_GREEN },
          })),
          symbolSize: 9,
        }],
      };
    } else if (chartKey === "monthly_heatmap" && Array.isArray(points)) {
      const periodData = ((payload.period_pnl as Record<string, Array<Record<string, unknown>>> | undefined) ?? {})[heatGranularity] ?? [];
      const rows = periodData.map((r) => ({
        label: heatGranularity === "month"
          ? `${String(r.year).padStart(4, "0")}-${String(r.month).padStart(2, "0")}`
          : String(r.date ?? r.week ?? ""),
        pnl: Number(r.pnl ?? 0),
      }));
      const labels = rows.map((r) => r.label);
      const maxAbs = Math.max(1, ...rows.map((r) => Math.abs(r.pnl)));
      option = {
        grid: { left: 18, right: 18, top: 44, bottom: 80, containLabel: true },
        tooltip: { ...tooltip, trigger: "item", formatter: (params: { data?: { label?: string; pnl?: number } }) => {
          return `${params.data?.label ?? ""}: ${Number(params.data?.pnl ?? 0).toFixed(2)}`;
        } },
        xAxis: { type: "category", data: labels, splitArea: { show: true }, ...axis, ...middleName },
        yAxis: { type: "category", data: ["PnL"], splitArea: { show: true }, ...axis },
        visualMap: {
          min: -maxAbs, max: maxAbs, calculable: true, orient: "horizontal", left: "center", bottom: 24,
          textStyle: { color: t.textColor, fontSize: 10 },
          inRange: { color: [ANALYSIS_GREEN, "#f5f5f5", ANALYSIS_RED] },
        },
        series: [{
          type: "heatmap",
          data: rows.map((r, i) => ({ value: [i, 0, r.pnl], label: r.label, pnl: r.pnl })),
          label: { show: false },
          itemStyle: { borderColor: t.tooltipBg, borderWidth: 1 },
        }],
      };
    } else if (chartKey === "pnl_vs_holding" && Array.isArray(points)) {
      const rows = points as Array<{ holding_days?: number; holding_bars?: number; return_pct?: number; win: boolean }>;
      option = {
        grid, tooltip: { ...tooltip, trigger: "item" },
        xAxis: { ...valueAxis, name: i18n.t("runDetail.chartAxisHoldingDays" as any), ...middleName },
        yAxis: { ...valueAxis, name: i18n.t("runDetail.chartAxisTradePnl" as any) },
        series: [{
          type: "scatter",
          data: rows.map((r) => ({
            value: [r.holding_bars ?? r.holding_days ?? 0, r.return_pct ?? 0],
            itemStyle: { color: r.win ? ANALYSIS_RED : ANALYSIS_GREEN },
          })),
          symbolSize: 9,
        }],
      };
    } else if (chartKey === "mae_mfe" && Array.isArray(points)) {
      const rows = points as Array<{ mae_pct?: number; mfe_pct?: number; win: boolean }>;
      const maxValue = Math.max(1, ...rows.map((r) => Math.max(r.mae_pct ?? 0, r.mfe_pct ?? 0)));
      option = {
        grid, tooltip: { ...tooltip, trigger: "item" },
        xAxis: { ...valueAxis, name: i18n.t("runDetail.chartAxisMae" as any), ...middleName },
        yAxis: { ...valueAxis, name: i18n.t("runDetail.chartAxisMfe" as any) },
        series: [
          {
            type: "scatter",
            data: rows.map((r) => ({
              value: [r.mae_pct ?? 0, r.mfe_pct ?? 0],
              itemStyle: { color: r.win ? ANALYSIS_RED : ANALYSIS_GREEN },
            })),
            symbolSize: 9,
          },
          {
            type: "line", data: [[0, 0], [maxValue, maxValue]], showSymbol: false, silent: true,
            lineStyle: { type: "dashed", color: t.warningColor, width: 1 },
          },
        ],
      };
    } else if (chartKey === "holding_buckets" && Array.isArray(points)) {
      const rows = points as Array<{ bucket: string; avg_return_pct: number; win_rate: number }>;
      option = {
        grid,
        tooltip: { ...tooltip, trigger: "axis" },
        legend: { top: 0, textStyle: { color: t.textColor, fontSize: 10 } },
        xAxis: { type: "category", name: i18n.t("runDetail.chartAxisBucket" as any), data: rows.map((r) => r.bucket), ...axis, ...middleName },
        yAxis: [
          { ...valueAxis, name: i18n.t("runDetail.chartAxisAvgReturn" as any) },
          { ...valueAxis, name: i18n.t("runDetail.chartAxisWinRate" as any), min: 0, max: 105 },
        ],
        series: [
          {
            type: "bar", name: "avg %",
            data: rows.map((r) => ({
              value: r.avg_return_pct,
              itemStyle: { color: r.avg_return_pct >= 0 ? ANALYSIS_RED : ANALYSIS_GREEN },
            })),
          },
          {
            type: "line", name: "win %", yAxisIndex: 1,
            data: rows.map((r) => r.win_rate * 100), showSymbol: true, symbolSize: 6,
            lineStyle: { color: t.infoColor, width: 1.5 },
          },
        ],
      };
    }
    chart.setOption(option);
    const ro = new ResizeObserver(() => chart.resize());
    ro.observe(ref.current!);
    return () => { ro.disconnect(); chart.dispose(); };
  }, [chartKey, points, heatGranularity, dark]);

  return (
    <div className="rounded-md border border-border/60 bg-card p-3">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-medium">{title}</h3>
        {chartKey === "monthly_heatmap" && (
          <div className="flex gap-0.5">
            {(["day", "week", "month"] as const).map((g) => (
              <button key={g} onClick={() => setHeatGranularity(g)} className={cn("px-1.5 py-0.5 rounded text-[10px] font-mono transition-colors", heatGranularity === g ? "bg-primary/15 text-primary font-medium" : "text-muted-foreground/50 hover:text-muted-foreground")}>{i18n.t(`runDetail.heatmap${g === "day" ? "Day" : g === "week" ? "Week" : "Month"}` as any)}</button>
            ))}
          </div>
        )}
      </div>
      {hasData ? (
        <div ref={ref} className="h-72 w-full" />
      ) : pngUrl ? (
        <img src={pngUrl} alt={title} className="h-72 w-full object-contain" />
      ) : (
        <div className="flex h-72 items-center justify-center text-sm text-muted-foreground">
          {i18n.t("runDetail.chartNoData")}
        </div>
      )}
    </div>
  );
}

function AnalysisTab({ runId }: { runId: string }) {
  const [analysis, setAnalysis] = useState<RunAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const generationRef = useRef(0);

  useEffect(() => {
    const generation = ++generationRef.current;
    setLoading(true);
    setError(null);
    setAnalysis(null);
    api.getRunAnalysis(runId)
      .then((result) => { if (generationRef.current === generation) setAnalysis(result); })
      .catch((err) => {
        if (generationRef.current === generation) setError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => { if (generationRef.current === generation) setLoading(false); });
    return () => { generationRef.current += 1; };
  }, [runId]);

  if (loading) {
    return (
      <div className="flex items-center gap-2 p-8 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> {i18n.t("runDetail.loadingAnalysis")}
      </div>
    );
  }
  if (error) return <div className="p-8 text-sm text-red-500">{error}</div>;
  if (!analysis || !analysis.markdown) {
    return (
      <div className="p-8 space-y-1">
        <p className="font-medium text-sm">{i18n.t("runDetail.noAnalysis")}</p>
        <p className="text-sm text-muted-foreground">{i18n.t("runDetail.noAnalysisDesc")}</p>
      </div>
    );
  }

  const status = analysis.status;
  return (
    <div className="space-y-4 p-4">
      {status && (
        <div className="rounded-md border border-border/60 bg-card p-3 text-xs text-muted-foreground">
          <div className="flex flex-wrap gap-x-6 gap-y-1">
            <span><b className="text-foreground">{i18n.t("runDetail.analysisStatus")}:</b> {status.status}</span>
            <span><b className="text-foreground">{i18n.t("runDetail.analysisGeneratedBy")}:</b> {status.generated_by}</span>
            <span><b className="text-foreground">{i18n.t("runDetail.analysisGeneratedAt")}:</b> {status.generated_at}</span>
          </div>
          {status.error && <p className="mt-1 text-red-500">{status.error}</p>}
          {status.llm_usage && (
            <p className="mt-1"><b className="text-foreground">{i18n.t("runDetail.analysisUsage")}:</b> {JSON.stringify(status.llm_usage)}</p>
          )}
        </div>
      )}
      {analysis.benchmark && (
        <div className="rounded-md border border-border/60 bg-card p-3 text-xs text-muted-foreground">
          <div className="flex flex-wrap gap-x-6 gap-y-1">
            <span><b className="text-foreground">{i18n.t("runDetail.benchmarkLabel")}:</b> {analysis.benchmark.label || "-"}</span>
            {analysis.benchmark.ticker && (
              <span><b className="text-foreground">{i18n.t("runDetail.benchmarkTicker")}:</b> {analysis.benchmark.ticker}</span>
            )}
            {analysis.benchmark.return != null && (
              <span><b className="text-foreground">{i18n.t("runDetail.benchmarkReturn")}:</b> {(Number(analysis.benchmark.return) * 100).toFixed(2)}%</span>
            )}
          </div>
        </div>
      )}
      <div className="rounded-md border border-border/60 bg-card p-4 [&_pre]:overflow-auto [&_pre]:rounded [&_pre]:bg-muted/40 [&_pre]:p-2 [&_table]:w-full [&_td]:border [&_td]:border-border/60 [&_td]:p-1 [&_th]:border [&_th]:border-border/60 [&_th]:p-1">
        <div className={analysisProseClassName}>
          <ReactMarkdown remarkPlugins={remarkPlugins} rehypePlugins={rehypePlugins}>{analysis.markdown}</ReactMarkdown>
        </div>
      </div>
    </div>
  );
}
