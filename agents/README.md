# TalkFlix Agents

Agent configurations for Algolia Agent Studio. Create these via the dashboard, then update `agentId` in each config.

## Agents

| Agent | Purpose | Status |
|-------|---------|--------|
| **inspire-agent** | Generate talk ideas from watched talks | Pending |
| **match-score-agent** | Calculate CFP-profile fit % | Pending (heuristic fallback in frontend) |
| **hero-selection-agent** | Pick best CFP for homepage hero | Pending (weighted scoring fallback) |

## Setup

1. Go to [Agent Studio Dashboard](https://dashboard.algolia.com/generativeAi/agent-studio/agents)
2. Create each agent using the config in this directory
3. Copy the `agentId` back to the JSON file
4. Update `frontend/src/config.ts` with the new IDs

## Config Format

```json
{
  "name": "Agent name in dashboard",
  "description": "What it does",
  "role": "System prompt - who the agent is",
  "style": "How it should respond",
  "constraints": ["Rules it must follow"],
  "output_format": { "type": "json", "schema": {...} },
  "tools": [{ "type": "algolia_search", "index": "cfps" }],
  "model": "minimax",
  "temperature": 0.3-0.8,
  "agentId": "UUID after creation"
}
```

## Updating Agents

When you need to iterate:
1. Edit the JSON config locally
2. PATCH via API (when available) or update in dashboard
3. Commit the updated config

## Current Agent

The existing agent (`9f27077f-f2bb-465f-a5cd-80cb8928995e`) is used for general chat and inspiration. Once dedicated agents are created, update the frontend hooks to use the appropriate agent for each task.
