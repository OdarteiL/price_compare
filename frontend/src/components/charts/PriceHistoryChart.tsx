"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from "recharts";
import { type PriceHistoryPoint } from "@/lib/api";
import { useMemo } from "react";

const COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#a855f7", "#ec4899"];

interface Props {
  history: PriceHistoryPoint[];
}

export function PriceHistoryChart({ history }: Props) {
  const { chartData, domains } = useMemo(() => {
    const domainSet = new Set(history.map((h) => h.store_domain));
    const domains = Array.from(domainSet);

    // Group by date
    const byDate: Record<string, Record<string, number>> = {};
    for (const point of history) {
      const date = new Date(point.recorded_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      });
      if (!byDate[date]) byDate[date] = {};
      byDate[date][point.store_domain] = point.price;
    }

    const chartData = Object.entries(byDate).map(([date, prices]) => ({
      date,
      ...prices,
    }));

    return { chartData, domains };
  }, [history]);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData} margin={{ top: 5, right: 20, left: 0, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
        <XAxis dataKey="date" tick={{ fontSize: 12 }} />
        <YAxis tickFormatter={(v) => `$${v}`} tick={{ fontSize: 12 }} />
        <Tooltip
          formatter={(value: number, name: string) => [`$${value.toFixed(2)}`, name]}
          labelStyle={{ fontWeight: "bold" }}
        />
        <Legend />
        {domains.map((domain, i) => (
          <Line
            key={domain}
            type="monotone"
            dataKey={domain}
            stroke={COLORS[i % COLORS.length]}
            strokeWidth={2}
            dot={false}
            activeDot={{ r: 5 }}
            connectNulls
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
