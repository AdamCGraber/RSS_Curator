from pydantic import BaseModel


class BulkDeleteSources(BaseModel):
    source_ids: list[int]
