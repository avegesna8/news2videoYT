from pydantic import BaseModel, Field

#Response Model for Comedic Script Generation
class ComedicScriptResponse(BaseModel):
    script: str = Field(
        description="A comedic news script that a news character will read to deliver the news",
        min_length=100
    )
    is_too_long: bool = Field(
        description="Whether the article is too long to be included in the script",
        default=False
    )
