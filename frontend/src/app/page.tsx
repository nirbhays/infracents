import Link from 'next/link';
import { PricingCard } from '@/components/PricingCard';

/**
 * Landing Page
 *
 * The public-facing marketing page with:
 * - Hero section with value proposition
 * - Feature highlights
 * - How it works section
 * - Pricing tiers
 * - FAQ
 * - CTA
 */
export default function HomePage() {
  return (
    <div className="bg-white">
      {/* Hero Section */}
      <section className="relative overflow-hidden bg-gradient-to-br from-brand-950 via-brand-900 to-brand-800">
        <div className="absolute inset-0 bg-[url('/grid.svg')] opacity-10" />
        <div className="relative mx-auto max-w-7xl px-6 py-24 sm:py-32 lg:py-40">
          <div className="mx-auto max-w-3xl text-center">
            <div className="mb-6 inline-flex items-center rounded-full bg-brand-500/10 px-4 py-1.5 text-sm font-medium text-brand-300 ring-1 ring-brand-500/20">
              🚀 Now in public beta
            </div>
            <h1 className="text-4xl font-extrabold tracking-tight text-white sm:text-6xl lg:text-7xl">
              Know what your Terraform changes{' '}
              <span className="bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                cost
              </span>
            </h1>
            <p className="mt-6 text-lg leading-8 text-gray-300 sm:text-xl">
              InfraCents automatically estimates the cost impact of every Terraform pull request.
              No more surprise cloud bills. Catch cost regressions at code review time.
            </p>
            <div className="mt-10 flex items-center justify-center gap-x-6">
              <Link
                href="https://github.com/apps/infracents"
                className="rounded-lg bg-brand-500 px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-brand-500/25 hover:bg-brand-400 transition-all duration-200"
              >
                Install GitHub App →
              </Link>
              <Link
                href="#how-it-works"
                className="text-sm font-semibold leading-6 text-gray-300 hover:text-white transition-colors"
              >
                See how it works ↓
              </Link>
            </div>
          </div>

          {/* PR Comment Preview */}
          <div className="mx-auto mt-16 max-w-2xl">
            <div className="rounded-xl border border-gray-700 bg-gray-900/80 p-6 shadow-2xl backdrop-blur">
              <div className="flex items-start gap-3">
                <div className="h-10 w-10 rounded-full bg-brand-500 flex items-center justify-center text-white text-lg font-bold">
                  ₵
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-white">infracents</span>
                    <span className="text-xs text-gray-500">bot</span>
                    <span className="text-xs text-gray-500">• just now</span>
                  </div>
                  <div className="mt-3 rounded-lg bg-gray-800/50 p-4 text-sm">
                    <p className="text-lg font-semibold text-white">📈 InfraCents Cost Estimate</p>
                    <p className="mt-2 text-gray-300">
                      🔴 This change will <strong className="text-white">increase</strong> monthly costs by{' '}
                      <strong className="text-red-400">~$142/mo</strong> (+12.3%)
                    </p>
                    <div className="mt-4 overflow-hidden rounded border border-gray-700">
                      <table className="w-full text-left text-xs text-gray-300">
                        <thead className="bg-gray-800/80 text-gray-400">
                          <tr>
                            <th className="px-3 py-2">Resource</th>
                            <th className="px-3 py-2">Type</th>
                            <th className="px-3 py-2 text-right">Delta</th>
                          </tr>
                        </thead>
                        <tbody>
                          <tr className="border-t border-gray-700">
                            <td className="px-3 py-2 font-mono text-brand-400">analytics_db</td>
                            <td className="px-3 py-2">RDS Instance</td>
                            <td className="px-3 py-2 text-right text-red-400">+$142.50</td>
                          </tr>
                        </tbody>
                      </table>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
              Everything you need to control cloud costs
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              InfraCents integrates seamlessly into your existing workflow.
            </p>
          </div>

          <div className="mx-auto mt-16 grid max-w-5xl grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {[
              {
                icon: '🤖',
                title: 'Automated PR Comments',
                description:
                  'Every PR with Terraform changes gets an automatic cost estimate. No manual steps required.',
              },
              {
                icon: '📊',
                title: 'Cost Dashboard',
                description:
                  'Track cost trends over time across all your repositories with interactive charts.',
              },
              {
                icon: '☁️',
                title: 'Multi-Cloud',
                description:
                  'Supports AWS and GCP with 25+ resource types. Azure coming soon.',
              },
              {
                icon: '⚡',
                title: 'Real-Time Pricing',
                description:
                  'Queries official cloud pricing APIs with intelligent caching for accurate estimates.',
              },
              {
                icon: '🔒',
                title: 'Security First',
                description:
                  'Minimal permissions, webhook signature verification, no secrets stored.',
              },
              {
                icon: '💳',
                title: 'Flexible Billing',
                description:
                  'Free tier for open source. Pro, Business, and Enterprise plans for teams.',
              },
            ].map((feature, i) => (
              <div
                key={i}
                className="rounded-2xl border border-gray-200 bg-white p-8 shadow-sm hover:shadow-md transition-shadow"
              >
                <div className="text-4xl">{feature.icon}</div>
                <h3 className="mt-4 text-lg font-semibold text-gray-900">{feature.title}</h3>
                <p className="mt-2 text-sm text-gray-600">{feature.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section id="how-it-works" className="bg-gray-50 py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
              How it works
            </h2>
            <p className="mt-4 text-lg text-gray-600">Three simple steps to cost visibility.</p>
          </div>

          <div className="mx-auto mt-16 grid max-w-4xl grid-cols-1 gap-12 md:grid-cols-3">
            {[
              {
                step: '1',
                title: 'Install the GitHub App',
                description: 'One-click installation on any GitHub organization. Takes 30 seconds.',
              },
              {
                step: '2',
                title: 'Open a PR with .tf changes',
                description: 'InfraCents detects Terraform file changes automatically.',
              },
              {
                step: '3',
                title: 'Get your cost estimate',
                description:
                  'A detailed cost breakdown is posted as a comment on your PR within seconds.',
              },
            ].map((item, i) => (
              <div key={i} className="text-center">
                <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-brand-600 text-xl font-bold text-white">
                  {item.step}
                </div>
                <h3 className="mt-6 text-lg font-semibold text-gray-900">{item.title}</h3>
                <p className="mt-2 text-sm text-gray-600">{item.description}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing Section */}
      <section id="pricing" className="py-24 sm:py-32">
        <div className="mx-auto max-w-7xl px-6 lg:px-8">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight text-gray-900 sm:text-4xl">
              Simple, transparent pricing
            </h2>
            <p className="mt-4 text-lg text-gray-600">
              Start free. Upgrade when you need more.
            </p>
          </div>

          <div className="mx-auto mt-16 grid max-w-5xl grid-cols-1 gap-8 sm:grid-cols-2 lg:grid-cols-4">
            <PricingCard
              name="Free"
              price={0}
              description="For individual developers"
              features={['3 repositories', '50 scans/month', 'Basic estimates', '7 days history']}
              ctaText="Get Started"
              ctaHref="/sign-up"
            />
            <PricingCard
              name="Pro"
              price={29}
              description="For small teams"
              features={[
                '15 repositories',
                '500 scans/month',
                'Detailed breakdowns',
                '90 days history',
                'Slack integration',
                '5 team members',
              ]}
              ctaText="Start Free Trial"
              ctaHref="/sign-up?plan=pro"
              highlighted
            />
            <PricingCard
              name="Business"
              price={99}
              description="For growing teams"
              features={[
                'Unlimited repos',
                '5,000 scans/month',
                '1 year history',
                'SSO (SAML)',
                'Custom thresholds',
                'Priority support',
                'Audit logs',
              ]}
              ctaText="Start Free Trial"
              ctaHref="/sign-up?plan=business"
            />
            <PricingCard
              name="Enterprise"
              price={249}
              description="For large organizations"
              features={[
                'Everything in Business',
                'Unlimited scans',
                'Unlimited history',
                'Custom rules engine',
                '99.95% SLA',
                'Dedicated support',
              ]}
              ctaText="Contact Sales"
              ctaHref="mailto:sales@infracents.dev"
            />
          </div>
        </div>
      </section>

      {/* FAQ Section */}
      <section id="faq" className="bg-gray-50 py-24 sm:py-32">
        <div className="mx-auto max-w-3xl px-6 lg:px-8">
          <h2 className="text-3xl font-bold tracking-tight text-gray-900 text-center sm:text-4xl">
            Frequently asked questions
          </h2>

          <div className="mt-16 space-y-8">
            {[
              {
                q: 'How accurate are the cost estimates?',
                a: 'For resources with straightforward pricing (EC2, RDS, ECS), our estimates are within ±10%. For usage-dependent resources (S3, Lambda, CloudFront), estimates are within ±30%. We always show a confidence indicator.',
              },
              {
                q: 'What permissions does InfraCents need?',
                a: 'We request minimal permissions: read access to repository contents (to fetch .tf files) and write access to pull requests (to post comments). We never access your secrets, environment variables, or source code beyond .tf files.',
              },
              {
                q: 'Does InfraCents store my code?',
                a: 'No. We process .tf file contents in memory and never store them. We only store the cost estimate results (resource types, costs, and PR metadata).',
              },
              {
                q: 'Which cloud providers are supported?',
                a: 'We currently support AWS (15+ resource types) and GCP (10+ resource types). Azure support is coming soon.',
              },
              {
                q: 'Can I use InfraCents with Terraform Cloud?',
                a: 'Yes! If you use Terraform Cloud, you can send plan JSON output directly to our API for even more accurate estimates. See our API documentation for details.',
              },
              {
                q: 'What happens if I exceed my scan limit?',
                a: 'We post a friendly notification on your PR suggesting an upgrade. Your existing cost data is never deleted.',
              },
            ].map((faq, i) => (
              <div key={i} className="border-b border-gray-200 pb-8">
                <h3 className="text-lg font-semibold text-gray-900">{faq.q}</h3>
                <p className="mt-2 text-gray-600">{faq.a}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="bg-brand-900 py-24">
        <div className="mx-auto max-w-3xl text-center px-6">
          <h2 className="text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Stop guessing. Start knowing.
          </h2>
          <p className="mt-4 text-lg text-brand-200">
            Install InfraCents in 30 seconds and never be surprised by a cloud bill again.
          </p>
          <div className="mt-10">
            <Link
              href="https://github.com/apps/infracents"
              className="inline-flex items-center rounded-lg bg-white px-8 py-4 text-sm font-semibold text-brand-900 shadow-lg hover:bg-gray-100 transition-colors"
            >
              Install GitHub App — It&apos;s Free →
            </Link>
          </div>
        </div>
      </section>
    </div>
  );
}
