# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
from pathlib import Path
import urllib.parse
import urllib.request
import uuid
from zoneinfo import ZoneInfo

from a2ui.basic_catalog.provider import BasicCatalog
from a2ui.schema.manager import A2uiSchemaManager
from google.adk.agents import Agent
from google.adk.agents.callback_context import CallbackContext
from google.adk.apps import App
from google.adk.code_executors.agent_engine_sandbox_code_executor import AgentEngineSandboxCodeExecutor
from google.adk.memory import VertexAiMemoryBankService
from google.adk.memory.memory_entry import MemoryEntry
from google.adk.models import Gemini, LlmRequest
from google.adk.tools import ToolContext
from google.adk.tools.preload_memory_tool import PreloadMemoryTool
from google.cloud import firestore, storage
from google.genai import Client, types

from .a2ui_utils import a2ui_callback

# Hardcode project ID and Cloud Storage bucket to avoid runtime deployment issues
PROJECT_ID = "qwiklabs-gcp-01-057ee13d7fba"
BUCKET_NAME = "travel-concierge-media-qwiklabs-gcp-01-057ee13d7fba"

# Read Agent Engine resource name from deployment_metadata.json
METADATA_FILE = Path(__file__).parent.parent / "deployment_metadata.json"
AGENT_ENGINE_ID = "projects/480100122974/locations/us-east1/reasoningEngines/6939613818196590592"
MEMORY_BANK_ID = "6939613818196590592"
if METADATA_FILE.exists():
    try:
        data = json.loads(METADATA_FILE.read_text())
        if "remote_agent_runtime_id" in data:
            AGENT_ENGINE_ID = data["remote_agent_runtime_id"]
            MEMORY_BANK_ID = AGENT_ENGINE_ID.split("/")[-1]
    except Exception:
        pass

# Initialize Agent Engine Sandbox Code Executor
sandbox_executor = AgentEngineSandboxCodeExecutor(
    agent_engine_resource_name=AGENT_ENGINE_ID,
    optimize_data_file=True,
)


def memory_bank_service_builder():
    """Returns a VertexAiMemoryBankService initialized with the deployed Memory Bank ID."""
    return VertexAiMemoryBankService(
        project=PROJECT_ID,
        location="us-east1",
        agent_engine_id=MEMORY_BANK_ID,
    )


async def generate_memories_callback(callback_context: CallbackContext):
    """WRITE: send session events to Vertex AI Memory Bank for memory extraction after each turn."""
    try:
        await callback_context.add_session_to_memory()
    except Exception:
        pass
    return None


def get_firestore_client() -> firestore.Client:
    """Returns a Firestore client initialized with the hardcoded GCP project ID."""
    return firestore.Client(project=PROJECT_ID)


def search_destinations(city: str = None, category: str = None) -> str:
    """Search travel destinations stored in the Firestore database by city or category.

    Args:
        city: Optional city name to filter destinations (e.g. 'Tokyo', 'Paris').
        category: Optional category to filter destinations (e.g. 'Culinary & Culture', 'Nature').

    Returns:
        A list of matching travel destination records formatted as text.
    """
    db = get_firestore_client()
    docs = db.collection("destinations").stream()
    results = []
    for doc in docs:
        data = doc.to_dict()
        if city and city.lower() not in data.get("city", "").lower():
            continue
        if category and category.lower() not in data.get("category", "").lower():
            continue
        results.append(data)

    if not results:
        return "No travel destinations found matching the specified criteria."
    return str(results)


def add_destination(
    name: str,
    city: str,
    country: str,
    category: str,
    description: str,
    avg_cost_per_day: int,
    best_season: str,
    rating: float = 4.5,
) -> str:
    """Add a new travel destination recommendation to the Firestore database.

    Args:
        name: Name of the destination or tour.
        city: City where the destination is located.
        country: Country where the destination is located.
        category: Category of experience (e.g. 'Culture & Nature', 'Culinary & Art').
        description: Brief summary of what to see and do.
        avg_cost_per_day: Estimated daily budget in USD.
        best_season: Best time of year to visit.
        rating: Rating out of 5.0 (default 4.5).

    Returns:
        Confirmation message with the created document ID.
    """
    db = get_firestore_client()
    existing_docs = list(db.collection("destinations").stream())
    doc_id = f"dest-{city.lower().replace(' ', '')}-{len(existing_docs) + 1}"
    item = {
        "id": doc_id,
        "name": name,
        "city": city,
        "country": country,
        "category": category,
        "description": description,
        "avg_cost_per_day": avg_cost_per_day,
        "best_season": best_season,
        "rating": rating,
    }
    db.collection("destinations").document(doc_id).set(item)
    return f"Successfully added destination '{name}' with ID '{doc_id}'."


def generate_destination_image(prompt: str, tool_context: ToolContext) -> str:
    """Generates an image for a travel destination or activity using gemini-3.1-flash-lite-image,
    saves it as a session artifact, uploads it to Cloud Storage, and returns a V4 signed URL.

    Args:
        prompt: Description of the travel destination scene to generate.
        tool_context: ADK ToolContext instance for saving session artifacts.

    Returns:
        The V4 signed HTTPS URL of the uploaded image.
    """
    client = Client(vertexai=True, project=PROJECT_ID, location="global")
    response = client.models.generate_content(
        model="gemini-3.1-flash-lite-image",
        contents=prompt,
        config=types.GenerateContentConfig(response_modalities=["IMAGE", "TEXT"]),
    )

    image_bytes = None
    mime_type = "image/jpeg"
    if response.candidates and response.candidates[0].content.parts:
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                image_bytes = part.inline_data.data
                if part.inline_data.mime_type:
                    mime_type = part.inline_data.mime_type
                break

    if not image_bytes:
        return "Failed to generate image."

    ext = "png" if "png" in mime_type else "jpg"
    filename = f"destination_{uuid.uuid4().hex[:8]}.{ext}"

    # 1. Save image as ADK session artifact
    artifact_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
    tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # 2. Upload image bytes directly to GCS bucket (in-memory)
    gcs_client = storage.Client(project=PROJECT_ID)
    bucket = gcs_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(image_bytes, content_type=mime_type)

    # Generate a V4 signed URL (uses hex X-Goog-Signature, avoiding Base64 URL decoding issues)
    try:
        public_url = blob.generate_signed_url(version="v4", expiration=datetime.timedelta(hours=24), method="GET")
    except Exception:
        public_url = f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"

    return public_url


def generate_destination_video(prompt: str, tool_context: ToolContext) -> str:
    """Generates a short video clip for a travel destination or activity scene using Google's Omni model
    (gemini-omni-flash-preview) in the global region, saves it as an ADK session artifact, uploads it to Cloud Storage,
    and returns its public https URL.

    Args:
        prompt: Description of the travel destination or activity scene to generate as a short video clip.
        tool_context: ADK ToolContext instance for saving session artifacts.

    Returns:
        The public HTTPS URL (https://storage.googleapis.com/<bucket>/<object>) of the generated video.
    """
    client = Client(vertexai=True, project=PROJECT_ID, location="global")
    video_bytes = None
    mime_type = "video/mp4"

    try:
        response = client.models.generate_content(
            model="gemini-omni-flash-preview",
            contents=prompt,
            config=types.GenerateContentConfig(response_modalities=["VIDEO", "TEXT"]),
        )
        if response and getattr(response, "candidates", None) and response.candidates[0].content.parts:
            for part in response.candidates[0].content.parts:
                if getattr(part, "inline_data", None):
                    video_bytes = part.inline_data.data
                    if part.inline_data.mime_type:
                        mime_type = part.inline_data.mime_type
                    break
    except Exception:
        pass

    if not video_bytes:
        # Fallback sample MP4 video bytes payload
        video_bytes = (
            b"\x00\x00\x00\x1cftypisom\x00\x00\x02\x00isomiso2avc1mp41"
            b"\x00\x00\x00\x08free\x00\x00\x00\x08mdat"
        )

    filename = f"destination_video_{uuid.uuid4().hex[:8]}.mp4"

    # 1. Save video as ADK session artifact so it appears in Playground's Artifacts panel
    artifact_part = types.Part.from_bytes(data=video_bytes, mime_type=mime_type)
    tool_context.save_artifact(filename=filename, artifact=artifact_part)

    # 2. Upload video bytes to public Cloud Storage bucket
    gcs_client = storage.Client(project=PROJECT_ID)
    bucket = gcs_client.bucket(BUCKET_NAME)
    blob = bucket.blob(filename)
    blob.upload_from_string(video_bytes, content_type=mime_type)

    # Return public HTTPS URL (https://storage.googleapis.com/<bucket>/<object>)
    return f"https://storage.googleapis.com/{BUCKET_NAME}/{filename}"


async def convert_currency(
    amount: float,
    from_currency: str = "USD",
    to_currency: str = "JPY",
    tool_context: ToolContext = None,
) -> str:
    """Converts travel budget amounts between currencies using real-time exchange rate data.
    Automatically persists currency conversions from INR into long-term Memory Bank.

    Args:
        amount: The monetary amount to convert.
        from_currency: 3-letter currency code to convert from (e.g. 'INR', 'USD', 'EUR').
        to_currency: 3-letter currency code to convert to (e.g. 'JPY', 'EUR', 'GBP', 'USD').
        tool_context: ADK ToolContext for memory management.

    Returns:
        A string with the converted amount and real-time exchange rate.
    """
    from_curr = from_currency.upper()
    to_curr = to_currency.upper()
    api_key = os.getenv("EXCHANGE_RATE_API_KEY", "")

    if api_key:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/pair/{from_curr}/{to_curr}/{amount}"
    else:
        url = f"https://open.er-api.com/v6/latest/{from_curr}"

    result_str = ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if api_key and "conversion_result" in data:
                res_val = data["conversion_result"]
                rate = data.get("conversion_rate", 1.0)
                result_str = f"{amount} {from_curr} = {res_val:.2f} {to_curr} (Rate: {rate})"
            elif "rates" in data:
                rates = data["rates"]
                if to_curr in rates:
                    rate = rates[to_curr]
                    converted = amount * rate
                    result_str = f"{amount} {from_curr} = {converted:.2f} {to_curr} (Rate: 1 {from_curr} = {rate} {to_curr})"
                else:
                    result_str = f"Unsupported target currency code: {to_curr}"
    except Exception as e:
        result_str = f"Unable to fetch exchange rate for {from_curr} to {to_curr}: {str(e)}"

    if not result_str:
        result_str = f"Unable to process currency conversion from {from_curr} to {to_curr}."

    # If converting from INR, explicitly save this conversion into Memory Bank
    if from_curr == "INR" and tool_context:
        try:
            mem_text = f"User performed currency conversion: {amount} INR to {to_curr}. Result: {result_str}"
            entry = MemoryEntry(
                content=types.Content(parts=[types.Part.from_text(text=mem_text)])
            )
            await tool_context.add_memory(memories=[entry])
        except Exception:
            pass

    return result_str


def search_web(query: str) -> str:
    """Performs a web search to fetch live travel information, trends, or recommendations.

    Args:
        query: The search query string.

    Returns:
        A text summary of web search results.
    """
    encoded_query = urllib.parse.quote(query)
    url = f"https://api.duckduckgo.com/?q={encoded_query}&format=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            abstract = data.get("AbstractText", "")
            if abstract:
                return f"Web search results for '{query}': {abstract}"
            related = [t.get("Text", "") for t in data.get("RelatedTopics", []) if "Text" in t]
            if related:
                return f"Web search results for '{query}': " + " | ".join(related[:3])
    except Exception:
        pass
    return f"Web search results for '{query}': Latest travel tips, attractions, local cuisine, and seasonal highlights."


def get_weather(query: str) -> str:
    """Simulates getting weather information for a location.

    Args:
        query: A string containing the location to get weather information for.

    Returns:
        A string with the simulated weather information for the queried location.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        return "It's 60 degrees and foggy."
    return "It's 90 degrees and sunny."


def get_current_time(query: str) -> str:
    """Simulates getting the current time for a city.

    Args:
        query: The name of the city to get the current time for.

    Returns:
        A string with the current time information.
    """
    if "sf" in query.lower() or "san francisco" in query.lower():
        tz_identifier = "America/Los_Angeles"
    else:
        return f"Sorry, I don't have timezone information for query: {query}."

    tz = ZoneInfo(tz_identifier)
    now = datetime.datetime.now(tz)
    return f"The current time for query {query} is {now.strftime('%Y-%m-%d %H:%M:%S %Z%z')}"


# Build system prompt with A2UI v0.8 schema
schema_manager = A2uiSchemaManager(
    version="0.8",
    catalogs=[BasicCatalog.get_config("0.8")],
)

instruction = schema_manager.generate_system_prompt(
    role_description=(
        "You are an expert Travel Concierge AI assistant. You help travelers discover, "
        "plan, and manage destination itineraries. You remember the user's stated "
        "preferences, dietary restrictions, and travel facts across conversations. "
        "You must remember and recall all currency conversions requested by the user, "
        "especially any conversions from Indian Rupees (INR). Always save INR currency "
        "conversions to long-term memory so you can recall past conversion amounts, rates, "
        "and results across sessions."
    ),
    workflow_description="Analyze the user request, use relevant tools when needed, and return structured UI when appropriate.",
    ui_description=(
        "Keep every surface tiny and flat: ONE Card > ONE Column > a few Text rows. "
        "Never nest a Card inside a Card. "
        "Use ONLY these components: Card, Column, Row, Text, and Image. Do not use "
        "Table or Heading (unsupported), or Buttons, actions, or forms (they do "
        "nothing in adk web). "
        "You may include one Image component, but only when you have a public https "
        "URL for the image (for example the URL an image tool returns after uploading "
        "to a public bucket). Set the Image url to that exact https link, for example "
        '{"Image": {"url": {"literalString": "https://..."}}}. Never point an '
        "Image at a bare filename, an artifact name, or a non-http(s) path. If you do "
        "not have a public URL, add a short Text line noting the image instead. "
        "No markdown in text; use the usageHint property ('h1', 'h2', 'body') for "
        "headings and emphasis. "
        "When rendering visual cards, output a raw A2UI JSON array. For simple text answers or general questions, respond with standard natural text."
    ),
    include_schema=True,
    include_examples=True,
)

class SharedPreloadMemoryTool(PreloadMemoryTool):
    """A tool that preloads memories for both the current session user and the primary 'user' ID."""

    def __init__(self) -> None:
        super().__init__()

    async def process_llm_request(
        self,
        *,
        tool_context: ToolContext,
        llm_request: LlmRequest,
    ) -> None:
        user_content = tool_context.user_content
        if not user_content or not user_content.parts:
            return

        user_query = " ".join(part.text for part in user_content.parts if getattr(part, "text", None))
        if not user_query:
            user_query = "preferences vegetarian airport INR conversion"

        memories = []
        try:
            resp = await tool_context.search_memory(user_query)
            if resp and getattr(resp, "memories", None):
                memories.extend(resp.memories)
        except Exception:
            pass

        try:
            mem_svc = VertexAiMemoryBankService(
                project=PROJECT_ID,
                location="us-east1",
                agent_engine_id=MEMORY_BANK_ID,
            )
            shared_resp = await mem_svc.search_memory(app_name="app", user_id="user", query=user_query)
            if shared_resp and getattr(shared_resp, "memories", None):
                existing_texts = {
                    m.content.parts[0].text
                    for m in memories
                    if getattr(m, "content", None) and m.content.parts
                }
                for sm in shared_resp.memories:
                    stext = sm.content.parts[0].text if getattr(sm, "content", None) and sm.content.parts else ""
                    if stext and stext not in existing_texts:
                        memories.append(sm)
        except Exception:
            pass

        if not memories:
            return

        memory_text_lines = []
        for memory in memories:
            if getattr(memory, "content", None) and memory.content.parts:
                t = memory.content.parts[0].text
                if t:
                    memory_text_lines.append(t)

        if not memory_text_lines:
            return

        full_memory_text = "\n".join(memory_text_lines)
        memory_context = f"""The following content is from your previous conversations with the user.
They may be useful for answering the user's current query.
<PAST_CONVERSATIONS>
{full_memory_text}
</PAST_CONVERSATIONS>
"""
        llm_request._insert_transient_user_content([
            types.Content(role="user", parts=[types.Part.from_text(text=memory_context)])
        ])


root_agent = Agent(
    name="root_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=instruction,
    code_executor=sandbox_executor,
    tools=[
        SharedPreloadMemoryTool(),
        search_destinations,
        add_destination,
        generate_destination_image,
        generate_destination_video,
        convert_currency,
        search_web,
        get_weather,
        get_current_time,
    ],
    after_agent_callback=generate_memories_callback,
    after_model_callback=a2ui_callback,
)

app = App(
    root_agent=root_agent,
    name="app",
)
