# Travel Concierge AI Agent

An intelligent, multi-tool AI Travel Concierge built with the **Agent Development Kit (ADK)** and deployed on **Google Cloud Vertex AI Reasoning Engines**. It offers personalized destination discovery, real-time currency conversion, weather updates, live web search, AI media generation (images & videos), and cross-session memory.

![Travel Concierge Demo](./demo.gif)

---

## 🌟 Key Capabilities & Features

Based on the implemented tool architecture in `app/agent.py`:

- **Personalized Travel Discovery (`search_destinations`)**: Searches Firestore destination collections by city or category, automatically filtered according to stored user dietary preferences (e.g. Vegetarian) and home airport (e.g. DEL).
- **Memory Bank Integration (`SharedPreloadMemoryTool` & `VertexAiMemoryBankService`)**: Automatically persists user preferences, home airports, and conversion histories across chat sessions.
- **Real-Time Currency Conversion (`convert_currency`)**: Converts budget amounts between world currencies using live exchange rates and automatically writes conversion facts to long-term memory.
- **AI Destination Image Generation (`generate_destination_image`)**: Generates visual travel scenes using `gemini-3.1-flash-lite-image`, saves session artifacts, and uploads to Cloud Storage.
- **AI Short Video Generation (`generate_destination_video`)**: Generates short destination video clips using Google's Omni model (`gemini-omni-flash-preview`) in the `global` region.
- **Live Web Search & Weather (`search_web` & `get_weather`)**: Searches up-to-date travel trends and fetches current weather forecasts for destinations.
- **Rich A2UI Component Rendering (`a2ui_callback`)**: Automatically transforms structured agent outputs into dynamic UI components (cards, headers, images, columns, and rows).

---

## ☁️ Google Cloud Services & Architecture

- **Vertex AI Memory Bank**: Manages long-term, cross-session user facts and preferences.
- **Google Cloud Firestore**: Stores travel destination database documents and metadata.
- **Google Cloud Storage (GCS)**: Public media storage bucket for AI-generated images and video clips.
- **Vertex AI Reasoning Engine**: Cloud runtime hosting the ADK agent engine.
- **Vertex AI GenAI Models**:
  - `gemini-2.5-flash`: Core ReAct agent reasoning and orchestration.
  - `gemini-3.1-flash-lite-image`: Destination image generation.
  - `gemini-omni-flash-preview`: Destination short video clip generation.

---

## 🚀 Setup & Local Execution

### 1. Install Dependencies

```bash
uv sync
# OR
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create or set environment variables in your terminal:

```bash
export GOOGLE_CLOUD_PROJECT="<your-gcp-project-id>"
export AGENT_ENGINE_RESOURCE_NAME="projects/<project-number>/locations/<region>/reasoningEngines/<engine-id>"
export AGENT_DIRECTORY="app"
```

### 3. Run Agent Locally

Start the interactive local agent playground:

```bash
agents-cli playground
```

### 4. Run Frontend Proxy Locally

To run the custom FastAPI frontend proxy locally:

```bash
cd frontend
pip install -r requirements.txt
python main.py
```

---

## 📦 Deployment

### Deploy Agent Engine

Deploy or update the agent logic on Vertex AI Reasoning Engine:

```bash
agents-cli deploy
```

### Deploy Frontend to Cloud Run

Deploy the lightweight FastAPI proxy and UI to Google Cloud Run:

```bash
gcloud run deploy travel-concierge-frontend \
  --source=frontend \
  --region=us-east1 \
  --set-env-vars="AGENT_ENGINE_RESOURCE_NAME=<your-resource-name>,AGENT_DIRECTORY=app" \
  --allow-unauthenticated
```
