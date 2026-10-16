import os
from typing import Dict, Any, Optional, List, Union, Literal
from pydantic import BaseModel, Field, field_validator

class ChoiceQuestion(BaseModel):
    type: Literal["choice"] = "choice"
    instructions: Optional[str] = None
    criteria: Dict[str, str] = Field(..., min_length=2, description="Map of choice key to descriptive criteria")

class NoulQuestion(BaseModel):
    type: Literal["noul"] = "noul"
    instructions: Optional[str] = None
    criteria: Optional[Union[Dict[str, str], List[str]]] = None

class ScoreQuestion(BaseModel):
    type: Literal["score"] = "score"
    instructions: Optional[str] = None
    criteria: List[str] = Field(..., min_length=2, description="Ordered list of criteria descriptions from lowest to highest")

QuestionDef = Union[ChoiceQuestion, NoulQuestion, ScoreQuestion]

class SystemOneRequest(BaseModel):
    model: Optional[str] = None
    state: str = Field(..., min_length=1, max_length=50000, description="Input text or context")
    questions: Dict[str, QuestionDef] = Field(..., min_length=1, description="Questions dictionary")

class DecisionsRequest(BaseModel):
    model: Optional[str] = None
    input: Optional[str] = None
    state: Optional[str] = None
    questions: Dict[str, QuestionDef] = Field(..., min_length=1)

    @field_validator("input", mode="before")
    @classmethod
    def check_input_present(cls, v, info):
        values = info.data
        if not v and not values.get("state"):
            raise ValueError("Either 'input' or 'state' must be provided and non-empty")
        return v or values.get("state")

class ChoiceAnswer(BaseModel):
    type: Literal["choice"] = "choice"
    choice: str
    confidence: float
    probabilities: Optional[Dict[str, float]] = None

class NoulAnswer(BaseModel):
    type: Literal["noul"] = "noul"
    noul: float = Field(..., ge=0.0, le=1.0, description="Calibrated probability of True/Yes")

class ScoreAnswer(BaseModel):
    type: Literal["score"] = "score"
    score: float
    confidence: Optional[float] = None
    level: Optional[int] = None
    legend: Optional[Dict[str, str]] = None
    probabilities: Optional[Dict[str, float]] = None

AnswerDef = Union[ChoiceAnswer, NoulAnswer, ScoreAnswer]

class DecisionMeta(BaseModel):
    model_config = {"protected_namespaces": (), "extra": "allow"}
    backend: str
    model_used: str
    is_calibrated: bool
    confidence_type: str
    latency_ms: float
    calibration_note: Optional[str] = None
    runtime_device: Optional[str] = None

class SystemOneResponse(BaseModel):
    model: str
    answers: Dict[str, Any]
    usage: Dict[str, int] = Field(default_factory=lambda: {"input_tokens": 0, "output_tokens": 0})
    decision_meta: Optional[DecisionMeta] = None
