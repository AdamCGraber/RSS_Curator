from pydantic import BaseModel

class ProfileOut(BaseModel):
    id: int
    audience_text: str
    tone_text: str
    include_terms: str
    include_terms_2: str
    exclude_terms: str

    class Config:
        from_attributes = True

class ProfileUpdate(BaseModel):
    audience_text: str
    tone_text: str
    include_terms: str = ""
    include_terms_2: str = ""
    exclude_terms: str = ""
