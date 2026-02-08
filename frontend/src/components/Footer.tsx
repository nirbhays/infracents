import Link from 'next/link';

/**
 * Footer
 *
 * Site-wide footer with links and copyright.
 */
export function Footer() {
  return (
    <footer className="border-t border-gray-200 bg-gray-50">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <div className="grid grid-cols-2 gap-8 md:grid-cols-4">
          {/* Brand */}
          <div className="col-span-2 md:col-span-1">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
                ₵
              </div>
              <span className="text-lg font-bold text-gray-900">InfraCents</span>
            </div>
            <p className="mt-3 text-sm text-gray-500">
              Know what your Terraform changes cost before they ship.
            </p>
          </div>

          {/* Product */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Product</h3>
            <ul className="mt-3 space-y-2">
              <li><Link href="/#features" className="text-sm text-gray-500 hover:text-gray-900">Features</Link></li>
              <li><Link href="/#pricing" className="text-sm text-gray-500 hover:text-gray-900">Pricing</Link></li>
              <li><Link href="/dashboard" className="text-sm text-gray-500 hover:text-gray-900">Dashboard</Link></li>
              <li><Link href="/#faq" className="text-sm text-gray-500 hover:text-gray-900">FAQ</Link></li>
            </ul>
          </div>

          {/* Resources */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Resources</h3>
            <ul className="mt-3 space-y-2">
              <li><Link href="/docs" className="text-sm text-gray-500 hover:text-gray-900">Documentation</Link></li>
              <li><Link href="/docs/api" className="text-sm text-gray-500 hover:text-gray-900">API Reference</Link></li>
              <li><Link href="https://github.com/infracents/infracents" className="text-sm text-gray-500 hover:text-gray-900">GitHub</Link></li>
              <li><Link href="/changelog" className="text-sm text-gray-500 hover:text-gray-900">Changelog</Link></li>
            </ul>
          </div>

          {/* Legal */}
          <div>
            <h3 className="text-sm font-semibold text-gray-900">Legal</h3>
            <ul className="mt-3 space-y-2">
              <li><Link href="/privacy" className="text-sm text-gray-500 hover:text-gray-900">Privacy Policy</Link></li>
              <li><Link href="/terms" className="text-sm text-gray-500 hover:text-gray-900">Terms of Service</Link></li>
              <li><Link href="/security" className="text-sm text-gray-500 hover:text-gray-900">Security</Link></li>
            </ul>
          </div>
        </div>

        <div className="mt-12 border-t border-gray-200 pt-8">
          <p className="text-center text-xs text-gray-400">
            © {new Date().getFullYear()} InfraCents. All rights reserved. Built with ❤️ for DevOps teams.
          </p>
        </div>
      </div>
    </footer>
  );
}
