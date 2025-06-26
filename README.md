# Multi-LLM Book Writing Chatbot

This project is a web-based chatbot designed to assist with the creative process of writing a book. It provides a versatile interface to interact with multiple leading Large Language Models (LLMs), get diverse writing advice, review existing content by uploading Markdown files, and archive conversations for future reference.

## Features

*   **Multi-LLM Support**: Seamlessly switch between different AI models from various providers to get a wide range of creative feedback. Supported providers include:
    *   OpenAI (ChatGPT 4o, GPT-4.1, o3, etc.)
    *   Anthropic (Claude 4, Claude 3.5 Sonnet, etc.)
    *   Cohere (Command R+)
    *   Google (Gemini 2.5 Pro)
*   **Markdown File Upload**: Upload your book chapters or notes as Markdown (`.md`) files. The chatbot will use the content as context for the conversation, preserving structural elements like headings and lists.
*   **Chat Archiving**: Save your entire conversation history, including system messages and uploaded file content, to a timestamped Markdown file in the `archives` directory.
*   **Streaming Responses**: AI responses are streamed token-by-token for a real-time chat experience.
*   **Simple Web Interface**: A clean and straightforward UI built with HTML and JavaScript.

## Project Structure

```
.
├── archives/           # Saved chat conversations are stored here
├── static/
│   ├── index.html      # Main HTML file for the UI
│   └── script.js       # Frontend JavaScript for interactivity
├── .env                # API keys and environment variables
├── main.py             # FastAPI backend server
├── requirements.txt    # Python dependencies
└── README.md           # This file
```

## Setup and Installation

Follow these steps to get the chatbot running locally.

### 1. Clone the Repository

If you haven't already, clone this project to your local machine.

### 2. Install Dependencies

Make sure you have Python 3 installed. Then, install the required Python packages using pip:

```bash
pip install -r requirements.txt
```

### 3. Configure API Keys

The chatbot requires API keys from the LLM providers you wish to use.

1.  There is a `.env` file in the root directory.
2.  Open the `.env` file and add your API keys for OpenAI, Anthropic, Cohere, and Google.

```env
OPENAI_API_KEY="your_openai_api_key_here"
ANTHROPIC_API_KEY="your_anthropic_api_key_here"
COHERE_API_KEY="your_cohere_api_key_here"
GOOGLE_API_KEY="your_google_api_key_here"
```

## How to Run

Once the setup is complete, you can start the web server.

1.  Open your terminal and navigate to the project's root directory.
2.  Run the following command to start the FastAPI server:

```bash
python3 -m uvicorn main:main_app --reload
```

3.  Open your web browser and go to `http://127.0.0.1:8000`.

You can now start chatting with your chosen AI model, upload files, and save your conversations.
