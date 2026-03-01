#!/bin/bash
TEXT="$1"

curl -s http://m4-max:1234/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg text "$TEXT" '{
    "model": "collabllm-writing-llama-3.1-8b-instruct",
    "messages": [{"role": "user", "content": "Give me 10 alternative versions of the text. Ensure that the alternatives are all distinct from one another.\n\nText: \($text)\n\nAlternatives:"}],
    "temperature": 0.8
  }')" | jq -r '.choices[0].message.content'
