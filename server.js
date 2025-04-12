require('dotenv').config();
const express = require('express');
const path = require('path');
const { GoogleGenerativeAI } = require('@google/generative-ai');
const sqlite3 = require('sqlite3').verbose();

const app = express();
const port = process.env.PORT || 3000;

const genAI = new GoogleGenerativeAI(process.env.GEMINI_API_KEY);

app.use(express.json());
app.use(express.static(path.join(__dirname, 'templates')));

// Database setup
const db = new sqlite3.Database('reminders.db');
db.run(`CREATE TABLE IF NOT EXISTS reminders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    activity TEXT NOT NULL,
    scheduled_time DATETIME NOT NULL,
    completed BOOLEAN DEFAULT 0
)`);

// Routes
app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'templates', 'index.html'));
});

app.get('/api/suggestions', async (req, res) => {
    try {
        const model = genAI.getGenerativeModel({ model: 'gemini-pro' });
        const result = await model.generateContent({
            contents: [{ parts: [{ text: "Suggest a random self-care activity with a brief explanation why it's beneficial. Keep it concise and friendly." }]}]
        });
        const response = result.response;
        const text = response.text();
        res.json({ suggestion: text });
    } catch (error) {
        console.error('API Error:', error);
        res.status(500).json({ error: 'Failed to get suggestion' });
    }
});

app.get('/api/reminders', (req, res) => {
    db.all('SELECT * FROM reminders ORDER BY scheduled_time DESC', [], (err, rows) => {
        if (err) {
            res.status(500).json({ error: err.message });
            return;
        }
        res.json(rows);
    });
});

app.post('/api/reminders', (req, res) => {
    const { activity, scheduled_time } = req.body;
    db.run('INSERT INTO reminders (activity, scheduled_time) VALUES (?, ?)',
        [activity, scheduled_time],
        function(err) {
            if (err) {
                res.status(500).json({ error: err.message });
                return;
            }
            res.json({ id: this.lastID });
        });
});

app.delete('/api/reminders/:id', (req, res) => {
    db.run('DELETE FROM reminders WHERE id = ?', req.params.id, (err) => {
        if (err) {
            res.status(500).json({ error: err.message });
            return;
        }
        res.json({ message: 'Reminder deleted' });
    });
});

app.post('/api/chat', async (req, res) => {
    try {
        const { message } = req.body;
        const model = genAI.getGenerativeModel({ model: 'gemini-pro' });
        
        // Updated prompt for more specific responses
        const prompt = message.toLowerCase().includes('diet') 
            ? `Provide a detailed 7-day vegetarian diet plan with breakfast, lunch, dinner and snacks. Include calorie counts and nutritional benefits. The request was: ${message}`
            : `As a professional self-care assistant, provide specific advice for: ${message}. Give practical steps rather than asking follow-up questions.`;
            
        const result = await model.generateContent({
            contents: [{ parts: [{ text: prompt }]}]
        });
        const response = result.response;
        const text = response.text();
        res.json({ reply: text });
    } catch (error) {
        console.error('Chat Error:', error);
        res.status(500).json({ error: 'Failed to process chat message' });
    }
});

app.listen(port, () => {
    console.log(`Server running at http://localhost:${port}`);
});