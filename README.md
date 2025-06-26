# AI Writing Tool & Chatbot

This project is a full-stack web application designed to assist with the creative process of writing. It provides a versatile chat interface to interact with multiple leading Large Language Models (LLMs), manage and discuss documents, and securely save conversation archives, all tied to a robust user authentication system.

The application has been architected with a modern technology stack, featuring a React frontend and a Python (FastAPI) backend, with Google Firebase handling user authentication, database, and storage needs.

## Features

*   **Multi-LLM Support**: Seamlessly switch between different AI models from OpenAI, Anthropic, Cohere, and Google.
*   **Secure User Authentication**: Full email/password registration and login system, including email verification and password reset flows.
*   **Persistent Document Storage**: Upload `.md`, `.txt`, and `.pdf` files directly to a personal, secure cloud storage space powered by Firebase Storage.
*   **Document-Aware Chat**: Uploaded documents are automatically parsed and their content is injected into the chat's context, allowing for immediate discussion and analysis with the AI.
*   **Cloud-Based Chat Archiving**: Save chat conversations to a personal, cloud-based archive on Google Firestore.
*   **Account Management**: Users can update their display name, email, and password through a secure account management panel.
*   **Modern Frontend**: A responsive and interactive UI built with React, Vite, and Firebase.
*   **Asynchronous Backend**: A powerful and scalable backend built with FastAPI.

## Technology Stack

*   **Frontend**: React, Vite
*   **Backend**: Python 3, FastAPI, Uvicorn
*   **Database & Storage**: Google Firestore, Firebase Storage
*   **Authentication**: Firebase Authentication
*   **AI Integrations**: LangChain

## Project Structure

```
.
├── frontend/           # React frontend application
│   ├── src/
│   ├── public/
│   └── package.json
├── .env                # Backend environment variables (see setup)
├── main.py             # FastAPI backend server
├── requirements.txt    # Python dependencies
└── firebase_service_account.json # Firebase Admin credentials (see setup)
```

## Setup and Installation

Follow these steps to get the application running locally.

### 1. Firebase Project Setup

1.  Create a new project in the [Firebase Console](https://console.firebase.google.com/).
2.  **Authentication**: Go to the **Authentication** section, click "Get started," and enable the **Email/Password** sign-in provider.
3.  **Firestore**: Go to the **Firestore Database** section, click "Create database," and start in **test mode** for now.
4.  **Storage**: Go to the **Storage** section and click "Get started."
5.  **Get Service Account Key**:
    *   In your Firebase project, go to **Project settings** (the gear icon).
    *   Go to the **Service accounts** tab.
    *   Click **Generate new private key**.
    *   A JSON file will be downloaded. Rename it to `firebase_service_account.json` and place it in the root of this project directory.

### 2. Backend Setup

1.  **Install Dependencies**: Make sure you have Python 3 and `pip` installed. Create and activate a virtual environment, then install the required packages.
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
    ```
2.  **Configure Environment Variables**:
    *   Create a file named `.env` in the project root.
    *   Add your Firebase Storage bucket name to it. You can find this in the Firebase Console under **Storage**. It will look like `<your-project-id>.appspot.com` or something similar if you created a custom one.
    ```env
    STORAGE_BUCKET="your-storage-bucket-name-here"
    ```

### 3. Frontend Setup

1.  **Navigate to Frontend Directory**:
    ```bash
    cd frontend
    ```
2.  **Install Dependencies**:
    ```bash
    npm install
    ```
3.  **Configure Environment Variables**:
    *   In the `frontend/` directory, create a file named `.env.local`.
    *   Go to your Firebase project settings and find your web app's configuration details.
    *   Add these keys to your `.env.local` file:
    ```env
    VITE_FIREBASE_API_KEY="your_api_key"
    VITE_FIREBASE_AUTH_DOMAIN="your_auth_domain"
    VITE_FIREBASE_PROJECT_ID="your_project_id"
    VITE_FIREBASE_STORAGE_BUCKET="your_storage_bucket"
    VITE_FIREBASE_MESSAGING_SENDER_ID="your_messaging_sender_id"
    VITE_FIREBASE_APP_ID="your_app_id"
    VITE_FIREBASE_MEASUREMENT_ID="your_measurement_id"
    ```

## How to Run

You will need two separate terminal windows to run the backend and frontend servers simultaneously.

**Terminal 1: Start the Backend**

Navigate to the project root and run:
```bash
source venv/bin/activate
python3 -m uvicorn main:main_app --reload
```
The backend will be running at `http://127.0.0.1:8000`.

**Terminal 2: Start the Frontend**

Navigate to the `frontend/` directory and run:
```bash
npm run dev
```
The frontend development server will start, usually at `http://localhost:5173`.

Open your web browser and go to `http://localhost:5173` to use the application.
