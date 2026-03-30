"use client";

import { useQuery } from "@tanstack/react-query";
import { getPlatformStats } from "@/lib/api";

export function StatsBar() {
  const { data } = useQuery({ queryKey: ["platform-stats"], queryFn: getPlatformStats });

  if (!data) return null;

  return (
    <div className="grid grid-cols-3 gap-6 text-center">
      <div className="card py-4">
        <p className="text-3xl font-extrabold text-primary-600">{data.total_products.toLocaleString()}</p>
        <p className="text-sm text-gray-500 mt-1">Products tracked</p>
      </div>
      <div className="card py-4">
        <p className="text-3xl font-extrabold text-primary-600">{data.total_listings.toLocaleString()}</p>
        <p className="text-sm text-gray-500 mt-1">Price listings</p>
      </div>
      <div className="card py-4">
        <p className="text-3xl font-extrabold text-primary-600">{data.completed_crawls.toLocaleString()}</p>
        <p className="text-sm text-gray-500 mt-1">Crawls completed</p>
      </div>
    </div>
  );
}
