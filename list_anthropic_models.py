import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    print("Error: ANTHROPIC_API_KEY not found in .env file.")
    exit()

print("Fetching available Anthropic models...\n")

try:
    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    
    response = requests.get("https://api.anthropic.com/v1/models", headers=headers)
    response.raise_for_status()  # Raise an exception for bad status codes
    
    models_data = response.json()
    
    # Sort models, for example, by name
    sorted_models = sorted(models_data.get('data', []), key=lambda x: x.get('id'))

    print("Available Anthropic Models:")
    for model in sorted_models:
        print(f"- {model.get('id')} (Display Name: {model.get('display_name', 'N/A')})")

except requests.exceptions.RequestException as e:
    print(f"An error occurred while making the request: {e}")
except Exception as e:
    print(f"An error occurred: {e}") 