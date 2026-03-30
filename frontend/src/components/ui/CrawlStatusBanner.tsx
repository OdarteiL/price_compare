"use client";

import { useEffect, useState } from "react";
import { getCrawlJob } from "@/lib/api";
import { Loader2, CheckCircle, XCircle } from "lucide-react";

interface Props {
  jobId: string;
  onComplete?: () => void;
}

export function CrawlStatusBanner({ jobId, onComplete }: Props) {
  const [status, setStatus] = useState<string>("pending");
  const [resultsCount, setResultsCount] = useState(0);

  useEffect(() => {
    // Use the SSE stream endpoint for real-time updates
    const evtSource = new EventSource(`/api/v1/crawl/${jobId}/stream`);

    evtSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setStatus(data.status);
      setResultsCount(data.results_count || 0);

      if (data.status === "completed" || data.status === "failed") {
        evtSource.close();
        if (data.status === "completed" && onComplete) {
          setTimeout(onComplete, 2000);
        }
      }
    };

    evtSource.onerror = () => evtSource.close();

    return () => evtSource.close();
  }, [jobId, onComplete]);

  if (status === "completed") {
    return (
      <div className="flex items-center gap-2 px-4 py-3 bg-green-50 border border-green-200 rounded-xl text-green-700 text-sm">
        <CheckCircle className="h-4 w-4 flex-shrink-0" />
        Crawl complete — found {resultsCount} products. Refreshing...
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="flex items-center gap-2 px-4 py-3 bg-red-50 border border-red-200 rounded-xl text-red-700 text-sm">
        <XCircle className="h-4 w-4 flex-shrink-0" />
        Crawl failed. Showing cached results.
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 px-4 py-3 bg-blue-50 border border-blue-200 rounded-xl text-blue-700 text-sm">
      <Loader2 className="h-4 w-4 animate-spin flex-shrink-0" />
      Crawling stores for fresh prices — this takes ~30 seconds...
    </div>
  );
}
