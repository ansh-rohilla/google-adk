from typing import Literal
from pydantic import BaseModel, Field

from google.adk.agents import LlmAgent, LoopAgent, ParallelAgent, SequentialAgent
from google.adk.tools import exit_loop

MODEL = "gemini-3.5-flash"

# ---------------------------------------------------------------------------
# Course Catalog & Specialist Tools (used by parallel research agents)
# ---------------------------------------------------------------------------

COURSE_CATALOG = {
    "GenAI": {
        "title": "Generative AI Engineering",
        "duration_weeks": 12,
        "fee_inr": 18000,
        "prerequisites": "Python basics and comfort with APIs / JSON.",
        "outcomes": "Build production RAG pipelines, MCP servers, and multi-agent systems with Google ADK.",
        "faqs": "Includes weekly live doubt sessions, lifetime recordings, and 2 capstone projects.",
    },
    "Data Science": {
        "title": "Applied Data Science & Machine Learning",
        "duration_weeks": 16,
        "fee_inr": 20000,
        "prerequisites": "Basic high-school math and introductory Python.",
        "outcomes": "End-to-end EDA, feature engineering, predictive modeling, and model evaluation.",
        "faqs": "Beginner-friendly; includes SQL + Python refresher in weeks 1-2 and 3 portfolio projects.",
    },
    "MLOps": {
        "title": "Production MLOps",
        "duration_weeks": 10,
        "fee_inr": 15000,
        "prerequisites": "Familiarity with Python, Git, and training basic ML models.",
        "outcomes": "Containerize ML services with Docker, automate CI/CD, and monitor drift in production.",
        "faqs": "Hands-on cloud deployment labs using free-tier cloud resources; weekend live classes.",
    },
    "Deep Learning": {
        "title": "Deep Learning & Computer Vision / NLP",
        "duration_weeks": 12,
        "fee_inr": 16000,
        "prerequisites": "Intermediate Python, NumPy, and foundational Machine Learning.",
        "outcomes": "Train and fine-tune CNNs, transformers, and custom PyTorch architectures.",
        "faqs": "Covers GPU workflows on Colab/Kaggle; no paid hardware required.",
    },
    "Other": {
        "title": "Foundations & Custom Learning Track",
        "duration_weeks": 8,
        "fee_inr": 10000,
        "prerequisites": "No prior coding experience required.",
        "outcomes": "Personalized mentorship and Python programming fundamentals.",
        "faqs": "Flexible 1-on-1 mentor check-ins to transition into specialized tracks afterward.",
    },
}

BUNDLE_DISCOUNT_RATE = 0.10


def calculate_pricing_plan(courses: list[str], budget_inr: int | None = None) -> dict:
    """Calculate itemized fees, bundle discount, EMI options, and budget fit.

    Args:
        courses: List of CampusX course keys (e.g. ["GenAI", "MLOps"]).
        budget_inr: Optional student budget in INR.

    Returns:
        A dict with itemized pricing, bundle total, 3/6-month EMI breakdowns,
        and courses that fit individually within budget_inr.
    """
    items = []
    unknown = []
    for name in courses:
        info = COURSE_CATALOG.get(name)
        if not info:
            unknown.append(name)
        else:
            items.append({
                "course": name,
                "title": info["title"],
                "fee_inr": info["fee_inr"],
                "duration_weeks": info["duration_weeks"],
            })

    if unknown:
        return {
            "status": "error",
            "error_message": f"Unknown courses: {unknown}. Valid options: {list(COURSE_CATALOG)}",
        }

    subtotal_inr = sum(item["fee_inr"] for item in items)
    discount_inr = int(subtotal_inr * BUNDLE_DISCOUNT_RATE) if len(items) >= 2 else 0
    final_total_inr = subtotal_inr - discount_inr

    within_budget = None if budget_inr is None else final_total_inr <= budget_inr
    affordable_single_courses = (
        [item["course"] for item in items if item["fee_inr"] <= budget_inr]
        if budget_inr is not None
        else []
    )

    return {
        "status": "success",
        "items": items,
        "subtotal_inr": subtotal_inr,
        "bundle_discount_inr": discount_inr,
        "final_total_inr": final_total_inr,
        "emi_3_months_inr": round(final_total_inr / 3),
        "emi_6_months_inr": round(final_total_inr / 6),
        "budget_inr": budget_inr,
        "within_budget": within_budget,
        "affordable_single_courses": affordable_single_courses,
    }


def lookup_curriculum_and_faqs(course_name: str) -> dict:
    """Look up prerequisites, project outcomes, duration, and FAQs for a course.

    Args:
        course_name: One of "GenAI", "Data Science", "MLOps", "Deep Learning", or "Other".

    Returns:
        A dict with curriculum details and FAQs, or an error if unknown.
    """
    course = COURSE_CATALOG.get(course_name)
    if not course:
        return {
            "status": "error",
            "error_message": f"Unknown course '{course_name}'. Valid options: {list(COURSE_CATALOG)}",
        }
    return {
        "status": "success",
        "course_name": course_name,
        "title": course["title"],
        "duration_weeks": course["duration_weeks"],
        "prerequisites": course["prerequisites"],
        "outcomes": course["outcomes"],
        "faqs": course["faqs"],
    }


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
# Stage 2: Parallel Research Fan-Out (ParallelAgent)
# Both sub-agents run concurrently and write to disjoint output_keys.
# ---------------------------------------------------------------------------

pricing_agent = LlmAgent(
    name="pricing_agent",
    model=MODEL,
    description="Computes itemized pricing, bundle discounts, EMIs, and budget fit.",
    instruction=(
        "You are a CampusX fee and payment-plan specialist.\n\n"
        "Extracted student enquiry:\n{enquiry}\n\n"
        "Call `calculate_pricing_plan` once with `courses` set to `interested_in` and "
        "`budget_inr` from the enquiry. Then summarize the exact itemized fees, any 10% "
        "bundle discount, 3-month and 6-month EMI numbers, and whether the total fits "
        "`budget_inr` (or which single course fits if over budget)."
    ),
    tools=[calculate_pricing_plan],
    output_key="pricing_plan",
)

curriculum_agent = LlmAgent(
    name="curriculum_agent",
    model=MODEL,
    description="Fetches course prerequisites, learning outcomes, and FAQs.",
    instruction=(
        "You are a CampusX academic advisor.\n\n"
        "Extracted student enquiry:\n{enquiry}\n\n"
        "Call `lookup_curriculum_and_faqs` for EVERY course in `interested_in`. "
        "Summarize each course's duration, prerequisites, hands-on outcomes, and key FAQs "
        "clearly and concisely."
    ),
    tools=[lookup_curriculum_and_faqs],
    output_key="curriculum_notes",
)

research_parallel = ParallelAgent(
    name="research_parallel",
    description="Runs pricing analysis and curriculum/FAQ lookup concurrently.",
    sub_agents=[pricing_agent, curriculum_agent],
)


# ---------------------------------------------------------------------------
# Stage 3: Draft & Critique Refinement Loop (LoopAgent)
# ---------------------------------------------------------------------------

advisor_agent = LlmAgent(
    name="advisor_agent",
    model=MODEL,
    description="Synthesizes enquiry, pricing plan, and curriculum notes into a proposal.",
    instruction=(
        "You are a helpful CampusX admissions advisor.\n\n"
        "Extracted student enquiry:\n{enquiry}\n\n"
        "Pricing & EMI analysis (from pricing_agent):\n{pricing_plan}\n\n"
        "Curriculum, prerequisites & FAQs (from curriculum_agent):\n{curriculum_notes}\n\n"
        "Previous reviewer feedback (empty on the first pass):\n{review_feedback?}\n\n"
        "Instructions:\n"
        "1. Write a warm, concise proposal addressed to the student (`name` if present, "
        "otherwise a polite greeting).\n"
        "2. Cover EVERY course in `interested_in` using exact fees, durations, prerequisites, "
        "and outcomes from `pricing_plan` and `curriculum_notes`—never invent numbers.\n"
        "3. Address `budget_inr`: mention any bundle discount and EMI options from `pricing_plan`, "
        "and if over budget recommend starting with an affordable single course or EMI plan "
        "(if `budget_inr` is null, ask for their budget).\n"
        "4. If `email` is present, note that the detailed syllabus will be sent there; if `email` is "
        "null, politely ask for their email address.\n"
        "5. If `review_feedback` is non-empty, fix every issue the reviewer flagged."
    ),
    output_key="proposal",
)

reviewer_agent = LlmAgent(
    name="reviewer_agent",
    model=MODEL,
    description="Audits the proposal against enquiry, pricing, and curriculum facts.",
    instruction=(
        "You are a strict QA reviewer checking an admissions proposal before it is sent.\n\n"
        "Extracted student enquiry:\n{enquiry}\n\n"
        "Verified pricing plan:\n{pricing_plan}\n\n"
        "Verified curriculum notes:\n{curriculum_notes}\n\n"
        "Current proposal draft:\n{proposal}\n\n"
        "Check every requirement below:\n"
        "1. Student name is used accurately (or polite generic greeting if name is null).\n"
        "2. Every course in `interested_in` is covered with accurate fees, durations, and "
        "key prerequisites/outcomes from the verified notes, with no unrequested courses pushed.\n"
        "3. Budget (`budget_inr`) is explicitly addressed using exact bundle/EMI/phased numbers "
        "from `pricing_plan` (or politely asked if null).\n"
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
# Stage 4: Final Presentation (SequentialAgent step after LoopAgent exits)
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
        "Multi-agent pipeline: extracts structured enquiry data, runs parallel pricing and "
        "curriculum research, iteratively drafts and reviews a proposal, and formats the output."
    ),
    sub_agents=[extractor_agent, research_parallel, refinement_loop, final_formatter_agent],
)
