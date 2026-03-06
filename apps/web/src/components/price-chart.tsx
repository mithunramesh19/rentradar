"use client";

import { useMemo, useState } from "react";
import { Area, AreaChart, CartesianGrid, XAxis, YAxis } from "recharts";

import { Badge } from "@/components/ui/badge";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  ChartContainer,
  ChartLegend,
  ChartLegendContent,
  ChartTooltip,
  ChartTooltipContent,
  type ChartConfig,
} from "@/components/ui/chart";
import type { ListingSource, PriceHistory } from "@/lib/types";
import { cn } from "@/lib/utils";

const SOURCE_COLORS: Record<ListingSource, string> = {
  streeteasy: "hsl(220, 70%, 55%)",
  craigslist: "hsl(35, 90%, 50%)",
  zillow: "hsl(210, 80%, 45%)",
  rentcom: "hsl(150, 60%, 45%)",
  zumper: "hsl(280, 60%, 55%)",
};

type ViewMode = "combined" | "by-source";

interface PriceChartProps {
  data: PriceHistory[];
  title?: string;
  description?: string;
  showCard?: boolean;
  height?: number;
}

export function PriceChart({
  data,
  title = "Price History",
  description,
  showCard = false,
  height = 250,
}: PriceChartProps) {
  const [mode, setMode] = useState<ViewMode>("combined");

  const sources = useMemo(
    () => [...new Set(data.map((d) => d.source))],
    [data],
  );

  const chartConfig = useMemo<ChartConfig>(() => {
    if (mode === "combined") {
      return { price: { label: "Price", color: "var(--color-primary)" } };
    }
    return Object.fromEntries(
      sources.map((s) => [s, { label: s, color: SOURCE_COLORS[s] }]),
    );
  }, [mode, sources]);

  const chartData = useMemo(() => {
    const sorted = [...data].sort(
      (a, b) =>
        new Date(a.recorded_at).getTime() - new Date(b.recorded_at).getTime(),
    );

    if (mode === "combined") {
      return sorted.map((d) => ({
        date: formatDate(d.recorded_at),
        price: d.price,
      }));
    }

    // Group by date, one column per source
    const byDate = new Map<string, Record<string, string | number>>();
    for (const d of sorted) {
      const key = formatDate(d.recorded_at);
      const row = byDate.get(key) ?? { date: key };
      row[d.source] = d.price;
      byDate.set(key, row);
    }
    return Array.from(byDate.values());
  }, [data, mode]);

  // Stats
  const stats = useMemo(() => {
    if (data.length === 0) return null;
    const prices = data.map((d) => d.price);
    const first = prices[0];
    const last = prices[prices.length - 1];
    const change = last - first;
    const changePct = first > 0 ? (change / first) * 100 : 0;
    return {
      current: last,
      low: Math.min(...prices),
      high: Math.max(...prices),
      change,
      changePct,
    };
  }, [data]);

  if (data.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        No price history available
      </p>
    );
  }

  const chart = (
    <div className="space-y-3">
      {/* Mode toggle + stats */}
      <div className="flex items-center justify-between">
        {stats && (
          <div className="flex items-center gap-3 text-sm">
            <span className="font-medium">
              ${stats.current.toLocaleString()}
            </span>
            <Badge
              variant="outline"
              className={cn(
                "text-[10px]",
                stats.change < 0
                  ? "text-green-700 dark:text-green-400"
                  : stats.change > 0
                    ? "text-red-700 dark:text-red-400"
                    : "",
              )}
            >
              {stats.change >= 0 ? "+" : ""}
              {stats.changePct.toFixed(1)}%
            </Badge>
            <span className="text-xs text-muted-foreground">
              L: ${stats.low.toLocaleString()} · H: $
              {stats.high.toLocaleString()}
            </span>
          </div>
        )}
        {sources.length > 1 && (
          <div className="flex gap-1">
            {(["combined", "by-source"] as const).map((m) => (
              <Badge
                key={m}
                variant={mode === m ? "default" : "outline"}
                className="cursor-pointer text-[10px]"
                onClick={() => setMode(m)}
              >
                {m === "combined" ? "Combined" : "By Source"}
              </Badge>
            ))}
          </div>
        )}
      </div>

      <ChartContainer config={chartConfig} className="w-full" style={{ height }}>
        <AreaChart
          data={chartData}
          margin={{ top: 8, right: 8, bottom: 0, left: 8 }}
        >
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="date"
            tickLine={false}
            axisLine={false}
            fontSize={12}
          />
          <YAxis
            tickFormatter={(v: number) => `$${v.toLocaleString()}`}
            tickLine={false}
            axisLine={false}
            fontSize={12}
            width={70}
          />
          <ChartTooltip content={<ChartTooltipContent />} />
          {mode === "combined" ? (
            <Area
              dataKey="price"
              type="monotone"
              fill="var(--color-primary)"
              fillOpacity={0.15}
              stroke="var(--color-primary)"
              strokeWidth={2}
            />
          ) : (
            sources.map((src) => (
              <Area
                key={src}
                dataKey={src}
                type="monotone"
                fill={SOURCE_COLORS[src]}
                fillOpacity={0.1}
                stroke={SOURCE_COLORS[src]}
                strokeWidth={2}
                connectNulls
              />
            ))
          )}
          {mode === "by-source" && sources.length > 1 && (
            <ChartLegend content={<ChartLegendContent />} />
          )}
        </AreaChart>
      </ChartContainer>
    </div>
  );

  if (!showCard) return chart;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
        {description && <CardDescription>{description}</CardDescription>}
      </CardHeader>
      <CardContent>{chart}</CardContent>
    </Card>
  );
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}
