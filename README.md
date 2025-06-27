# Multi-Bot Chat Application

This is a multi-bot chat application that allows users to interact with various large language models (LLMs) from different providers like OpenAI, Anthropic, Cohere, and Google. It features a persistent chat history, document uploads for context, and a credit-based usage system.

## Key Features

- **Multi-Bot Support**: Switch between different LLMs from various providers on the fly.
- **Real-time Web Search**: Augment the LLM's knowledge with real-time web search results from SerpApi.
- **Persistent Chat History**: Conversations are automatically saved and loaded.
- **Document Upload**: Upload `.md`, `.txt`, and `.pdf` files to provide context to the LLM.
- **Chat Archives**: Save important conversations as archives, organized by project.
- **Credit System**: Users have a credit balance that decrements with each interaction.
- **Admin Panel**: A management interface for administrators to manage users and system resources.
- **Secure Authentication**: Built on Firebase for secure user authentication and management.

## Admin Panel

The application includes an admin panel for user management, accessible only to users with administrative privileges.

### Admin Features

- **List Users**: View a list of all registered users, their credit balance, and their current role.
- **Update Credits**: Manually add or remove credits from any user's account.
- **Manage Admin Roles**: Grant or revoke admin privileges for any user.

### How to Grant Admin Privileges

Admin access is controlled via Firebase custom claims. To make a user an admin, you must set an `admin: true` custom claim on their Firebase user account.

A utility script, `set_admin.py`, is provided to simplify this process:

1.  **Find the User UID**: Get the UID of the target user from the Firebase Console.
2.  **Edit the Script**: Open `set_admin.py` and replace the placeholder UID with the target user's UID.
3.  **Run the Script**: Execute the script from your terminal:
    ```bash
    python3 set_admin.py
    ```

Once the claim is set, the user will see the "Admin" link in the application header upon their next login and will have access to the admin panel.

## Technology Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React (with Vite)
- **Database**: Firestore (for chat history, archives, and user data)
- **Authentication**: Firebase Authentication
- **Storage**: Firebase Cloud Storage (for document uploads)
- **Web Search**: SerpApi

## Setup and Installation

1.  **Clone the repository**:
    ```bash
    git clone <repository-url>
    cd <repository-directory>
    ```

2.  **Backend Setup**:
    - Navigate to the project root.
    - Create a Python virtual environment: `python3 -m venv venv`
    - Activate it: `source venv/bin/activate`
    - Install dependencies: `pip install -r requirements.txt`
    - Create a `.env` file and populate it with your API keys (see `.env.example`).
    - Place your `firebase_service_account.json` in the root directory.

3.  **Frontend Setup**:
    - Navigate to the `frontend` directory: `cd frontend`
    - Install dependencies: `npm install`
    - Create a `.env` file and add your Firebase client configuration (see `frontend/.env.example`).

4.  **Running the Application**:
    - **Start the backend server** (from the root directory):
      ```bash
      python3 -m uvicorn main:main_app --reload
      ```
    - **Start the frontend development server** (from the `frontend` directory):
      ```bash
      npm run dev
      ```

The application will be available at `http://localhost:5173`.
