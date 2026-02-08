/**
 * InfraCents API Client
 *
 * Provides type-safe methods for calling the InfraCents backend API.
 * All methods accept a Clerk JWT token for authentication.
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  /**
   * Make an authenticated API request.
   */
  private async request<T>(
    path: string,
    token: string,
    options: RequestInit = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const headers: Record<string, string> = {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers as Record<string, string> || {}),
    };

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(error.detail || `API error: ${response.status}`);
    }

    return response.json();
  }

  // ---------------------------------------------------------------------------
  // Dashboard Endpoints
  // ---------------------------------------------------------------------------

  /** Get the organization-level cost overview. */
  async getDashboardOverview(token: string, period: string = '30d'): Promise<any> {
    return this.request(`/api/dashboard/overview?period=${period}`, token);
  }

  /** List all repositories for the organization. */
  async getRepos(token: string, page: number = 1, perPage: number = 20): Promise<any> {
    return this.request(`/api/dashboard/repos?page=${page}&per_page=${perPage}`, token);
  }

  /** Get detailed view for a specific repository. */
  async getRepoDetail(token: string, repoId: string, period: string = '30d'): Promise<any> {
    return this.request(`/api/dashboard/repos/${repoId}?period=${period}`, token);
  }

  /** Get full details for a specific scan. */
  async getScanDetail(token: string, scanId: string): Promise<any> {
    return this.request(`/api/dashboard/scans/${scanId}`, token);
  }

  // ---------------------------------------------------------------------------
  // Billing Endpoints
  // ---------------------------------------------------------------------------

  /** Get the current subscription status. */
  async getSubscription(token: string): Promise<any> {
    return this.request('/api/billing/subscription', token);
  }

  /** Create a Stripe Checkout session for upgrading. */
  async createCheckout(
    token: string,
    data: { plan: string; success_url: string; cancel_url: string },
  ): Promise<{ checkout_url: string; session_id: string }> {
    return this.request('/api/billing/checkout', token, {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  /** Create a Stripe Customer Portal session. */
  async createPortal(token: string): Promise<{ portal_url: string }> {
    return this.request('/api/billing/portal', token, {
      method: 'POST',
    });
  }

  // ---------------------------------------------------------------------------
  // Health
  // ---------------------------------------------------------------------------

  /** Check if the API is healthy (no auth required). */
  async healthCheck(): Promise<{ status: string; version: string }> {
    const response = await fetch(`${this.baseUrl}/health`);
    return response.json();
  }
}

/** Singleton API client instance. */
export const apiClient = new ApiClient();
