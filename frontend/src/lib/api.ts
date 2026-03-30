import axios from "axios";

const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30_000,
  headers: { "Content-Type": "application/json" },
});

export interface ProductSummary {
  id: string;
  name: string;
  brand: string | null;
  image_url: string | null;
  best_price: number | null;
  best_price_store: string | null;
  currency: string;
  listing_count: number;
}

export interface PriceListing {
  id: string;
  store_name: string;
  store_domain: string;
  product_url: string;
  price: number;
  original_price: number | null;
  currency: string;
  availability: string;
  rating: number | null;
  review_count: number | null;
  shipping_cost: number | null;
  seller_name: string | null;
  scraped_at: string;
  discount_percent: number | null;
}

export interface PriceHistoryPoint {
  store_domain: string;
  price: number;
  currency: string;
  recorded_at: string;
}

export interface PriceAnalysis {
  product_id: string;
  product_name: string;
  lowest_price: number;
  highest_price: number;
  average_price: number;
  median_price: number;
  best_deal: PriceListing;
  savings_vs_highest: number;
  savings_percent: number;
  listings: PriceListing[];
  price_history: PriceHistoryPoint[];
  in_stock_count: number;
  total_listing_count: number;
}

export interface CrawlJob {
  id: string;
  query: string;
  status: "pending" | "in_progress" | "completed" | "failed";
  results_count: number;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
}

export interface PlatformStats {
  total_products: number;
  total_listings: number;
  completed_crawls: number;
}

export interface StoreStats {
  store_name: string;
  store_domain: string;
  avg_price: number;
  listing_count: number;
}

// ── API calls ────────────────────────────────────────────────────────────────

export const searchProducts = async (
  query: string,
  crawlFresh = false,
  maxResults = 20
): Promise<{ query: string; results: ProductSummary[]; total: number; crawl_job_id: string | null }> => {
  const { data } = await api.post("/search", {
    query,
    crawl_fresh: crawlFresh,
    max_results: maxResults,
  });
  return data;
};

export const getPriceAnalysis = async (productId: string): Promise<PriceAnalysis> => {
  const { data } = await api.get(`/products/${productId}/analysis`);
  return data;
};

export const triggerCrawl = async (query: string, urls?: string[]): Promise<CrawlJob> => {
  const { data } = await api.post("/crawl", { query, urls });
  return data;
};

export const getCrawlJob = async (jobId: string): Promise<CrawlJob> => {
  const { data } = await api.get(`/crawl/${jobId}`);
  return data;
};

export const getPlatformStats = async (): Promise<PlatformStats> => {
  const { data } = await api.get("/analytics/stats");
  return data;
};

export const getCheapestStores = async (limit = 10): Promise<StoreStats[]> => {
  const { data } = await api.get(`/analytics/cheapest-stores?limit=${limit}`);
  return data;
};

export const getPriceTrend = async (productId: string, days = 30) => {
  const { data } = await api.get(`/analytics/price-trend/${productId}?days=${days}`);
  return data;
};

export default api;
