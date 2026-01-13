"""User authorization and validation utilities."""
from typing import List
from config import settings


def is_user_allowed(email: str) -> bool:
    """
    Check if a user email is in the allowed users list.
    
    Args:
        email: User email address to check
        
    Returns:
        True if user is allowed, False otherwise
    """
    if not email:
        return False
    return email.lower().strip() in settings.allowed_users


def get_allowed_users() -> List[str]:
    """
    Get the list of allowed user emails.
    
    Returns:
        List of allowed user email addresses
    """
    return settings.allowed_users
