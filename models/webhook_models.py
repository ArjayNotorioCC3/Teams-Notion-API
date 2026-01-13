"""Pydantic models for Microsoft Graph webhook payloads."""
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ResourceData(BaseModel):
    """Resource data in webhook notification."""
    id: Optional[str] = None
    odata_id: Optional[str] = Field(None, alias="@odata.id")
    odata_etag: Optional[str] = Field(None, alias="@odata.etag")
    odata_type: Optional[str] = Field(None, alias="@odata.type")


class ChangeNotification(BaseModel):
    """Individual change notification."""
    changeType: str
    clientState: Optional[str] = None
    resource: str
    resourceData: Optional[ResourceData] = None
    subscriptionExpirationDateTime: Optional[datetime] = None
    subscriptionId: str
    tenantId: Optional[str] = None


class Notification(BaseModel):
    """Webhook notification payload from Microsoft Graph."""
    value: List[ChangeNotification]
    validationTokens: Optional[List[str]] = None


class MessageReaction(BaseModel):
    """Message reaction information."""
    reactionType: str
    user: Dict[str, Any]


class MessageAttachment(BaseModel):
    """Message attachment information."""
    id: str
    contentUrl: Optional[str] = None
    name: Optional[str] = None
    contentType: Optional[str] = None


class MessageBody(BaseModel):
    """Message body content."""
    content: str
    contentType: str = "html"


class MessageFrom(BaseModel):
    """Message sender information."""
    user: Optional[Dict[str, Any]] = None
    application: Optional[Dict[str, Any]] = None


class ChannelIdentity(BaseModel):
    """Channel identity information."""
    teamId: Optional[str] = None
    channelId: Optional[str] = None


class GraphMessage(BaseModel):
    """Microsoft Graph message object."""
    id: str
    messageType: Optional[str] = None
    createdDateTime: Optional[datetime] = None
    lastModifiedDateTime: Optional[datetime] = None
    subject: Optional[str] = None
    body: Optional[MessageBody] = None
    from_: Optional[MessageFrom] = Field(None, alias="from")
    channelIdentity: Optional[ChannelIdentity] = None
    attachments: Optional[List[MessageAttachment]] = None
    reactions: Optional[List[MessageReaction]] = None
