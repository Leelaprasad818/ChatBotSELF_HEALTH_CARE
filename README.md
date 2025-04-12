# AI-Powered Self-Care Reminder

A Flask-based web application that helps users maintain their well-being through AI-powered self-care reminders and suggestions using Google's Gemini AI.

## Features

- AI-generated self-care activity suggestions
- Create and manage personal reminders
- Track completion status of activities
- Clean, responsive user interface

## Setup

1. Clone the repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file in the project root and add your Gemini API key:
   ```
   GEMINI_API_KEY=your_api_key_here
   ```
4. Run the application:
   ```bash
   python app.py
   ```

## Technology Stack

- Backend: Flask
- Database: SQLite with SQLAlchemy
- Frontend: HTML, JavaScript, Tailwind CSS
- AI: Google Gemini API

## Project Structure

```
.
├── app.py              # Main application file
├── requirements.txt    # Python dependencies
├── templates/         # Frontend templates
│   └── index.html    # Main page template
└── .env              # Environment variables (create this file)
```

## Usage

1. Access the application at `http://localhost:5000`
2. Click "Get Suggestion" to receive AI-powered self-care recommendations
3. Add reminders with specific activities and times
4. Track your self-care journey through the reminders list

## Note

Make sure to keep your Gemini API key secure and never commit it to version control.