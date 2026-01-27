from pydantic import BaseModel

class ActionRequest(BaseModel):
    action: str  # keep | reject | defer
