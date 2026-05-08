from pydantic import BaseModel, Field
from typing import Literal, Optional, List
from datetime import datetime

JobStatus = Literal["queued", "running", "done", "error"]

class JobProgressEvent(BaseModel):
    ts: datetime = Field(default_factory=datetime.utcnow)
    step: str
    pct: Optional[int] = None
    message: str

class PromptItem(BaseModel):
    id: str
    characterName: str
    target: str = "generic"
    text: str
    edited: bool = False

class GeneratedCharacterPrompt(BaseModel):
    id: str
    main_name: str
    aliases: List[str] = Field(default_factory=list)
    description: str
    image_prompt: str
    confidence: Literal["low", "medium", "high"] = "medium"
    warnings: List[str] = Field(default_factory=list)

class JobResult(BaseModel):
    language: str
    characters: list[dict] = Field(default_factory=list)
    characters_text: str = ""
    prompts: list[PromptItem] = Field(default_factory=list)
    generated_characters: list[GeneratedCharacterPrompt] = Field(default_factory=list)

class JobState(BaseModel):
    job_id: str
    status: JobStatus = "queued"
    error: Optional[str] = None
    result: Optional[JobResult] = None
