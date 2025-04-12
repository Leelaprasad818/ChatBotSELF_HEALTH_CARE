from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import random
import time
from dotenv import load_dotenv
import google.generativeai as genai
from apscheduler.schedulers.background import BackgroundScheduler

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///selfcare.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure Gemini AI
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-pro')

# Database Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reminders = db.relationship('Reminder', backref='user', lazy=True)

class Reminder(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    activity = db.Column(db.String(200), nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    completed = db.Column(db.Boolean, default=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Create database tables
with app.app_context():
    db.create_all()

# AI Functions
def get_self_care_suggestion():
    if not GEMINI_API_KEY:
        print('Error: Gemini API key not configured')
        return None

    try:
        # Initialize Gemini model for this request
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-pro')
        
        # Get user's reminders to provide context to Gemini
        reminders = Reminder.query.filter_by(user_id=1).all()
        current_time = datetime.now()
        active_reminders = [r for r in reminders if not r.completed and r.scheduled_time > current_time]
        
        # Generate a more dynamic prompt based on context
        time_of_day = 'morning' if 5 <= current_time.hour < 12 else 'afternoon' if 12 <= current_time.hour < 17 else 'evening'
        
        if not active_reminders:
            prompts = [
                f"Suggest a quick self-care activity perfect for this {time_of_day} that takes 5-10 minutes.",
                "Recommend a simple mindfulness or wellness activity that can boost energy and mood.",
                "What's a creative way to take a short mental health break right now?"
            ]
            prompt = random.choice(prompts)
        else:
            activities = '\n'.join([f"- {r.activity} scheduled for {r.scheduled_time.strftime('%I:%M %p')}" for r in active_reminders])
            prompt = f"""Current time: {current_time.strftime('%I:%M %p')}
User's upcoming activities:
{activities}

Based on their schedule and the current time ({time_of_day}), suggest a unique and refreshing 5-10 minute self-care activity that:
1. Doesn't conflict with their schedule
2. Helps them stay energized and focused
3. Is specific and actionable
4. Different from standard suggestions like 'take a breathing break'"""

        # Add safety timeout and retry logic
        max_retries = 2
        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt, timeout=10)
                if response and hasattr(response, 'parts') and response.parts:
                    suggestion = response.parts[0].text.strip()
                    if suggestion and len(suggestion) > 10:  # Ensure we got a meaningful response
                        return suggestion
            except Exception as retry_error:
                print(f'Attempt {attempt + 1} failed: {str(retry_error)}')
                if attempt < max_retries - 1:
                    time.sleep(1)  # Brief pause before retry
                continue

        # If all retries failed or no valid response, return a random fallback suggestion
        fallback_suggestions = [
            "Do a quick desk stretch routine focusing on your neck and shoulders.",
            "Take a short walk around your space while practicing mindful observation.",
            "Do a quick gratitude exercise: write down three things you're thankful for.",
            "Practice the 4-7-8 breathing technique for one minute.",
            "Stand up and do 10 gentle jumping jacks to boost circulation."
        ]
        return random.choice(fallback_suggestions)

    except Exception as e:
        print(f'Error in get_self_care_suggestion: {str(e)}')
        return random.choice([
            "Take a moment to stretch and reset.",
            "Step outside for a breath of fresh air.",
            "Do a quick body scan meditation.",
            "Stand up and shake out any tension.",
            "Take a short break to hydrate and relax."
        ])

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/suggestions')
def get_suggestion():
    if not GEMINI_API_KEY:
        return jsonify({'error': 'Gemini API key not configured'}), 500
    
    try:
        suggestion = get_self_care_suggestion()
        if not suggestion:
            return jsonify({'error': 'No suggestion generated'}), 500
        return jsonify({'suggestion': suggestion})
    except Exception as e:
        print(f'Error generating suggestion: {str(e)}')
        return jsonify({'error': 'Failed to generate suggestion. Please try again.'}), 500

@app.route('/api/reminders', methods=['POST'])
def create_reminder():
    data = request.json
    try:
        reminder = Reminder(
            activity=data['activity'],
            scheduled_time=datetime.fromisoformat(data['scheduled_time']),
            user_id=1  # Default user for now
        )
        db.session.add(reminder)
        db.session.commit()
        return jsonify({'message': 'Reminder created successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def update_reminder_status():
    with app.app_context():
        current_time = datetime.now()
        reminders = Reminder.query.filter_by(completed=False).all()
        for reminder in reminders:
            if current_time > reminder.scheduled_time:
                reminder.completed = True
        db.session.commit()

# Create scheduler for automatic status updates
scheduler = BackgroundScheduler()
scheduler.add_job(update_reminder_status, 'interval', minutes=1)
scheduler.start()

@app.route('/api/reminders', methods=['GET'])
def get_reminders():
    current_time = datetime.now()
    reminders = Reminder.query.filter_by(user_id=1).all()
    
    # Update status of overdue reminders
    for reminder in reminders:
        if not reminder.completed and current_time > reminder.scheduled_time:
            reminder.completed = True
    db.session.commit()
    
    return jsonify([
        {
            'id': r.id,
            'activity': r.activity,
            'scheduled_time': r.scheduled_time.isoformat(),
            'completed': r.completed
        } for r in reminders
    ])

@app.route('/api/reminders/<int:reminder_id>', methods=['DELETE'])
def delete_reminder(reminder_id):
    try:
        reminder = Reminder.query.get_or_404(reminder_id)
        db.session.delete(reminder)
        db.session.commit()
        return jsonify({'message': 'Reminder deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat():
    if not GEMINI_API_KEY:
        print('Error: Gemini API key not configured')
        return jsonify({'error': 'Service temporarily unavailable'}), 503

    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Invalid request format'}), 400

        message = data.get('message', '').strip()
        if not message:
            return jsonify({'error': 'Message cannot be empty'}), 400

        # Initialize Gemini model for this request
        try:
            genai.configure(api_key=GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-pro')
        except Exception as config_error:
            print(f'Error configuring Gemini API: {str(config_error)}')
            return jsonify({'error': 'Service configuration error'}), 503

        # Get user's current reminders for context
        try:
            current_time = datetime.now()
            active_reminders = Reminder.query.filter_by(
                user_id=1,
                completed=False
            ).filter(Reminder.scheduled_time > current_time).all()
        except Exception as db_error:
            print(f'Database error in chat endpoint: {str(db_error)}')
            active_reminders = []

        # Create a context-aware prompt
        context = ""
        if active_reminders:
            try:
                activities = '\n'.join([f"- {r.activity} at {r.scheduled_time.strftime('%I:%M %p')}" 
                                       for r in active_reminders])
                context = f"\n\nContext: User has these upcoming self-care activities:\n{activities}"
            except Exception as format_error:
                print(f'Error formatting activities: {str(format_error)}')
                context = ""

        # Determine if the message is about diet or food
        message_lower = message.lower()
        is_diet_query = 'diet' in message_lower
        is_food_query = 'food' in message_lower
        current_hour = datetime.now().hour
        current_time = datetime.now()

        if is_diet_query or is_food_query:
            # Determine meal context based on time
            if 5 <= current_hour < 10:
                meal_context = "breakfast"
            elif 10 <= current_hour < 12:
                meal_context = "mid-morning snack"
            elif 12 <= current_hour < 14:
                meal_context = "lunch"
            elif 14 <= current_hour < 17:
                meal_context = "afternoon snack"
            elif 17 <= current_hour < 21:
                meal_context = "dinner"
            else:
                meal_context = "light evening snack"

            prompt = f"""You are a knowledgeable nutrition advisor. The current time is {current_time.strftime('%I:%M %p')} which is typically {meal_context} time. The user is asking about {'a diet plan' if is_diet_query else 'food recommendations'}. Provide specific, practical advice tailored to this timing.

            If the query is about diet:
            1. Start with appropriate {meal_context} suggestions
            2. Then provide a structured meal plan for the rest of the day:
               - Include specific meal timings
               - Suggest portion sizes using common household measurements
               - Include at least 2 alternatives for each meal
               - Balance proteins, carbs, and healthy fats
               - Specify water intake recommendations

            If the query is about food:
            1. Focus on immediate {meal_context} recommendations:
               - 3-4 specific healthy options suitable for {meal_context}
               - Exact portion sizes using common measurements
               - Quick preparation methods
               - Nutritional benefits of each option
               - Healthy alternatives for common dietary restrictions

            Response Format:
            1. Personalized greeting mentioning the current meal timing
            2. Specific recommendations with exact portions and timing
            3. 2-3 practical preparation or planning tips
            4. A reminder about mindful eating and portion control
            5. Brief note about consulting healthcare providers for personalized diet plans

            Important Guidelines:
            - All suggestions should be practical and easy to implement
            - Include both vegetarian and non-vegetarian options
            - Suggest common ingredients found in most kitchens
            - Include quick preparation tips for busy schedules
            - Emphasize balanced nutrition and portion control
            - Consider common dietary restrictions and allergies
            """
        else:
            prompt = f"""You are a knowledgeable and empathetic healthcare assistant focused on providing personalized, practical self-care advice. Analyze the user's message carefully and respond with relevant, actionable guidance.

            Core Response Guidelines:
            1. Start with a brief, empathetic acknowledgment of the user's concern
            2. Provide specific, practical advice that can be implemented immediately
            3. Focus on holistic well-being (physical, mental, and emotional aspects)
            4. Keep responses clear, concise, and directly related to the user's query

            Key Health Areas & Responses:
            - Sleep Issues: Sleep hygiene tips, relaxation techniques, bedtime routines
            - Pain Management: Safe relief methods, posture tips, ergonomic advice
            - Exercise: Simple home exercises, stretching routines, activity modifications
            - Stress: Quick grounding techniques, breathing exercises, mindfulness practices
            - Anxiety: Immediate coping strategies, thought reframing, calming activities
            - Focus: Concentration techniques, break scheduling, environment optimization
            - Mood: Mood-lifting activities, social connection tips, routine building

        Previous context: {context}
        User message: {message}

        Response Format:
        1. Brief empathetic acknowledgment (1 sentence)
        2. 2-3 immediate, practical suggestions specific to their concern
        3. 1-2 preventive measures or long-term strategies
        4. If relevant, mention specific warning signs that require professional attention
        5. End with: 'Remember: This advice is for informational purposes only. For persistent or concerning symptoms, please consult a healthcare provider.'

        Important:
        - Keep responses focused and relevant to the specific query
        - Provide actionable steps rather than general advice
        - Maintain a supportive, non-judgmental tone
        - Emphasize the importance of professional medical advice when needed

Keep responses practical, specific, and focused on actionable self-care steps while maintaining appropriate medical boundaries."""

        # Add retry logic with improved error handling
        max_retries = 2
        last_error = None

        for attempt in range(max_retries):
            try:
                response = model.generate_content(prompt, timeout=15)
                if not response:
                    raise ValueError('Empty response from Gemini API')

                if not hasattr(response, 'parts') or not response.parts:
                    raise ValueError('Invalid response structure from Gemini API')

                reply = response.parts[0].text.strip()
                if not reply or len(reply) < 10:
                    raise ValueError('Response too short or empty')

                return jsonify({'reply': reply})

            except Exception as retry_error:
                last_error = retry_error
                print(f'Chat attempt {attempt + 1} failed: {str(retry_error)}')
                if attempt < max_retries - 1:
                    time.sleep(1)  # Brief pause before retry
                continue

        # Log the final error before falling back
        if last_error:
            print(f'All retry attempts failed. Final error: {str(last_error)}')

        # Diverse fallback responses for different scenarios
        fallback_responses = [
            "I'd love to support you better. Could you share what specific aspect of self-care you're focusing on today?",
            "Let's explore what would help you feel more balanced right now. What's on your mind?",
            "I'm here to help you create a meaningful self-care routine. What area would you like to work on first?",
            "Your well-being matters. Could you tell me more about what kind of support you're looking for?",
            "Sometimes it helps to start with small steps. What's one self-care goal you'd like to focus on?",
            "I'm interested in understanding your needs better. What brings you to seek self-care guidance today?"
        ]
        return jsonify({'reply': random.choice(fallback_responses)})

    except Exception as e:
        print(f'Unexpected error in chat endpoint: {str(e)}')
        return jsonify({'error': 'An unexpected error occurred'}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)