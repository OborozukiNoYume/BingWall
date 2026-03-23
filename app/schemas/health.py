from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class LiveHealthResponse(BaseModel):
    status: Literal["ok"]
    service: str
    environment: Literal["development", "test", "production"]
    timestamp: datetime
