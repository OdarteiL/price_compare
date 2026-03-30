import { type PriceListing } from "@/lib/api";
import { ExternalLink, Star } from "lucide-react";
import { clsx } from "clsx";

interface Props {
  listings: PriceListing[];
  bestPrice: number;
}

const availabilityBadge: Record<string, string> = {
  in_stock: "badge-green",
  out_of_stock: "badge-red",
  limited: "badge-yellow",
  unknown: "bg-gray-100 text-gray-600 inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium",
};

const availabilityLabel: Record<string, string> = {
  in_stock: "In Stock",
  out_of_stock: "Out of Stock",
  limited: "Limited",
  unknown: "Unknown",
};

export function PriceComparisonTable({ listings, bestPrice }: Props) {
  return (
    <div className="overflow-x-auto -mx-6 px-6">
      <table className="min-w-full divide-y divide-gray-200">
        <thead>
          <tr>
            {["Store", "Price", "Shipping", "Availability", "Rating", ""].map((h) => (
              <th
                key={h}
                className="px-4 py-3 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider bg-gray-50 first:rounded-tl-lg last:rounded-tr-lg"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {listings.map((listing, i) => {
            const isBest = listing.price === bestPrice;
            return (
              <tr key={listing.id} className={clsx("transition-colors", isBest ? "bg-green-50" : "hover:bg-gray-50")}>
                <td className="px-4 py-4">
                  <div className="font-medium text-gray-900 flex items-center gap-2">
                    {isBest && (
                      <span className="badge-green text-xs">Best</span>
                    )}
                    {listing.store_name}
                  </div>
                  <div className="text-xs text-gray-400">{listing.store_domain}</div>
                </td>
                <td className="px-4 py-4">
                  <div className="font-bold text-gray-900 text-lg">
                    {listing.currency} {listing.price.toFixed(2)}
                  </div>
                  {listing.original_price && listing.original_price > listing.price && (
                    <div className="text-xs text-gray-400 line-through">
                      ${listing.original_price.toFixed(2)}
                    </div>
                  )}
                  {listing.discount_percent && (
                    <span className="text-xs font-semibold text-green-600">
                      -{listing.discount_percent}% off
                    </span>
                  )}
                </td>
                <td className="px-4 py-4 text-sm text-gray-600">
                  {listing.shipping_cost === 0
                    ? <span className="text-green-600 font-medium">Free</span>
                    : listing.shipping_cost !== null
                    ? `$${listing.shipping_cost.toFixed(2)}`
                    : "—"}
                </td>
                <td className="px-4 py-4">
                  <span className={availabilityBadge[listing.availability] || availabilityBadge.unknown}>
                    {availabilityLabel[listing.availability] || listing.availability}
                  </span>
                </td>
                <td className="px-4 py-4 text-sm text-gray-600">
                  {listing.rating ? (
                    <div className="flex items-center gap-1">
                      <Star className="h-3.5 w-3.5 fill-yellow-400 text-yellow-400" />
                      <span>{listing.rating.toFixed(1)}</span>
                      {listing.review_count && (
                        <span className="text-gray-400">({listing.review_count.toLocaleString()})</span>
                      )}
                    </div>
                  ) : "—"}
                </td>
                <td className="px-4 py-4">
                  <a
                    href={listing.product_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 text-primary-600 hover:text-primary-700 text-sm font-medium"
                    onClick={(e) => e.stopPropagation()}
                  >
                    Buy <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
