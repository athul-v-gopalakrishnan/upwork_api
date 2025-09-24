from typing import Sequence
from typing_extensions import Annotated, TypedDict, List, Optional
from pydantic import BaseModel,Field

from langchain_core.messages import SystemMessage,BaseMessage, AIMessage, HumanMessage, ToolMessage
from langgraph.graph.message import add_messages


class Milestone(BaseModel):
    title: str = Field(..., description="Title of the milestone")
    amount: float = Field(..., description="Amount for the milestone")
    due_date: str = Field(..., description="Due date for the milestone in YYYY-MM-DD format")
    
class QuestionAnswer(BaseModel):
    question: str = Field(..., description="The question asked by the client in the job posting")
    answer: str = Field(..., description="Your answer to the question")
    
class Proposal(BaseModel):
    cover_letter: str = Field(..., description="A well formatted cover letter for the job proposal.")
    questions_and_answers: List[QuestionAnswer] = Field(default_factory=list , description="List of questions and your answers")
    
class State(TypedDict):
    messages:Annotated[Sequence[BaseMessage],add_messages]
    rag_query:Optional[str]
    proposal:Optional[Proposal]
    project_details:Optional[str]
    retrieved_projects:Optional[str]