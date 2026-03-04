"""Firebase FCM push notification dispatcher."""

from __future__ import annotations

import logging
from typing import Any

import firebase_admin
from firebase_admin import credentials, messaging

logger = logging.getLogger(__name__)

_app: firebase_admin.App | None = None


def _get_app(credentials_path: str) -> firebase_admin.App:
    """Lazily initialize Firebase app."""
    global _app
    if _app is None:
        cred = credentials.Certificate(credentials_path)
        _app = firebase_admin.initialize_app(cred)
    return _app


def send_push(
    device_tokens: list[str],
    title: str,
    body: str,
    data: dict[str, str] | None = None,
    *,
    credentials_path: str = "./firebase-credentials.json",
) -> list[str]:
    """Send push notification via FCM.

    Returns list of tokens that failed (for cleanup).
    """
    if not device_tokens:
        return []

    _get_app(credentials_path)

    notification = messaging.Notification(title=title, body=body)
    message = messaging.MulticastMessage(
        tokens=device_tokens,
        notification=notification,
        data=data or {},
        android=messaging.AndroidConfig(
            priority="high",
            notification=messaging.AndroidNotification(
                click_action="OPEN_LISTING",
            ),
        ),
        apns=messaging.APNSConfig(
            payload=messaging.APNSPayload(
                aps=messaging.Aps(sound="default", badge=1),
            ),
        ),
    )

    response = messaging.send_each_for_multicast(message)

    failed_tokens: list[str] = []
    for i, send_response in enumerate(response.responses):
        if send_response.exception is not None:
            failed_tokens.append(device_tokens[i])
            logger.warning(
                "FCM send failed for token %s: %s",
                device_tokens[i][:8],
                send_response.exception,
            )

    logger.info(
        "FCM push: %d sent, %d failed",
        response.success_count,
        response.failure_count,
    )
    return failed_tokens


def format_listing_notification(
    event_type: str,
    listing: dict[str, Any],
) -> tuple[str, str, dict[str, str]]:
    """Format listing event into push notification title/body/data."""
    address = listing.get("address", "Unknown address")
    price = listing.get("price")
    price_str = f"${price:,.0f}/mo" if price else "Price N/A"
    beds = listing.get("bedrooms")
    beds_str = f"{beds}BR" if beds is not None else ""
    borough = listing.get("borough", "")

    titles = {
        "listed": "New Listing",
        "price_drop": "Price Drop",
        "price_increase": "Price Increase",
        "relisted": "Relisted",
        "removed": "Listing Removed",
    }
    title = titles.get(event_type, "Listing Update")

    if event_type == "price_drop":
        old_price = listing.get("old_price")
        drop = ""
        if old_price and price:
            drop = f" (-${old_price - price:,.0f})"
        body = f"{beds_str} {address} now {price_str}{drop}"
    elif event_type == "listed":
        body = f"{beds_str} in {borough} — {price_str}"
    else:
        body = f"{beds_str} {address} — {price_str}"

    data = {
        "event_type": event_type,
        "listing_id": str(listing.get("id", "")),
    }

    return title, body.strip(), data
