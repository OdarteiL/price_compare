export const dynamic = "force-dynamic";

import { Suspense } from "react";
import { SearchBar } from "@/components/ui/SearchBar";
import { SearchResults } from "./SearchResults";
import { Loader2 } from "lucide-react";

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
