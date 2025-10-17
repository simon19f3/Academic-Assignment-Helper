Academic Plagiarism & Research Assistant API
This project provides a FastAPI-based API for students to upload assignments, trigger plagiarism and research analysis, retrieve results, and search academic sources. It integrates with an n8n workflow for analysis processing and uses PostgreSQL for data persistence.
Features

Student Registration & Authentication: Secure registration and login for students using JWT tokens.
Assignment Upload: Students can upload assignment files (e.g., essays, reports) for analysis.
External Analysis Trigger: Integrates with an n8n webhook to trigger an external analysis workflow (e.g., plagiarism checking, research suggestion generation).
Analysis Result Retrieval: Fetch detailed analysis results for uploaded assignments, including plagiarism scores, flagged sections, research suggestions, and citation recommendations.
Academic Source Search: Search a database of academic sources (articles, papers, etc.) relevant to research topics.
Asynchronous Operations: Leverages asyncio for non-blocking database and HTTP operations.

Technologies Used

FastAPI: High-performance web framework for building APIs.
SQLAlchemy (Async): Asynchronous ORM for interacting with PostgreSQL.
PostgreSQL: Relational database for storing student, assignment, analysis, and academic source data.
python-jose: JWT (JSON Web Token) implementation for authentication.
passlib: Password hashing utilities.
httpx: Asynchronous HTTP client for interacting with the n8n webhook.
aiofiles: Asynchronous file operations for handling uploads.
python-dotenv: For managing environment variables.
n8n (External): Expected to handle the heavy lifting of plagiarism detection and research analysis via webhooks.

Setup and Installation


Clone the repository
textgit clone <your-repository-url>
cd <your-project-directory>


Create and activate a Python virtual environment
textpython -m venv venv

On Windows: .\venv\Scripts\activate
On macOS/Linux: source venv/bin/activate



Install dependencies
textpip install -r requirements.txt


Set up Environment Variables
Create a .env file in the root directory of your project based on .env.example:
textPOSTGRES_URL="postgresql://user:password@host:port/database"
JWT_SECRET_KEY="your_super_secret_jwt_key_here"
N8N_WEBHOOK_URL="http://localhost:5678/webhook-test/<your-n8n-webhook-id>"
Replace placeholders with your actual values:

POSTGRES_URL: Your PostgreSQL connection string. Make sure the database exists. Example: postgresql://fastapi_user:password@localhost:5432/fastapi_db
JWT_SECRET_KEY: A strong, random secret key for signing JWT tokens. You can generate one with openssl rand -hex 32.
N8N_WEBHOOK_URL: The URL of your n8n workflow webhook endpoint that will process the uploaded assignments.



Initialize the Database
The application will automatically create tables on startup if they don't exist. Ensure your POSTGRES_URL points to an accessible PostgreSQL database.


Run the Application
textuvicorn main:app --reload
The API will be available at http://127.0.0.1:8000. You can access the interactive API documentation (Swagger UI) at http://127.0.0.1:8000/docs.


API Endpoints
Authentication


POST /auth/register
Register a new student account.

Form Data: email, password, full_name, student_id
Response: {"msg": "Student registered successfully"} or conflict errors.



POST /auth/login
Log in and obtain an access token.

Form Data: username (email), password
Response: {"access_token": "...", "token_type": "bearer"}



Assignment Management


POST /upload (Requires Authentication)
Upload an assignment file for analysis. This triggers the n8n workflow.

File Upload: file (the assignment document)
Response: {"analysis_id": <int>, "msg": "Analysis triggered. Results will be available shortly."}



GET /analysis/{assignment_id} (Requires Authentication)
Retrieve the analysis results for a specific assignment.

Path Parameter: assignment_id (the ID of the assignment).
Response: Detailed JSON object with suggested_sources, plagiarism_score, flagged_sections, etc.



Research & Sources


GET /sources (Requires Authentication)
Search for academic sources based on a query.

Query Parameter: query (e.g., ?query=artificial intelligence)
Response: List of academic sources matching the query, including id, title, authors, abstract, etc.



N8N Workflow Integration (Conceptual)
The n8n integration is critical for the analysis part. You'll need to set up an n8n workflow that:

Receives a webhook trigger: Configured to listen at the N8N_WEBHOOK_URL defined in your .env.
Processes the uploaded file: The webhook will receive the assignment file and student metadata.
Performs analysis:

Plagiarism Check: Use external tools or custom logic.
Research Suggestions: Generate suggestions based on the assignment's content.
Citation Recommendations: Provide guidance on citations.


Updates the API: After analysis, the n8n workflow should make a PUT or POST request back to your FastAPI application (an endpoint you'd need to add) to update the AnalysisResult for the given analysis_id with the generated data.

Example N8N Webhook Data Structure (from /upload endpoint):

Files: data (the uploaded file)
Body Data:

student_email: The email of the student who uploaded.
student_id: The student ID of the student.
filename: The original filename of the uploaded assignment.