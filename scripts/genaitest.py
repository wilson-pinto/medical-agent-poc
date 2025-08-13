from google import genai
from google.genai import types
import json

# Initialize Gemini client with your API key
client = genai.Client(api_key="")

# Prompt asking for structured data
prompt = "List 3 famous cities and their most iconic landmarks."

# JSON Schema (dict-based) for the response
response_schema = {
    "type": "ARRAY",
    "items": {
        "type": "OBJECT",
        "properties": {
            "city": {"type": "STRING"},
            "landmark": {"type": "STRING"}
        },
        "required": ["city", "landmark"]
    }
}

# Generate content using the defined schema
response = client.models.generate_content(
    model="gemini-1.5-flash",  # Or "gemini-2.0-flash-001" if you're using the newer one
    contents=prompt,
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_schema=response_schema,
        temperature=0.4,
    )
)

# Access parsed JSON data
parsed = response.parsed

# Pretty print the structured output
print(json.dumps(parsed, indent=2))
