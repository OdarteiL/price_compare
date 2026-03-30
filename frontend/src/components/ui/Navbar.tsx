import Link from "next/link";
import { BarChart2, Search, Home } from "lucide-react";

export function Navbar() {
  return (
    <nav className="bg-white border-b border-gray-200 sticky top-0 z-40">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">PC</span>
            </div>
            <span className="font-bold text-gray-900 text-lg">PriceCompare</span>
          </Link>

          <div className="flex items-center gap-1">
            <NavLink href="/" icon={<Home className="h-4 w-4" />} label="Home" />
            <NavLink href="/search" icon={<Search className="h-4 w-4" />} label="Search" />
            <NavLink href="/analytics" icon={<BarChart2 className="h-4 w-4" />} label="Analytics" />
          </div>
        </div>
      </div>
    </nav>
  );
}

function NavLink({ href, icon, label }: { href: string; icon: React.ReactNode; label: string }) {
  return (
    <Link
      href={href}
      className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-100 transition-colors"
    >
      {icon}
      {label}
    </Link>
  );
}
