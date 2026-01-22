"""User authorization and validation utilities."""
from typing import List, Optional
from config import settings
import re


def normalize_email(email: Optional[str]) -> str:
    """
    Normalize email address, converting @CC3solutions.com to @cc3solutions.com.
    
    Args:
        email: Email address to normalize
        
    Returns:
        Normalized email address (lowercase, stripped, with corrected domain)
    """
    if not email:
        return email or ""
    
    # Convert to string and strip whitespace
    normalized = str(email).strip()
    
    # Convert @CC3solutions.com to @cc3solutions.com (case-insensitive)
    # Match @CC3solutions.com or any case variation
    normalized = re.sub(
        r'@CC3solutions\.com$',
        '@cc3solutions.com',
        normalized,
        flags=re.IGNORECASE
    )
    
    # Apply general normalization (lowercase)
    normalized = normalized.lower()
    
    return normalized


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
