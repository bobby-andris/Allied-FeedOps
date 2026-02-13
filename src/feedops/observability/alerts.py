"""Alert notification helpers for Slack and email.

This module provides fire-and-forget notification functions for job lifecycle
events. All functions gracefully degrade when environment variables are not
configured, logging warnings instead of raising exceptions.

Environment Variables:
- SLACK_WEBHOOK_URL: Slack incoming webhook URL
- RESEND_API_KEY: Resend API key for sending emails
- ALERT_EMAIL_TO: Default email recipient for alerts

Functions:
- send_slack_notification(): Send message to Slack via webhook
- send_email_alert(): Send email alert via Resend API
- notify_job_event(): High-level helper for job lifecycle notifications
"""

from __future__ import annotations

import json
import logging
import os
import urllib.request
from typing import Any

logger = logging.getLogger(__name__)


def send_slack_notification(message: str, channel: str | None = None) -> bool:
    """Send notification to Slack via webhook.

    Uses urllib.request (stdlib) to avoid adding new dependencies.
    Gracefully degrades if SLACK_WEBHOOK_URL not configured.

    Args:
        message: Message text to send
        channel: Optional channel override (currently unused - webhook determines channel)

    Returns:
        True if message sent successfully, False otherwise

    Example:
        send_slack_notification("Backfill job batch-123 started with 100 SKUs")
    """
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")

    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL not configured - skipping Slack notification")
        return False

    try:
        payload = {"text": message}
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status == 200:
                logger.debug(f"Slack notification sent: {message[:100]}")
                return True
            else:
                logger.warning(f"Slack notification failed with status {response.status}")
                return False

    except Exception as e:
        logger.error(f"Failed to send Slack notification: {e}")
        return False


def send_email_alert(subject: str, body: str, to_email: str | None = None) -> bool:
    """Send email alert via Resend API.

    Uses urllib.request (stdlib) to avoid adding new dependencies.
    Gracefully degrades if RESEND_API_KEY or recipient not configured.

    Args:
        subject: Email subject line
        body: Email body (plain text)
        to_email: Recipient email (defaults to ALERT_EMAIL_TO env var)

    Returns:
        True if email sent successfully, False otherwise

    Example:
        send_email_alert(
            subject="Backfill job failed",
            body="Job batch-123 failed with error: Connection timeout",
            to_email="alerts@allied-brass.com"
        )
    """
    api_key = os.environ.get("RESEND_API_KEY")
    recipient = to_email or os.environ.get("ALERT_EMAIL_TO")

    if not api_key:
        logger.warning("RESEND_API_KEY not configured - skipping email alert")
        return False

    if not recipient:
        logger.warning("No email recipient configured (to_email or ALERT_EMAIL_TO) - skipping email alert")
        return False

    try:
        payload = {
            "from": "FeedOps <alerts@feedops.allied-brass.com>",
            "to": [recipient],
            "subject": subject,
            "text": body,
        }
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=data,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        with urllib.request.urlopen(req, timeout=10) as response:
            if response.status in (200, 201):
                logger.debug(f"Email alert sent: {subject}")
                return True
            else:
                logger.warning(f"Email alert failed with status {response.status}")
                return False

    except Exception as e:
        logger.error(f"Failed to send email alert: {e}")
        return False


def notify_job_event(
    event_type: str,
    job_id: str,
    job_type: str,
    details: dict[str, Any] | None = None,
) -> None:
    """High-level helper for job lifecycle notifications.

    Formats and sends notifications based on event type. All sends are
    fire-and-forget (never raise exceptions).

    Event Types:
    - "started": Slack only - job started notification
    - "completed": Slack only - job completed successfully
    - "failed": BOTH Slack and email - job failed with error details

    Args:
        event_type: One of "started", "completed", "failed"
        job_id: Job UUID
        job_type: Job type (search_terms, performance_metrics, etc.)
        details: Optional dict with event details (total_items, completed, failed, error)

    Example:
        notify_job_event(
            event_type="started",
            job_id="abc-123",
            job_type="full_backfill",
            details={"total_items": 100}
        )
    """
    details = details or {}

    try:
        if event_type == "started":
            total_items = details.get("total_items", "unknown")
            message = f"Backfill job {job_id} ({job_type}) started with {total_items} SKUs"
            send_slack_notification(message)

        elif event_type == "completed":
            completed = details.get("completed", 0)
            total = details.get("total", 0)
            failed = details.get("failed", 0)
            message = f"Backfill job {job_id} completed: {completed}/{total} SKUs ({failed} failed)"
            send_slack_notification(message)

        elif event_type == "failed":
            error = details.get("error", "Unknown error")
            total = details.get("total", 0)
            completed = details.get("completed", 0)

            # Send both Slack and email for failures
            message = f"Backfill job {job_id} FAILED: {error} (processed {completed}/{total} SKUs)"
            send_slack_notification(message)

            # Email with more details
            email_body = f"""
Backfill Job Failure Report

Job ID: {job_id}
Job Type: {job_type}
Status: FAILED

Progress:
- Total SKUs: {total}
- Completed: {completed}
- Failed: {details.get('failed', 0)}

Error:
{error}

View job details:
https://allied-feed-ops.vercel.app/backfill/{job_id}
            """.strip()

            send_email_alert(
                subject=f"FeedOps Alert: {job_type} job {job_id[:8]} failed",
                body=email_body,
            )

        else:
            logger.warning(f"Unknown event type: {event_type}")

    except Exception as e:
        # Catch-all to ensure notification failures never affect job processing
        logger.error(f"Error in notify_job_event: {e}")
