"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { getPriceAnalysis } from "@/lib/api";
import { PriceComparisonTable } from "@/components/ui/PriceComparisonTable";
import { PriceHistoryChart } from "@/components/charts/PriceHistoryChart";
import { AnalysisSummaryCards } from "@/components/ui/AnalysisSummaryCards";
import { Loader2, ArrowLeft } from "lucide-react";
import Link from "next/link";
import Image from "next/image";

export default function ProductPage() {
  const { id } = useParams<{ id: string }>();

  const { data: analysis, isLoading, isError } = useQuery({
    queryKey: ["analysis", id],
    queryFn: () => getPriceAnalysis(id),
  });

  if (isLoading) {
    return (
      <div className="flex justify-center py-20">
        <Loader2 className="h-10 w-10 animate-spin text-primary-600" />
      </div>
    );
  }

  if (isError || !analysis) {
    return (
      <div className="card text-center text-red-600 py-12">
        Failed to load product analysis.
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center gap-4">
        <Link href="/search" className="text-gray-400 hover:text-gray-600 transition-colors">
          <ArrowLeft className="h-6 w-6" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{analysis.product_name}</h1>
          <p className="text-sm text-gray-500 mt-0.5">
            {analysis.total_listing_count} stores compared · {analysis.in_stock_count} in stock
          </p>
        </div>
      </div>

      {/* Summary cards */}
      <AnalysisSummaryCards analysis={analysis} />

      {/* Price comparison table */}
      <div className="card">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Price Comparison</h2>
        <PriceComparisonTable listings={analysis.listings} bestPrice={analysis.lowest_price} />
      </div>

      {/* Price history chart */}
      {analysis.price_history.length > 1 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Price History</h2>
          <PriceHistoryChart history={analysis.price_history} />
        </div>
      )}
    </div>
  );
}
