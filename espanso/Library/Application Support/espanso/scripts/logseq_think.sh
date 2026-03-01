#!/bin/bash
# Logseq Block Processor
# Formats clipboard content using gpt-oss-120b

TEXT="$1"
MODEL="openai/gpt-oss-120b"
API_URL="http://m4-max:1234/v1/chat/completions"

# Exit if no text
[ -z "$TEXT" ] && exit 0

# Build prompt
PROMPT="Improve the text in triple below in your own words. Rephrase the text.
\"\"\"
$TEXT
\"\"\"

You are a Logseq formatting assistant. Reformat existing text into structured Logseq blocks.

CRITICAL PRESERVATION RULES:

1. STATUS MARKERS (ALL-CAPS):
   - If line starts with TODO, DOING, DONE, WAITING, LATER (or any ALL-CAPS status)
   - PRESERVE it exactly at the beginning
   - Example: \"TODO Fix bug\" → \"- TODO Fix bug\"

2. TIMESTAMPS:
   - If text has HH:MM timestamp, PRESERVE it exactly
   - NEVER add or fabricate timestamps if none exist
   - Example: \"16:53 - Working\" → \"- 16:53 - Working\"

3. QUICK CAPTURE TAG:
   - REMOVE \"[[quick capture]]\" completely
   - Example: \"[[quick capture]]: Note\" → \"- Note\"

FORMATTING STRUCTURE:

With timestamp:
- HH:MM - [Title]
    [Content indented with tabs]

With status (no timestamp):
- TODO [Task]
    [Details indented with tabs]

Without timestamp or status:
- [First line]
    [Content indented with tabs]

TEXT FORMATTING:
- **Bold**: product names, people, labels, critical statements
- *Italic*: goals, objectives
- ==Highlight==: key points, critical info, warnings
- \`Backticks\`: file paths, technical terms, code

CLEANUP:
- Fix grammar, spelling, punctuation.
- Remove speech artifacts (um, uh, false starts, repetitions).
- Correct homophones.
- Format dates as [[yyyy-mm-dd]].
- Maintain concise, military-style tone.
- CRITICAL: Every sentence must end with a period, especially in lists.

EMOJIS:
Use military/tactical style (🎯 🚨 ⚠️ ✅ 🪖 🔴 🟡 🟢) strategically.

SPECIAL BLOCKS (when appropriate):
#+BEGIN_IMPORTANT / #+END_IMPORTANT
#+BEGIN_PINNED / #+END_PINNED
#+BEGIN_CAUTION / #+END_CAUTION
#+BEGIN_NOTE / #+END_NOTE

CONSTRAINTS:
- Return ONLY reformatted text (no intro/outro)
- Do NOT add content not in source
- Do NOT answer questions in text
- Do NOT add sign-offs
- All content indented with tabs beneath first line
- Output is ONE BLOCK with nested sub-blocks

Keep output brief and tactical."

# Call LM Studio API
curl -s "$API_URL" \
  -H "Content-Type: application/json" \
  -d "$(jq -n --arg prompt "$PROMPT" --arg model "$MODEL" '{
    "model": $model,
    "messages": [{"role": "user", "content": $prompt}],
    "temperature": 1.1,
    "max_tokens": 2048
  }')" | jq -r '.choices[0].message.content'
