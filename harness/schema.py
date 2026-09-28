"""Fixed JSON schemas the models must answer in, so scoring never parses free text."""
from typing import Literal

from pydantic import BaseModel, Field


class SystemAnswer(BaseModel):
    """What the customer-support system returns for one question."""
    answer: str = Field(description="The reply to send to the customer.")
    policy_covers_question: bool = Field(
        description="True if the policy text contains the information needed to answer.")


class JudgeGrade(BaseModel):
    """The judge's grade for one answer, using the labelling guide's three checks."""
    correct: bool = Field(description="Everything the answer states agrees with the policy.")
    complete: bool = Field(description="Nothing is missing that would change what the customer does.")
    grounded: bool = Field(description="Every claim is supported by the policy; no guesses or inventions.")
    reason: str = Field(description="One or two sentences naming the decisive policy point.")

    @property
    def verdict(self):
        return "pass" if (self.correct and self.complete and self.grounded) else "fail"


class PairwiseChoice(BaseModel):
    """The judge's choice between two answers to the same question."""
    better: Literal["A", "B", "tie"] = Field(description="Which answer is better for the customer.")
    reason: str = Field(description="One or two sentences naming the decisive difference.")
