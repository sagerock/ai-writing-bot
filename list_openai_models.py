import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# The OpenAI client uses the OPENAI_API_KEY environment variable by default
client = OpenAI()

print("Fetching available OpenAI models...\n")

try:
    # Fetch the list of all models
    models = client.models.list()

    # Filter for models that are relevant for chat and sort them
    gpt_models = sorted(
        [model for model in models if "gpt" in model.id and "instruct" not in model.id],
        key=lambda x: x.id
    )

    print("Available GPT Models:")
    for model in gpt_models:
        print(f"- {model.id}")

except Exception as e:
    print(f"An error occurred: {e}")
    print("Please ensure your OPENAI_API_KEY is set correctly in your .env file.") 