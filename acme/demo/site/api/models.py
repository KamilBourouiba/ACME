from pydantic import BaseModel, EmailStr, Field


class LeadIn(BaseModel):
    email: EmailStr
    company: str = Field(min_length=1, max_length=200)
    message: str = Field(default="", max_length=2000)


class LeadOut(BaseModel):
    id: int
    status: str = "accepted"


class ServiceItem(BaseModel):
    title: str
    desc: str


class ServicesOut(BaseModel):
    items: list[ServiceItem]
