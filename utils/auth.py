"""Authentication helpers."""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def verify_webhook_client_state(client_state: Optional[str]) -> bool:
    """
    Verify webhook client state matches configured value.
    
    Args:
        client_state: Client state from webhook notification
        
    Returns:
        True if client state matches, False otherwise
    """
    from config import settings
    return client_state == settings.webhook_client_state
