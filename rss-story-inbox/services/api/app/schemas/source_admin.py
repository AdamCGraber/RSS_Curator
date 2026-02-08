from pydantic import BaseModel
from typing import Union


class BulkDeleteSources(BaseModel):
    source_ids: list[Union[int, str]]
