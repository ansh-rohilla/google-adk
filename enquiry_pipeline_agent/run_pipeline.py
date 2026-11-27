import asyncio
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from agent import root_agent

APP_NAME = "enquiry_pipeline"
USER_ID = "student_demo"


async def main() -> None:
    session_service = InMemorySessionService()
    runner = Runner(agent=root_agent, app_name=APP_NAME, session_service=session_service)

    session = await session_service.create_session(app_name=APP_NAME, user_id=USER_ID)

    sample_message = (
        "Hi, I am Priya Sharma. I want to learn GenAI and MLOps. "
        "My total budget is around 20k right now."
    )
    print(f"User: {sample_message}\n")

    content = types.Content(role="user", parts=[types.Part(text=sample_message)])

    async for event in runner.run_async(
        user_id=USER_ID,
        session_id=session.id,
        new_message=content,
    ):
        if event.content and event.content.parts:
            for part in event.content.parts:
                if part.function_call:
                    print(
                        f"[{event.author}] -> tool call: {part.function_call.name}({part.function_call.args})",
                        flush=True,
                    )
                elif part.text and part.text.strip():
                    print(f"\n--- [{event.author}] ---\n{part.text.strip()}", flush=True)

    updated_session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session.id,
    )
    print("\n=== Final Session State Keys ===")
    for key, value in updated_session.state.items():
        print(f"- {key}: {repr(value)[:140]}")


if __name__ == "__main__":
    asyncio.run(main())
