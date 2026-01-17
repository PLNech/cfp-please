#!/bin/bash
# Sync Agent Studio config to Algolia
# Usage: ./sync.sh [create|update|delete]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/../.env"

CONFIG_FILE="$SCRIPT_DIR/config.json"
AGENT_NAME="cfp-please"

# Substitute env vars in config
CONFIG=$(cat "$CONFIG_FILE" | \
  sed "s/\${ALGOLIA_APP_ID}/$ALGOLIA_APP_ID/g" | \
  sed "s/\${ALGOLIA_SEARCH_API_KEY}/$ALGOLIA_SEARCH_API_KEY/g")

API_BASE="https://${ALGOLIA_APP_ID}.algolia.net/agent-studio/1"

# Find existing agent by name
find_agent() {
  curl -s "$API_BASE/agents" \
    -H "X-Algolia-Application-Id: $ALGOLIA_APP_ID" \
    -H "X-Algolia-API-Key: $ALGOLIA_API_KEY" | \
    jq -r ".data[] | select(.name == \"$AGENT_NAME\") | .id"
}

create_agent() {
  echo "Creating agent '$AGENT_NAME'..."
  curl -s -X POST "$API_BASE/agents" \
    -H "X-Algolia-Application-Id: $ALGOLIA_APP_ID" \
    -H "X-Algolia-API-Key: $ALGOLIA_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$CONFIG" | jq '.'
}

update_agent() {
  AGENT_ID=$(find_agent)
  if [ -z "$AGENT_ID" ]; then
    echo "Agent '$AGENT_NAME' not found. Creating..."
    create_agent
    return
  fi

  echo "Updating agent '$AGENT_NAME' ($AGENT_ID)..."
  curl -s -X PATCH "$API_BASE/agents/$AGENT_ID" \
    -H "X-Algolia-Application-Id: $ALGOLIA_APP_ID" \
    -H "X-Algolia-API-Key: $ALGOLIA_API_KEY" \
    -H "Content-Type: application/json" \
    -d "$CONFIG" | jq '.'
}

publish_agent() {
  AGENT_ID=$(find_agent)
  if [ -z "$AGENT_ID" ]; then
    echo "Agent '$AGENT_NAME' not found"
    exit 1
  fi

  echo "Publishing agent '$AGENT_NAME' ($AGENT_ID)..."
  curl -s -X POST "$API_BASE/agents/$AGENT_ID/publish" \
    -H "X-Algolia-Application-Id: $ALGOLIA_APP_ID" \
    -H "X-Algolia-API-Key: $ALGOLIA_API_KEY" | jq '.'
}

delete_agent() {
  AGENT_ID=$(find_agent)
  if [ -z "$AGENT_ID" ]; then
    echo "Agent '$AGENT_NAME' not found"
    exit 1
  fi

  echo "Deleting agent '$AGENT_NAME' ($AGENT_ID)..."
  curl -s -X DELETE "$API_BASE/agents/$AGENT_ID" \
    -H "X-Algolia-Application-Id: $ALGOLIA_APP_ID" \
    -H "X-Algolia-API-Key: $ALGOLIA_API_KEY"
  echo "Deleted"
}

show_agent() {
  AGENT_ID=$(find_agent)
  if [ -z "$AGENT_ID" ]; then
    echo "Agent '$AGENT_NAME' not found"
    exit 1
  fi

  curl -s "$API_BASE/agents/$AGENT_ID" \
    -H "X-Algolia-Application-Id: $ALGOLIA_APP_ID" \
    -H "X-Algolia-API-Key: $ALGOLIA_API_KEY" | jq '.'
}

case "${1:-update}" in
  create)  create_agent ;;
  update)  update_agent ;;
  publish) publish_agent ;;
  delete)  delete_agent ;;
  show)    show_agent ;;
  *)
    echo "Usage: $0 [create|update|publish|delete|show]"
    exit 1
    ;;
esac
