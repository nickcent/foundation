#!/bin/bash
TEXT="$1"
MODEL="${2:-collabllm-writing-llama-3.1-8b-instruct}"

curl -s http://m4-max:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg text "$TEXT" --arg model "$MODEL" '{
    "model": $model,
    "messages": [{"role": "user", "content": "Rewrite this in first person:\n\n\($text)"}],
    "temperature": 0.7
  }')" | jq -r '.choices[0].message.content'
