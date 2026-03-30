import { type PriceAnalysis } from "@/lib/api";
import { TrendingDown, TrendingUp, BarChart, Tag } from "lucide-react";

interface Props {
  analysis: PriceAnalysis;
}

export function AnalysisSummaryCards({ analysis }: Props) {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <SummaryCard
        icon={<TrendingDown className="h-5 w-5 text-green-500" />}
        label="Lowest Price"
        value={`$${analysis.lowest_price.toFixed(2)}`}
        sub={`at ${analysis.best_deal.store_name}`}
        accent="green"
      />
      <SummaryCard
        icon={<TrendingUp className="h-5 w-5 text-red-400" />}
        label="Highest Price"
        value={`$${analysis.highest_price.toFixed(2)}`}
        sub="among all stores"
        accent="red"
      />
      <SummaryCard
        icon={<BarChart className="h-5 w-5 text-blue-500" />}
        label="Average Price"
        value={`$${analysis.average_price.toFixed(2)}`}
        sub={`median $${analysis.median_price.toFixed(2)}`}
        accent="blue"
      />
      <SummaryCard
        icon={<Tag className="h-5 w-5 text-purple-500" />}
        label="Max Savings"
        value={`$${analysis.savings_vs_highest.toFixed(2)}`}
        sub={`${analysis.savings_percent}% off highest`}
        accent="purple"
      />
    </div>
  );
}

function SummaryCard({
  icon, label, value, sub, accent,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub: string;
  accent: string;
}) {
  return (
    <div className="card">
      <div className="flex items-center gap-2 mb-2">
        {icon}
        <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide">{label}</span>
      </div>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-400 mt-0.5">{sub}</p>
    </div>
  );
}
