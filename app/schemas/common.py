from typing import Generic
from typing import Literal
from typing import TypeVar

from pydantic import BaseModel

DataT = TypeVar("DataT")


class Pagination(BaseModel):
    page: int
    page_size: int
    total: int
    total_pages: int


class SuccessEnvelope(BaseModel, Generic[DataT]):
    success: Literal[True] = True
    message: str = "ok"
    data: DataT
    trace_id: str
    pagination: Pagination | None = None


class ErrorEnvelope(BaseModel):
    success: Literal[False] = False
    message: str
    error_code: str
    data: None = None
    trace_id: str
