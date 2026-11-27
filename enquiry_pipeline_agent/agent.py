from typing import Literal
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent, LoopAgent, SequentialAgent
from google.adk.tools import exit_loop

MODEL = "gemini-3.5-flash"

# ---------------------------------------------------------------------------
# Course Catalog & Lookup Tool (used by Advisor inside the LoopAgent)
# ---------------------------------------------------------------------------

COURSE_CATALOG = {
    "GenAI": {
        "title": "Generative AI Engineering",
        "duration_weeks": 12,
        "fee_inr": 18000,
        "highlights": "LLMs, RAG, Google ADK, MCP servers, and multi-agent systems",
    },
    "Data Science": {
        "title": "Applied Data Science & Machine Learning",
        "duration_weeks": 16,
        "fee_inr": 20000,
        "highlights": "Python, SQL, EDA, feature engineering, and classical ML",
    },
    "MLOps": {
        "title": "Production MLOps",
        "duration_weeks": 10,
        "fee_inr": 15000,
        "highlights": "Docker, CI/CD, model registries, monitoring, and deployment",
    },
    "Deep Learning": {
        "title": "Deep Learning & Computer Vision / NLP",
        "duration_weeks": 12,
        "fee_inr": 16000,
        "highlights": "PyTorch, neural architectures, transformers, and fine-tuning",
    },
    "Other": {
        "title": "Foundations & Custom Learning Track",
        "duration_weeks": 8,
        "fee_inr": 10000,
        "highlights": "Personalized mentorship and Python programming fundamentals",
    },
}


def lookup_course_catalog(course_name: str) -> dict:
    """Look up official CampusX course fee, duration, and curriculum highlights.

    Args:
        course_name: One of "GenAI", "Data Science", "MLOps", "Deep Learning", or "Other".

    Returns:
        A dict with course details if found, or an error message with valid keys.
    """
    course = COURSE_CATALOG.get(course_name)
    if not course:
        return {
            "status": "error",
            "error_message": f"Unknown course '{course_name}'. Valid options: {list(COURSE_CATALOG)}",
        }
    return {"status": "success", "course_name": course_name, **course}


# ---------------------------------------------------------------------------
# Stage 1: Structured Extraction (extends structured_output_agent)
# ---------------------------------------------------------------------------

class Enquiry(BaseModel):
    name: str | None = Field(default=None, description="Student's full name, properly capitalized")
    email: str | None = Field(default=None, description="Email address exactly as written")
    interested_in: list[Literal["GenAI", "Data Science", "MLOps", "Deep Learning", "Other"]] = Field(
        description="CampusX courses the student is interested in"
    )
    budget_inr: int | None = Field(
        default=None,
        ge=0,
        le=500000,
        description="Total budget in rupees as a plain number. Convert '15k' to 15000",
    )


extractor_agent = LlmAgent(
    name="extractor_agent",
    model=MODEL,
    description="Extracts structured student enquiry details from a message.",
    instruction=(
        "Read the student's message and extract their details into the Enquiry schema. "
        "If something is not mentioned, leave it empty. Never guess."
    ),
    output_schema=Enquiry,
    output_key="enquiry",
)


# ---------------------------------------------------------------------------
# Stage 2: Draft & Critique Refinement Loop (LoopAgent)
# ---------------------------------------------------------------------------

advisor_agent = LlmAgent(
    name="advisor_agent",
    model=MODEL,
    description="Drafts or revises a personalized CampusX course proposal.",
    instruction=(
        "You are a helpful CampusX admissions advisor.\n\n"
        "Extracted student enquiry:\n{enquiry}\n\n"
        "Previous reviewer feedback (empty on the first pass):\n{review_feedback?}\n\n"
        "Instructions:\n"
        "1. Call lookup_course_catalog for EVERY course listed in `interested_in`.\n"
        "2. Write a warm, concise proposal addressed to the student (`name` if present, "
        "otherwise a polite greeting).\n"
        "3. Include exact fee (in INR), duration, and highlights from the catalog—never invent numbers.\n"
        "4. Address `budget_inr`: if total fees exceed `budget_inr`, recommend starting with one "
        "course or a phased/EMI plan within budget; if `budget_inr` is null, ask for their budget.\n"
        "5. If `email` is present, note that the detailed syllabus will be sent there; if `email` is "
        "null, politely ask for their email address.\n"
        "6. If `review_feedback` is non-empty, fix every issue the reviewer flagged."
    ),
    tools=[lookup_course_catalog],
    output_key="proposal",
)

reviewer_agent = LlmAgent(
    name="reviewer_agent",
    model=MODEL,
    description="Audits the proposal against the extracted enquiry and exits the loop when ready.",
    instruction=(
        "You are a strict QA reviewer checking an admissions proposal before it is sent.\n\n"
        "Extracted student enquiry:\n{enquiry}\n\n"
        "Current proposal draft:\n{proposal}\n\n"
        "Check every requirement below:\n"
        "1. Student name is used accurately (or polite generic greeting if name is null).\n"
        "2. Every course in `interested_in` is covered, with no unrequested courses pushed.\n"
        "3. Budget (`budget_inr`) is explicitly addressed (fits budget, phased/EMI option if over "
        "budget, or politely asked if null).\n"
        "4. Email is handled properly (confirmed if present, politely requested if null).\n"
        "5. Tone is warm, concise, and clear.\n\n"
        "If ALL 5 criteria pass, call the `exit_loop` tool immediately and write `APPROVED`.\n"
        "If ANY criterion fails, do NOT call `exit_loop`. Instead, output a short numbered list "
        "of exact fixes the advisor must make."
    ),
    tools=[exit_loop],
    output_key="review_feedback",
)

refinement_loop = LoopAgent(
    name="refinement_loop",
    description="Iteratively drafts and reviews the course proposal until approved.",
    sub_agents=[advisor_agent, reviewer_agent],
    max_iterations=3,
)


# ---------------------------------------------------------------------------
# Stage 3: Final Presentation (SequentialAgent step after LoopAgent exits)
# ---------------------------------------------------------------------------

final_formatter_agent = LlmAgent(
    name="final_formatter_agent",
    model=MODEL,
    description="Presents the extracted enquiry summary and approved final proposal.",
    instruction=(
        "Present the final result cleanly in Markdown with two sections:\n"
        "1. **Extracted Enquiry** — summarize `{enquiry}` concisely.\n"
        "2. **Recommended Reply** — output the polished proposal from `{proposal}` verbatim "
        "(do not alter facts or numbers)."
    ),
)

root_agent = SequentialAgent(
    name="enquiry_pipeline",
    description=(
        "Multi-agent pipeline: extracts structured enquiry data, iteratively drafts and "
        "reviews a course proposal in a loop, and formats the final response."
    ),
    sub_agents=[extractor_agent, refinement_loop, final_formatter_agent],
)
