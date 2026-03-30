"use client";

import { useQuery } from "@tanstack/react-query";
import { getPlatformStats, getCheapestStores } from "@/lib/api";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { TrendingDown, ShoppingBag, Search, RefreshCw } from "lucide-react";

export default function AnalyticsPage() {
  const { data: stats } = useQuery({ queryKey: ["platform-stats"], queryFn: getPlatformStats });
  const { data: stores } = useQuery({ queryKey: ["cheapest-stores"], queryFn: () => getCheapestStores(10) });

  return (
    <div className="space-y-8">
      <h1 className="text-2xl font-bold text-gray-900">Platform Analytics</h1>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        <StatCard
          icon={<ShoppingBag className="h-6 w-6 text-blue-500" />}
          label="Total Products"
          value={stats?.total_products ?? "—"}
        />
        <StatCard
          icon={<TrendingDown className="h-6 w-6 text-green-500" />}
          label="Price Listings"
          value={stats?.total_listings ?? "—"}
        />
        <StatCard
          icon={<RefreshCw className="h-6 w-6 text-purple-500" />}
          label="Completed Crawls"
          value={stats?.completed_crawls ?? "—"}
        />
      </div>

      {/* Cheapest stores chart */}
      {stores && stores.length > 0 && (
        <div className="card">
          <h2 className="text-lg font-semibold text-gray-900 mb-6">
            Average Price by Store
          </h2>
          <ResponsiveContainer width="100%" height={320}>
            <BarChart data={stores} margin={{ top: 5, right: 20, left: 0, bottom: 60 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
              <XAxis
                dataKey="store_name"
                angle={-35}
                textAnchor="end"
                tick={{ fontSize: 12 }}
              />
              <YAxis
                tickFormatter={(v) => `$${v}`}
                tick={{ fontSize: 12 }}
              />
              <Tooltip
                formatter={(value: number) => [`$${value.toFixed(2)}`, "Avg Price"]}
              />
              <Bar dataKey="avg_price" fill="#3b82f6" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Store table */}
      {stores && stores.length > 0 && (
        <div className="card overflow-hidden">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Store Rankings</h2>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead>
                <tr>
                  {["Rank", "Store", "Avg Price", "Listings"].map((h) => (
                    <th
                      key={h}
                      className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider bg-gray-50"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {stores.map((store, i) => (
                  <tr key={store.store_domain} className="hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-3 text-sm font-semibold text-gray-500">#{i + 1}</td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-gray-900">{store.store_name}</div>
                      <div className="text-xs text-gray-400">{store.store_domain}</div>
                    </td>
                    <td className="px-4 py-3 text-sm font-bold text-green-600">
                      ${store.avg_price.toFixed(2)}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600">{store.listing_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ icon, label, value }: { icon: React.ReactNode; label: string; value: number | string }) {
  return (
    <div className="card flex items-center gap-4">
      <div className="p-3 bg-gray-50 rounded-xl">{icon}</div>
      <div>
        <p className="text-sm text-gray-500">{label}</p>
        <p className="text-2xl font-bold text-gray-900">{value.toLocaleString()}</p>
      </div>
    </div>
  );
}
