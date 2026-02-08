'use client';

import { useEffect, useState } from 'react';
import { useAuth } from '@clerk/nextjs';
import { apiClient } from '@/lib/api';

/**
 * Settings Page
 *
 * Manages billing, integrations, and organization settings.
 */
export default function SettingsPage() {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [subscription, setSubscription] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function fetchSubscription() {
      if (!isLoaded || !isSignedIn) return;

      try {
        const token = await getToken();
        const result = await apiClient.getSubscription(token || '');
        setSubscription(result);
      } catch (error) {
        console.error('Failed to fetch subscription:', error);
      } finally {
        setLoading(false);
      }
    }

    fetchSubscription();
  }, [isLoaded, isSignedIn, getToken]);

  const handleUpgrade = async (plan: string) => {
    try {
      const token = await getToken();
      const result = await apiClient.createCheckout(token || '', {
        plan,
        success_url: `${window.location.origin}/dashboard/settings?success=true`,
        cancel_url: `${window.location.origin}/dashboard/settings?canceled=true`,
      });
      window.location.href = result.checkout_url;
    } catch (error) {
      console.error('Failed to create checkout:', error);
    }
  };

  const handleManageBilling = async () => {
    try {
      const token = await getToken();
      const result = await apiClient.createPortal(token || '');
      window.location.href = result.portal_url;
    } catch (error) {
      console.error('Failed to create portal session:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-pulse text-gray-500">Loading settings...</div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-4xl px-6 py-8">
      <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
      <p className="mt-1 text-sm text-gray-500">Manage your subscription and integrations</p>

      {/* Current Plan */}
      <section className="mt-8">
        <h2 className="text-lg font-semibold text-gray-900">Current Plan</h2>
        <div className="mt-4 rounded-xl border border-gray-200 bg-white p-6">
          {subscription ? (
            <div>
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xl font-bold text-gray-900 capitalize">
                    {subscription.plan} Plan
                  </p>
                  <p className="mt-1 text-sm text-gray-500">
                    Status: <span className={`font-medium ${
                      subscription.status === 'active' ? 'text-green-600' : 'text-yellow-600'
                    }`}>
                      {subscription.status}
                    </span>
                  </p>
                </div>
                {subscription.plan !== 'free' && (
                  <button
                    onClick={handleManageBilling}
                    className="rounded-lg border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50"
                  >
                    Manage Billing
                  </button>
                )}
              </div>

              {/* Usage */}
              <div className="mt-6 grid grid-cols-2 gap-4">
                <div className="rounded-lg bg-gray-50 p-4">
                  <p className="text-sm text-gray-500">Scans Used</p>
                  <p className="mt-1 text-2xl font-bold text-gray-900">
                    {subscription.scans_used} <span className="text-lg font-normal text-gray-500">/ {subscription.scan_limit}</span>
                  </p>
                  <div className="mt-2 h-2 rounded-full bg-gray-200">
                    <div
                      className="h-2 rounded-full bg-brand-600"
                      style={{ width: `${Math.min(100, (subscription.scans_used / subscription.scan_limit) * 100)}%` }}
                    />
                  </div>
                </div>
                <div className="rounded-lg bg-gray-50 p-4">
                  <p className="text-sm text-gray-500">Repositories</p>
                  <p className="mt-1 text-2xl font-bold text-gray-900">
                    — <span className="text-lg font-normal text-gray-500">/ {subscription.repo_limit}</span>
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <p className="text-gray-500">Unable to load subscription data.</p>
          )}
        </div>
      </section>

      {/* Upgrade Options */}
      {subscription && subscription.plan === 'free' && (
        <section className="mt-8">
          <h2 className="text-lg font-semibold text-gray-900">Upgrade Your Plan</h2>
          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            {[
              { name: 'Pro', price: '$29/mo', plan: 'pro', features: ['15 repos', '500 scans', 'Slack'] },
              { name: 'Business', price: '$99/mo', plan: 'business', features: ['Unlimited repos', '5K scans', 'SSO'] },
              { name: 'Enterprise', price: '$249/mo', plan: 'enterprise', features: ['Unlimited all', 'SLA', 'Custom rules'] },
            ].map((tier) => (
              <div key={tier.plan} className="rounded-xl border border-gray-200 bg-white p-5">
                <h3 className="text-lg font-semibold text-gray-900">{tier.name}</h3>
                <p className="mt-1 text-2xl font-bold text-brand-600">{tier.price}</p>
                <ul className="mt-4 space-y-2">
                  {tier.features.map((f) => (
                    <li key={f} className="flex items-center gap-2 text-sm text-gray-600">
                      <span className="text-green-500">✓</span> {f}
                    </li>
                  ))}
                </ul>
                <button
                  onClick={() => handleUpgrade(tier.plan)}
                  className="mt-6 w-full rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-500 transition-colors"
                >
                  Upgrade to {tier.name}
                </button>
              </div>
            ))}
          </div>
        </section>
      )}

      {/* Integrations */}
      <section className="mt-8">
        <h2 className="text-lg font-semibold text-gray-900">Integrations</h2>
        <div className="mt-4 space-y-4">
          <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-5">
            <div className="flex items-center gap-3">
              <div className="text-2xl">🐙</div>
              <div>
                <p className="font-medium text-gray-900">GitHub</p>
                <p className="text-sm text-gray-500">Connected via GitHub App</p>
              </div>
            </div>
            <span className="inline-flex items-center rounded-full bg-green-100 px-3 py-0.5 text-xs font-medium text-green-800">
              Connected
            </span>
          </div>

          <div className="flex items-center justify-between rounded-xl border border-gray-200 bg-white p-5">
            <div className="flex items-center gap-3">
              <div className="text-2xl">💬</div>
              <div>
                <p className="font-medium text-gray-900">Slack</p>
                <p className="text-sm text-gray-500">Get cost alerts in Slack channels</p>
              </div>
            </div>
            <button className="rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-50">
              Connect
            </button>
          </div>
        </div>
      </section>
    </div>
  );
}
