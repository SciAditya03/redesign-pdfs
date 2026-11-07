from pydantic import BaseModel, Field
from typing import Literal

class DesignTokens(BaseModel):
    page_size: Literal["A4", "Letter"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    primary_color: str = "#191F5B"
    accent_color: str = "#079B4B"
    background_color: str = "#FFFFFF"
    surface_color: str = "#EEF0F8"
    heading_font: str = "Poppins"
    body_font: str = "Inter"
    label_font: str = "IBM Plex Mono"
    style_notes: list[str] = Field(default_factory=list)

class DesignSpec(BaseModel):
    tokens: DesignTokens = Field(default_factory=DesignTokens)
    page_types: list[str] = Field(default_factory=lambda: ["cover", "contents", "section_opener", "content", "glossary", "index"])
    components: dict = Field(default_factory=dict)
    observations: list[str] = Field(default_factory=list)
    confidence_notes: list[str] = Field(default_factory=list)
