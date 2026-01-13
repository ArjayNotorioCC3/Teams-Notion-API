"""Microsoft Graph subscription normalization and validation utilities."""
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
import logging

logger = logging.getLogger(__name__)

# Teams message subscriptions have a maximum expiration of 1 hour
TEAMS_MAX_EXPIRATION = timedelta(hours=1)


def normalize_graph_subscription(
    *,
    resource: str,
    change_types: List[str],
    notification_url: str,
    lifecycle_notification_url: Optional[str],
    expiration_datetime: Optional[datetime],
    client_state: str,
) -> Dict[str, str]:
    """
    Normalize and validate Microsoft Graph subscription payload.

    This enforces ALL Microsoft Graph rules for Teams message subscriptions
    and prevents misleading 'validation timed out' errors.

    Args:
        resource: Resource path to subscribe to
        change_types: List of change types (e.g., ["created", "updated"])
        notification_url: URL to receive notifications
        lifecycle_notification_url: URL for lifecycle notifications
        expiration_datetime: Subscription expiration datetime
        client_state: Client state for webhook validation

    Returns:
        Normalized subscription payload dictionary

    Raises:
        ValueError: If required fields are missing for Teams subscriptions
    """
    # --- Resource MUST start with '/'
    if not resource.startswith("/"):
        logger.warning("Normalizing resource to start with '/'")
        resource = "/" + resource

    now = datetime.now(timezone.utc)

    # --- Expiration (default + clamp)
    if expiration_datetime is None:
        expiration_datetime = now + TEAMS_MAX_EXPIRATION

    # --- Teams messages rules
    is_teams_messages = resource.startswith("/teams/") and "/messages" in resource

    if is_teams_messages:
        # changeType - Teams messages ONLY support "created"
        if change_types != ["created"]:
            logger.warning(
                "Teams messages only support changeType=['created']. "
                f"Filtering from: {change_types}"
            )
            change_types = ["created"]

        # expiration ≤ 1 hour
        if expiration_datetime - now > TEAMS_MAX_EXPIRATION:
            logger.warning("Capping Teams subscription expiration to 1 hour")
            expiration_datetime = now + TEAMS_MAX_EXPIRATION

        # lifecycleNotificationUrl REQUIRED for Teams messages
        if not lifecycle_notification_url:
            raise ValueError(
                "lifecycleNotificationUrl is REQUIRED for Teams message subscriptions"
            )

    # --- Format datetime to ISO 8601 with Z (not +00:00)
    expiration_str = expiration_datetime.isoformat()
    if expiration_str.endswith("+00:00"):
        expiration_str = expiration_str.replace("+00:00", "Z")
    elif not expiration_str.endswith("Z"):
        expiration_str += "Z"

    # Build payload
    payload = {
        "resource": resource,
        "changeType": ",".join(change_types),
        "notificationUrl": notification_url,
        "expirationDateTime": expiration_str,
        "clientState": client_state,
    }

    # Add lifecycleNotificationUrl if provided
    if lifecycle_notification_url:
        payload["lifecycleNotificationUrl"] = lifecycle_notification_url

    return payload
