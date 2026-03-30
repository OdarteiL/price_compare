import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.amazon.com" },
      { protocol: "https", hostname: "**.ebayimg.com" },
      { protocol: "https", hostname: "**.ebay.com" },
      { protocol: "https", hostname: "m.media-amazon.com" },
    ],
  },
  async rewrites() {
    // BACKEND_URL is a server-side env var (no NEXT_PUBLIC_ prefix).
    // Docker Compose sets it to http://backend:8000.
    // Local dev uses http://localhost:8000 via .env.local.
    const backendUrl = process.env.BACKEND_URL || "http://localhost:8000";
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
