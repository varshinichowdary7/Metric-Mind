"use client";

import { useEffect, useRef } from "react";

// The agent sends a renderer-agnostic `viz` spec (api/viz.py) derived from the
// governed result's annotation. This component is a thin renderer: it maps that
// spec onto ECharts and formats values by the measure's type. It never decides
// *which* chart to draw — that choice is made (and unit-tested) in Python.

const PALETTE_LIGHT = ["#4457c9", "#6a4fe0", "#2e9e8f", "#d99a2b", "#c9445f", "#3b86d1"];
const PALETTE_DARK = ["#8fa0f2", "#9a86f5", "#54c7b6", "#e6b85c", "#f26a8a", "#6ab0f0"];

function prefersDark() {
  try {
    return window.matchMedia("(prefers-color-scheme: dark)").matches;
  } catch {
    return false;
  }
}

function fmt(value, type) {
  if (typeof value !== "number" || Number.isNaN(value)) return value == null ? "" : String(value);
  if (type === "percent") return `${value.toFixed(1)}%`;
  return new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 }).format(value);
}

// Time axis values arrive as ISO strings ("2025-01-01"); keep just the date.
const label = (v) => String(v ?? "").slice(0, 10);

function buildOption(viz, result, dark) {
  const data = result?.data || [];
  const measures = result?.annotation?.measures || {};
  const title = (m) => measures[m]?.title || m;
  const typeOf = (m) => measures[m]?.type;
  const color = dark ? PALETTE_DARK : PALETTE_LIGHT;
  const ink = dark ? "#a6aebc" : "#48505f";
  const grid = dark ? "#262c37" : "#e3e7ee";

  const axis = {
    axisLine: { lineStyle: { color: grid } },
    axisLabel: { color: ink },
    splitLine: { lineStyle: { color: grid } },
  };
  const base = {
    color,
    textStyle: { color: ink, fontFamily: "inherit" },
    grid: { left: 8, right: 16, top: 28, bottom: 8, containLabel: true },
    legend: { top: 0, textStyle: { color: ink } },
    tooltip: { trigger: viz.chart === "pie" ? "item" : "axis" },
  };

  if (viz.chart === "line" && viz.seriesBy) {
    // Time trend split into one line per category value.
    const xs = [...new Set(data.map((r) => label(r[viz.x])))].sort();
    const groups = [...new Set(data.map((r) => r[viz.seriesBy]))];
    const mtype = typeOf(viz.measure);
    return {
      ...base,
      tooltip: { ...base.tooltip, valueFormatter: (v) => fmt(v, mtype) },
      xAxis: { type: "category", data: xs, ...axis },
      yAxis: { type: "value", axisLabel: { color: ink, formatter: (v) => fmt(v, mtype) }, splitLine: axis.splitLine },
      series: groups.map((g) => ({
        name: String(g),
        type: "line",
        data: xs.map((x) => {
          const row = data.find((r) => label(r[viz.x]) === x && r[viz.seriesBy] === g);
          return row ? row[viz.measure] : null;
        }),
      })),
    };
  }

  if (viz.chart === "line" || viz.chart === "bar") {
    const series = viz.series || [];
    const mtype = typeOf(series[0]);
    const cats = data.map((r) => (viz.xType === "time" ? label(r[viz.x]) : String(r[viz.x])));
    return {
      ...base,
      tooltip: { ...base.tooltip, valueFormatter: (v) => fmt(v, mtype) },
      xAxis: { type: "category", data: cats, ...axis },
      yAxis: { type: "value", axisLabel: { color: ink, formatter: (v) => fmt(v, mtype) }, splitLine: axis.splitLine },
      series: series.map((m) => ({
        name: title(m),
        type: viz.chart,
        smooth: false,
        data: data.map((r) => r[m]),
      })),
    };
  }

  if (viz.chart === "pie") {
    const mtype = typeOf(viz.measure);
    return {
      ...base,
      tooltip: { trigger: "item", valueFormatter: (v) => fmt(v, mtype) },
      series: [
        {
          name: title(viz.measure),
          type: "pie",
          radius: ["42%", "70%"],
          itemStyle: { borderColor: dark ? "#171b22" : "#ffffff", borderWidth: 2 },
          label: { color: ink, formatter: "{b}: {d}%" },
          data: data.map((r) => ({ name: String(r[viz.x]), value: r[viz.measure] })),
        },
      ],
    };
  }

  return null;
}

function Kpi({ viz, result }) {
  const data = result?.data || [];
  const measures = result?.annotation?.measures || {};
  const row = data[0] || {};
  return (
    <div className="kpis">
      {(viz.series || []).map((m) => (
        <div key={m} className="kpi">
          <div className="kpi-value">{fmt(row[m], measures[m]?.type)}</div>
          <div className="kpi-label">{measures[m]?.title || m}</div>
        </div>
      ))}
    </div>
  );
}

export default function Chart({ viz, result }) {
  const ref = useRef(null);

  useEffect(() => {
    if (!viz || viz.chart === "kpi" || viz.chart === "none" || !ref.current) return;

    let chart;
    let observer;
    let cancelled = false;

    import("echarts").then((echarts) => {
      if (cancelled || !ref.current) return;
      chart = echarts.init(ref.current);
      const option = buildOption(viz, result, prefersDark());
      if (option) chart.setOption(option);
      observer = new ResizeObserver(() => chart && chart.resize());
      observer.observe(ref.current);
    });

    return () => {
      cancelled = true;
      if (observer) observer.disconnect();
      if (chart) chart.dispose();
    };
  }, [viz, result]);

  if (!viz || viz.chart === "none") return null;
  if (viz.chart === "kpi") return <Kpi viz={viz} result={result} />;

  return (
    <figure className="chart">
      <div ref={ref} className="chart-canvas" role="img" aria-label={viz.reason || "chart"} />
      {viz.reason && <figcaption className="chart-cap">{viz.reason}</figcaption>}
    </figure>
  );
}
