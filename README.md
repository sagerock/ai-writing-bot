# RomaLume - AI Chat Application

This is an AI chat application that allows users to interact with various large language models (LLMs) from different providers like OpenAI, Anthropic, Cohere, and Google. It features a persistent chat history, document uploads for context, and a credit-based usage system.

## Live URLs

- **Frontend (Firebase)**: [https://romalume.com](https://romalume.com)
- **Backend (Render)**: [https://ai-writing-bot-backend.onrender.com](https://ai-writing-bot-backend.onrender.com)

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

Once the claim is set, a user with admin privileges will see the "Admin" link in the application header upon their next login and will have access to the admin panel.

## Utility Scripts

This project includes several utility scripts to help with development and maintenance.

### Checking Available LLM Models

To ensure the model lists in the application are up-to-date, you can run the following scripts to fetch the currently available models from each provider:

-   **OpenAI**:
    ```bash
    python3 list_openai_models.py
    ```

-   **Anthropic**:
    ```bash
    python3 list_anthropic_models.py
    ```

Before running these, make sure your API keys are set correctly in your `.env` file.

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
    - Create a `.env` file and populate it with your API keys. You will need:
        *   `OPENAI_API_KEY`
        *   `ANTHROPIC_API_KEY`
        *   `COHERE_API_KEY`
        *   `GOOGLE_API_KEY`
        *   `XAI_API_KEY`
        *   `SERPAPI_API_KEY`
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

## Deployment & Hosting

This application is deployed using a hybrid approach, with the frontend and backend hosted on separate, specialized platforms.

### Frontend (Firebase Hosting)

The React frontend is hosted on **Firebase Hosting**, which provides a global CDN for fast delivery of static content.

- **URL**: `https://romalume.com`
- **Deployment Process**: To deploy changes to the frontend, follow these steps from your local machine:

  1.  **Navigate to the frontend directory**:
      ```bash
      cd frontend
      ```
  2.  **Build the application for production**: This compiles and optimizes the React code into a `dist` folder.
      ```bash
      npm run build
      ```
  3.  **Deploy to Firebase**: This command uploads the contents of the `dist` folder to Firebase Hosting.
      ```bash
      firebase deploy
      ```

### Backend (Render)

The Python FastAPI backend is hosted as a **Web Service on Render**.

- **URL**: `https://ai-writing-bot-backend.onrender.com`
- **Deployment Process**: Render is connected directly to the GitHub repository. **Any `git push` to the `main` branch will automatically trigger a new deployment.**
- **Managing Environment Variables**: All secret keys (e.g., `OPENAI_API_KEY`) and the `firebase_service_account.json` are stored securely in the Render dashboard under the service's **Environment** tab. They are **not** checked into the Git repository. If you need to add or update a key, you must do so in the Render UI, which will trigger a new deployment.

## Pushing Changes to GitHub & Deploying to Render

This project is set up so that any push to the `main` branch on GitHub will automatically trigger a deployment on Render.

### How to Push Changes

1. **Stage and Commit Your Changes**
   ```bash
   git add .
   git commit -m "Describe your changes"
   ```

2. **Set Up GitHub Authentication (First Time Only)**
   - Go to [GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens)
   - Click **Generate new token (classic)**
   - Give it a name, set an expiration, and check the `repo` scope
   - Click **Generate token** and copy it

3. **Push to GitHub**
   ```bash
   git push origin main
   ```
   - When prompted for a username, enter your GitHub username
   - When prompted for a password, paste your Personal Access Token (PAT)

4. **Automatic Deployment**
   - Render will detect the push to `main` and automatically deploy the backend.

**Tip:**  
To avoid entering your PAT every time, you can use a credential manager or switch your remote to SSH. See [GitHub Docs: Caching your GitHub credentials in Git](https://docs.github.com/en/get-started/getting-started-with-git/caching-your-github-credentials-in-git).
