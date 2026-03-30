import Link from "next/link";
import Image from "next/image";
import { type ProductSummary } from "@/lib/api";
import { ExternalLink, Store } from "lucide-react";

interface Props {
  product: ProductSummary;
}

export function ProductCard({ product }: Props) {
  return (
    <Link href={`/products/${product.id}`} className="block group">
      <div className="card hover:shadow-md transition-shadow duration-200 h-full flex flex-col">
        {/* Image */}
        <div className="relative w-full h-48 bg-gray-100 rounded-lg overflow-hidden mb-4">
          {product.image_url ? (
            <Image
              src={product.image_url}
              alt={product.name}
              fill
              className="object-contain p-2 group-hover:scale-105 transition-transform duration-200"
              sizes="(max-width: 640px) 100vw, (max-width: 1024px) 50vw, 25vw"
              unoptimized
            />
          ) : (
            <div className="flex items-center justify-center h-full">
              <Store className="h-12 w-12 text-gray-300" />
            </div>
          )}
        </div>

        {/* Content */}
        <div className="flex-1 space-y-2">
          {product.brand && (
            <p className="text-xs font-semibold text-primary-600 uppercase tracking-wide">{product.brand}</p>
          )}
          <h3 className="text-sm font-semibold text-gray-900 line-clamp-2 group-hover:text-primary-600 transition-colors">
            {product.name}
          </h3>
        </div>

        {/* Price */}
        <div className="mt-4 pt-4 border-t border-gray-100">
          {product.best_price !== null ? (
            <div className="flex items-baseline justify-between">
              <div>
                <span className="text-xs text-gray-400">Best price</span>
                <p className="text-xl font-bold text-gray-900">
                  {product.currency} {product.best_price.toFixed(2)}
                </p>
              </div>
              <div className="text-right">
                <span className="text-xs text-gray-400">{product.listing_count} stores</span>
                {product.best_price_store && (
                  <p className="text-xs font-medium text-green-600">{product.best_price_store}</p>
                )}
              </div>
            </div>
          ) : (
            <p className="text-sm text-gray-400">Price unavailable</p>
          )}
        </div>
      </div>
    </Link>
  );
}
