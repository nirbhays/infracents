"""
PR Comment Formatting

Generates beautiful, informative Markdown comments for GitHub PRs.
The comment includes:
- Summary headline with cost delta
- Per-resource cost breakdown table
- Provider-level subtotals
- Confidence indicators
- Links back to the dashboard
"""

from __future__ import annotations

from models.pricing import CostConfidence, CostEstimate, ResourceCost
from models.terraform import ResourceAction

# Marker used to identify InfraCents comments (for edit-in-place)
COMMENT_MARKER = "<!-- infracents-cost-estimate -->"


def format_pr_comment(
    estimate: CostEstimate,
    pr_number: int,
    repo_name: str,
    dashboard_url: str = "https://infracents.dev/dashboard",
) -> str:
    """Format a CostEstimate into a beautiful Markdown PR comment.

    Args:
        estimate: The cost estimate to format.
        pr_number: The PR number (for dashboard link).
        repo_name: The repository name (for dashboard link).
        dashboard_url: Base URL for the dashboard.

    Returns:
        A formatted Markdown string ready to post as a PR comment.
    """
    lines: list[str] = [COMMENT_MARKER, ""]

    # Header with emoji and summary
    delta = estimate.cost_delta
    delta_pct = estimate.cost_delta_percent

    if delta > 0:
        emoji = "📈"
        direction = "increase"
        color_indicator = "🔴"
    elif delta < 0:
        emoji = "📉"
        direction = "decrease"
        color_indicator = "🟢"
    else:
        emoji = "➡️"
        direction = "no change to"
        color_indicator = "⚪"

    lines.append(f"## {emoji} InfraCents Cost Estimate")
    lines.append("")

    # Main summary line
    if delta != 0:
        lines.append(
            f"> {color_indicator} This change will **{direction}** monthly costs by "
            f"**~${abs(delta):,.2f}/mo** ({'+' if delta > 0 else ''}{delta_pct:.1f}%)"
        )
    else:
        lines.append("> ⚪ This change has **no estimated cost impact**")

    lines.append("")

    # Cost summary box
    lines.append("### 💰 Cost Summary")
    lines.append("")
    lines.append("| | Monthly Cost |")
    lines.append("|---|---:|")
    lines.append(f"| **Before** | ${estimate.total_monthly_cost_before:,.2f} |")
    lines.append(f"| **After** | ${estimate.total_monthly_cost_after:,.2f} |")
    lines.append(
        f"| **Delta** | {'+' if delta >= 0 else ''}"
        f"${delta:,.2f} ({'+' if delta_pct >= 0 else ''}{delta_pct:.1f}%) |"
    )
    lines.append("")

    # Resource breakdown
    if estimate.resources:
        lines.append("### 📋 Resource Breakdown")
        lines.append("")
        lines.append("| Resource | Type | Action | Cost Delta | Confidence |")
        lines.append("|----------|------|--------|----------:|------------|")

        for resource in estimate.resources:
            action_emoji = _action_emoji(resource)
            confidence_indicator = _confidence_indicator(resource.confidence)
            cost_str = _format_delta(resource.monthly_cost)
            resource_display = _truncate(resource.resource_name, 30)
            type_display = _format_resource_type(resource.resource_type)

            lines.append(
                f"| `{resource_display}` | {type_display} | {action_emoji} | {cost_str} | {confidence_indicator} |"
            )

        lines.append("")

    # Provider breakdown (if multi-provider)
    providers = estimate.cost_by_provider
    if len(providers) > 1:
        lines.append("### ☁️ By Provider")
        lines.append("")
        lines.append("| Provider | Cost Delta |")
        lines.append("|----------|----------:|")
        for provider, cost in sorted(providers.items()):
            provider_name = {"aws": "AWS", "gcp": "Google Cloud"}.get(provider, provider.upper())
            lines.append(f"| {provider_name} | {_format_delta(cost)} |")
        lines.append("")

    # Cost components detail (for high-cost resources)
    high_cost_resources = [r for r in estimate.resources if abs(r.monthly_cost) >= 10]
    if high_cost_resources:
        lines.append("<details>")
        lines.append("<summary>📊 Detailed Cost Breakdown</summary>")
        lines.append("")
        for resource in high_cost_resources:
            lines.append(f"**{resource.resource_type}.{resource.resource_name}** — {_format_delta(resource.monthly_cost)}")
            if resource.cost_components:
                lines.append("")
                lines.append("| Component | Unit Price | Quantity | Cost |")
                lines.append("|-----------|----------:|----------:|-----:|")
                for comp in resource.cost_components:
                    lines.append(
                        f"| {comp.name} | ${comp.unit_price:.4f}/{comp.unit} | "
                        f"{comp.quantity:,.1f} | ${comp.monthly_cost:,.2f} |"
                    )
                lines.append("")
            if resource.notes:
                lines.append(f"_{resource.notes}_")
                lines.append("")
        lines.append("</details>")
        lines.append("")

    # Confidence note
    has_low_confidence = any(
        r.confidence == CostConfidence.LOW for r in estimate.resources
    )
    has_fallback = any(r.is_fallback for r in estimate.resources)

    if has_low_confidence or has_fallback:
        lines.append("---")
        lines.append("")
        lines.append("⚠️ **Note:** Some estimates have lower confidence due to usage-dependent pricing. "
                      "Actual costs may vary based on traffic, storage usage, and data transfer.")
        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(
        f"<sub>💡 [View full history]({dashboard_url}/{repo_name}) · "
        f"Powered by [InfraCents](https://infracents.dev) · "
        f"Confidence: ⭐⭐⭐ High · ⭐⭐ Medium · ⭐ Low</sub>"
    )

    return "\n".join(lines)


def format_scan_limit_comment(
    plan: str,
    current_usage: int,
    limit: int,
) -> str:
    """Format a comment when the org has exceeded their scan limit.

    Args:
        plan: Current plan tier name.
        current_usage: Current scan count this period.
        limit: Scan limit for the current plan.

    Returns:
        Markdown comment suggesting an upgrade.
    """
    lines = [
        COMMENT_MARKER,
        "",
        "## ⚠️ InfraCents — Scan Limit Reached",
        "",
        f"> Your organization has used **{current_usage}/{limit}** scans "
        f"this month on the **{plan.capitalize()}** plan.",
        "",
        "To continue receiving cost estimates on your PRs, please upgrade your plan:",
        "",
        "| Plan | Scans/Month | Price |",
        "|------|------------|-------|",
        "| Pro | 500 | $29/mo |",
        "| Business | 5,000 | $99/mo |",
        "| Enterprise | Unlimited | $249/mo |",
        "",
        "👉 [Upgrade Now](https://infracents.dev/dashboard/settings)",
        "",
        "---",
        "<sub>Powered by [InfraCents](https://infracents.dev)</sub>",
    ]
    return "\n".join(lines)


def format_error_comment(error_message: str) -> str:
    """Format an error comment when cost estimation fails."""
    lines = [
        COMMENT_MARKER,
        "",
        "## ❌ InfraCents — Estimation Failed",
        "",
        f"> Cost estimation encountered an error: {error_message}",
        "",
        "This may be due to:",
        "- Unsupported Terraform resource types",
        "- Cloud pricing API unavailability",
        "- Complex Terraform configurations (modules, dynamic blocks)",
        "",
        "If this persists, please [open an issue](https://github.com/infracents/infracents/issues).",
        "",
        "---",
        "<sub>Powered by [InfraCents](https://infracents.dev)</sub>",
    ]
    return "\n".join(lines)


# =============================================================================
# Helper Functions
# =============================================================================


def _action_emoji(resource: ResourceCost) -> str:
    """Get an emoji + label for a resource action."""
    cost = resource.monthly_cost
    if cost > 0:
        return "🆕 Add"
    elif cost < 0:
        return "🗑️ Remove"
    else:
        return "✏️ Modify"


def _confidence_indicator(confidence: CostConfidence) -> str:
    """Convert confidence level to star rating."""
    return {
        CostConfidence.HIGH: "⭐⭐⭐",
        CostConfidence.MEDIUM: "⭐⭐",
        CostConfidence.LOW: "⭐",
    }.get(confidence, "⭐")


def _format_delta(cost: float) -> str:
    """Format a cost delta as a signed string."""
    if cost >= 0:
        return f"+${cost:,.2f}"
    else:
        return f"-${abs(cost):,.2f}"


def _format_resource_type(resource_type: str) -> str:
    """Format a resource type for display (shorter, more readable)."""
    # Remove provider prefix for readability
    parts = resource_type.split("_", 1)
    if len(parts) > 1:
        return parts[1].replace("_", " ").title()
    return resource_type


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max length with ellipsis."""
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"
