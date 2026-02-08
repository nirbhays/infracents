import Link from 'next/link';

interface PricingCardProps {
  name: string;
  price: number;
  description: string;
  features: string[];
  ctaText: string;
  ctaHref: string;
  highlighted?: boolean;
}

/**
 * Pricing Card
 *
 * Displays a single pricing tier with features and CTA.
 * Used on the landing page pricing section.
 */
export function PricingCard({
  name,
  price,
  description,
  features,
  ctaText,
  ctaHref,
  highlighted = false,
}: PricingCardProps) {
  return (
    <div
      className={`relative rounded-2xl p-8 ${
        highlighted
          ? 'border-2 border-brand-600 bg-white shadow-xl shadow-brand-100'
          : 'border border-gray-200 bg-white'
      }`}
    >
      {highlighted && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
          <span className="inline-flex rounded-full bg-brand-600 px-4 py-1 text-xs font-semibold text-white">
            Most Popular
          </span>
        </div>
      )}

      <h3 className="text-lg font-semibold text-gray-900">{name}</h3>
      <p className="mt-1 text-sm text-gray-500">{description}</p>

      <div className="mt-4">
        <span className="text-4xl font-bold text-gray-900">
          ${price}
        </span>
        {price > 0 && (
          <span className="text-sm text-gray-500">/mo</span>
        )}
      </div>

      <ul className="mt-6 space-y-3">
        {features.map((feature, i) => (
          <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
            <svg
              className="mt-0.5 h-4 w-4 flex-shrink-0 text-green-500"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={2.5}
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
            </svg>
            {feature}
          </li>
        ))}
      </ul>

      <Link
        href={ctaHref}
        className={`mt-8 block w-full rounded-lg px-4 py-2.5 text-center text-sm font-semibold transition-colors ${
          highlighted
            ? 'bg-brand-600 text-white hover:bg-brand-500'
            : 'border border-gray-300 text-gray-700 hover:bg-gray-50'
        }`}
      >
        {ctaText}
      </Link>
    </div>
  );
}
