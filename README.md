# Architecture Council

Three AI architects debate your feature request and deliver a synthesized architectural decision.

A Solution Architect frames the challenge, two Senior Architects (Backend and Systems) propose independent solutions and cross-critique each other, then the Solution Architect makes a final decision with a formal ADR.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
# Clone the repository
git clone <repo-url>
cd architecture-council

# Copy env file and fill in your API keys
cp .env_example .env

# Install dependencies
uv sync
```

## Configuration

The app uses [LiteLLM](https://docs.litellm.ai/) to route to different model providers. You have three authentication options — pick one and configure it in `.env`:

### Option 1: Direct API Keys (simplest)

| Variable | Description |
|---|---|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `GEMINI_API_KEY` | Google Gemini API key |

### Option 2: Google Cloud Vertex AI (OAuth / service account)

Use Claude through GCP instead of a raw Anthropic API key.

| Variable | Description |
|---|---|
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCP service account JSON |
| `VERTEXAI_PROJECT` | Your GCP project ID |
| `VERTEXAI_LOCATION` | GCP region (e.g. `us-east5`) |
| `SA_MODEL` | Set to `vertex_ai/claude-opus-4-6` |
| `ARCH_A_MODEL` | Set to `vertex_ai/claude-sonnet-4-6` |

### Option 3: AWS Bedrock (IAM credentials)

Use Claude through AWS instead of a raw Anthropic API key.

| Variable | Description |
|---|---|
| `AWS_ACCESS_KEY_ID` | AWS access key |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key |
| `AWS_REGION_NAME` | AWS region (e.g. `us-east-1`) |
| `SA_MODEL` | Set to `bedrock/anthropic.claude-opus-4-6` |
| `ARCH_A_MODEL` | Set to `bedrock/anthropic.claude-sonnet-4-6` |

### Model Overrides

Regardless of auth method, you can override which model each agent uses:

| Variable | Default |
|---|---|
| `SA_MODEL` | `anthropic/claude-opus-4-6` |
| `ARCH_A_MODEL` | `anthropic/claude-sonnet-4-6` |
| `ARCH_B_MODEL` | `gemini/gemini-3.1-pro-preview` |

## Running

```bash
uv run app.py
```

The Gradio UI will be available at `http://localhost:8770`.

## How It Works

1. Enter a feature request, select a tech stack, and set a complexity level (1-5)
2. The Solution Architect formulates the challenge
3. Two Senior Architects independently propose solutions
4. Each architect cross-critiques the other's proposal
5. The Solution Architect synthesizes a final decision

Session results are saved to `output/sessions/` and can be viewed in the History tab.
