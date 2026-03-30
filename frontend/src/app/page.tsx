import { SearchHero } from "@/components/ui/SearchHero";
import { StatsBar } from "@/components/ui/StatsBar";

export default function HomePage() {
  return (
    <div className="space-y-10">
      <SearchHero />
      <StatsBar />
    </div>
  );
}
