"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Search } from "lucide-react";

export function SearchHero() {
  const [query, setQuery] = useState("");
  const router = useRouter();

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (query.trim().length < 2) return;
    router.push(`/search?q=${encodeURIComponent(query.trim())}`);
  };

  return (
    <div className="text-center py-16 space-y-6">
      <h1 className="text-4xl sm:text-5xl font-extrabold text-gray-900 leading-tight">
        Find the Best Price,
        <br />
        <span className="text-primary-600">Instantly</span>
      </h1>
      <p className="text-xl text-gray-500 max-w-2xl mx-auto">
        We crawl Amazon, eBay, and thousands of stores in real-time to find you the lowest price on any product.
      </p>

      <form onSubmit={handleSearch} className="max-w-2xl mx-auto">
        <div className="flex gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder='Search any product, e.g. "iPhone 16 Pro"'
              className="w-full pl-12 pr-4 py-3.5 text-base border border-gray-300 rounded-xl focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent shadow-sm"
            />
          </div>
          <button type="submit" className="btn-primary text-base px-8">
            Search
          </button>
        </div>
      </form>

      <div className="flex items-center justify-center gap-6 text-sm text-gray-400">
        <span>Amazon</span>
        <span>·</span>
        <span>eBay</span>
        <span>·</span>
        <span>Any store URL</span>
      </div>
    </div>
  );
}
