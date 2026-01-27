from pydantic import BaseModel

class SourceCreate(BaseModel):
    name: str
    feed_url: str

class SourceOut(BaseModel):
    id: int
    name: str
    feed_url: str
    active: bool

    class Config:
        from_attributes = True
