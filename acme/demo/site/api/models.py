from pydantic import BaseModel, EmailStr, Field


class WaitlistIn(BaseModel):
    email: EmailStr
    company: str = Field(default="", max_length=200)
    role: str = Field(default="", max_length=100)


class WaitlistOut(BaseModel):
    id: int
    status: str = "accepted"


class FeatureItem(BaseModel):
    icon: str
    title: str
    desc: str


class FeaturesOut(BaseModel):
    items: list[FeatureItem]
