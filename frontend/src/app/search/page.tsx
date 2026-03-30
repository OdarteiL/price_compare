"use client";

import { useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Suspense, useState } from "react";
import { searchProducts } from "@/lib/api";
import { ProductCard } from "@/components/ui/ProductCard";
import { CrawlStatusBanner } from "@/components/ui/CrawlStatusBanner";
import { SearchBar } from "@/components/ui/SearchBar";
import { Loader2 } from "lucide-react";

function SearchResults() {
  const searchParams = useSearchParams();
  const query = searchParams.get("q") || "";
  const [crawlJobId, setCrawlJobId] = useState<string | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["search", query],
    queryFn: async () => {
      const result = await searchProducts(query, false);
      if (result.crawl_job_id) setCrawlJobId(result.crawl_job_id);
      return result;
    },
    enabled: !!query,
  });

  if (!query) return <p className="text-gray-500 text-center mt-10">Enter a search term above.</p>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-gray-900">
          Results for <span className="text-primary-600">"{query}"</span>
        </h1>
        {data && (
          <span className="text-sm text-gray-500">{data.total} products found</span>
        )}
      </div>

      {crawlJobId && (
        <CrawlStatusBanner
          jobId={crawlJobId}
          onComplete={() => setCrawlJobId(null)}
        />
      )}

      {isLoading && (
        <div className="flex justify-center py-20">
          <Loader2 className="h-10 w-10 animate-spin text-primary-600" />
        </div>
      )}

      {isError && (
        <div className="card text-center text-red-600">
          Failed to fetch results. Please try again.
        </div>
      )}

      {data && data.results.length === 0 && !isLoading && (
        <div className="card text-center py-12">
          <p className="text-gray-500 text-lg">No cached results yet.</p>
          <p className="text-gray-400 text-sm mt-1">
            A crawl job has been triggered — results will appear shortly.
          </p>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {data?.results.map((product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
    </div>
  );
}

export default function SearchPage() {
  return (
    <div className="space-y-6">
      <SearchBar />
      <Suspense fallback={<div className="flex justify-center py-20"><Loader2 className="h-10 w-10 animate-spin text-primary-600" /></div>}>
        <SearchResults />
      </Suspense>
    </div>
  );
}
