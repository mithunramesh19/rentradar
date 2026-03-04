"""SendGrid email notification dispatcher."""

from __future__ import annotations

import logging
from typing import Any

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Content, Email, Mail, To

logger = logging.getLogger(__name__)

_client: SendGridAPIClient | None = None


def _get_client(api_key: str) -> SendGridAPIClient:
    global _client
    if _client is None:
        _client = SendGridAPIClient(api_key)
    return _client


def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    *,
    api_key: str,
    from_email: str = "alerts@rentradar.app",
) -> bool:
    """Send email via SendGrid. Returns True on success."""
    client = _get_client(api_key)

    message = Mail(
        from_email=Email(from_email, "RentRadar"),
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", html_body),
    )

    try:
        response = client.send(message)
        logger.info("Email sent to %s — status %s", to_email, response.status_code)
        return 200 <= response.status_code < 300
    except Exception:
        logger.exception("SendGrid error sending to %s", to_email)
        return False


def render_listing_email(
    event_type: str,
    listings: list[dict[str, Any]],
    search_name: str = "your saved search",
) -> tuple[str, str]:
    """Render listing alert as subject + HTML body."""
    count = len(listings)
    subjects = {
        "listed": f"{count} new listing{'s' if count != 1 else ''} matching {search_name}",
        "price_drop": f"Price drop{'s' if count != 1 else ''} on {count} listing{'s' if count != 1 else ''}",
        "price_increase": f"Price increase on {count} listing{'s' if count != 1 else ''}",
        "relisted": f"{count} listing{'s' if count != 1 else ''} relisted",
        "removed": f"{count} listing{'s' if count != 1 else ''} removed",
    }
    subject = subjects.get(event_type, f"{count} listing update{'s' if count != 1 else ''}")

    rows = ""
    for listing in listings[:20]:
        address = listing.get("address", "Unknown")
        price = listing.get("price")
        price_str = f"${price:,.0f}/mo" if price else "N/A"
        beds = listing.get("bedrooms")
        beds_str = f"{beds} BR" if beds is not None else ""
        borough = listing.get("borough", "")
        listing_id = listing.get("id", "")

        badge = ""
        if event_type == "price_drop":
            old_price = listing.get("old_price")
            if old_price and price:
                badge = (
                    f'<span style="background:#22c55e;color:#fff;padding:2px 8px;'
                    f'border-radius:4px;font-size:12px;">-${old_price - price:,.0f}</span>'
                )

        rows += f"""
        <tr>
          <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;">
            <div style="font-weight:600;color:#111827;">{address}</div>
            <div style="color:#6b7280;font-size:13px;">{beds_str} · {borough}</div>
          </td>
          <td style="padding:12px 16px;border-bottom:1px solid #e5e7eb;text-align:right;">
            <div style="font-weight:600;color:#111827;">{price_str}</div>
            {badge}
          </td>
        </tr>"""

    overflow = ""
    if count > 20:
        overflow = (
            f'<p style="text-align:center;color:#6b7280;font-size:13px;">'
            f"and {count - 20} more listings</p>"
        )

    html = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f3f4f6;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;">
  <div style="max-width:600px;margin:0 auto;padding:24px 16px;">
    <div style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 1px 3px rgba(0,0,0,0.1);">
      <div style="background:#1e40af;padding:24px 20px;">
        <h1 style="margin:0;color:#fff;font-size:20px;">RentRadar Alert</h1>
        <p style="margin:4px 0 0;color:#93c5fd;font-size:14px;">{subject}</p>
      </div>
      <table style="width:100%;border-collapse:collapse;">
        {rows}
      </table>
      {overflow}
      <div style="padding:20px;text-align:center;">
        <a href="https://rentradar.app/listings"
           style="display:inline-block;background:#1e40af;color:#fff;padding:12px 24px;
                  border-radius:8px;text-decoration:none;font-weight:600;font-size:14px;">
          View All Listings
        </a>
      </div>
    </div>
    <p style="text-align:center;color:#9ca3af;font-size:12px;margin-top:16px;">
      You're receiving this because of your saved search "{search_name}".
      <a href="https://rentradar.app/settings/notifications" style="color:#6b7280;">Manage preferences</a>
    </p>
  </div>
</body>
</html>"""

    return subject, html
