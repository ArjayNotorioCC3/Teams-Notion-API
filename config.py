"""Configuration management for the Teams-Notion middleware."""
from typing import List
from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # Microsoft Graph API credentials
    microsoft_client_id: str
    microsoft_client_secret: str
    microsoft_tenant_id: str
    
    # Notion API credentials
    notion_api_token: str
    notion_database_id: str
    
    # Allowed users (comma-separated email list)
    allowed_users: str
    
    # Webhook configuration
    webhook_notification_url: str
    webhook_client_state: str
    
    # Optional: Default status for new tickets
    default_ticket_status: str = "New"
    
    # Optional: Source identifier
    ticket_source: str = "Teams"
    
    @validator("allowed_users")
    def parse_allowed_users(cls, v):
        """Parse comma-separated email list."""
        if not v:
            raise ValueError("ALLOWED_USERS cannot be empty")
        return [email.strip().lower() for email in v.split(",") if email.strip()]
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()
