from typing import List, Literal, Optional
from pydantic import BaseModel


class ActionItem(BaseModel):
    owner: str
    task: str
    deadline: Optional[str] = None


class MeetingOutput(BaseModel):
    summary: str
    action_items: List[ActionItem]
    sentiment: Literal["positive", "neutral", "negative"]
    next_step: str
