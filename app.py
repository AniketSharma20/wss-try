from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_cors import CORS
import sqlite3
import hashlib
import secrets
import json
import os
from datetime import datetime
import requests
import threading
import time

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
CORS(app)

# Database setup
def init_db():
    conn = sqlite3.connect('security_system.db')
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            pattern_hash TEXT,
            phone_number TEXT,
            emergency_contact TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Add pattern_hash column if it doesn't exist
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN pattern_hash TEXT')
    except sqlite3.OperationalError:
        # Column already exists
        pass
    
    # Location tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS location_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            latitude REAL,
            longitude REAL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Complaints table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS complaints (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Safe shelters table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS safe_shelters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            phone TEXT,
            capacity INTEGER,
            facilities TEXT,
            rating REAL DEFAULT 0
        )
    ''')
    
    # Emergency tips table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emergency_tips (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Insert sample data
    cursor.execute('''
        INSERT OR IGNORE INTO safe_shelters (name, address, latitude, longitude, phone, capacity, facilities, rating)
        VALUES 
        ('Women Safety Center - Central', '123 Safety Street, City Center', 28.6139, 77.2090, '+91-11-2341-5678', 50, 'Security, Medical, Counseling', 4.5),
        ('Safe Haven Shelter', '456 Protection Avenue, District 2', 28.7041, 77.1025, '+91-11-3456-7890', 30, '24/7 Security, Legal Aid', 4.2),
        ('Women Protection Home', '789 Care Road, Zone 3', 28.5355, 77.3910, '+91-11-4567-8901', 40, 'Counseling, Job Training', 4.7)
    ''')
    
    cursor.execute('''
        INSERT OR IGNORE INTO emergency_tips (title, content, category)
        VALUES 
        ('Stay Alert in Public', 'Always be aware of your surroundings. Avoid isolated areas especially at night.', 'general'),
        ('Trust Your Instincts', 'If something feels wrong, trust your gut feeling and remove yourself from the situation.', 'safety'),
        ('Use Well-lit Routes', 'Always choose well-lit, busy routes when traveling alone.', 'travel'),
        ('Share Your Location', 'Always share your live location with trusted contacts when going out.', 'technology'),
        ('Emergency Numbers', 'Keep emergency numbers saved and easily accessible on your phone.', 'contact')
    ''')
    
    conn.commit()
    conn.close()

# Authentication functions
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password, password_hash):
    return hash_password(password) == password_hash

def hash_pattern(pattern):
    """Hash a pattern for secure storage"""
    pattern_string = ','.join(map(str, pattern))
    return hashlib.sha256(pattern_string.encode()).hexdigest()

def verify_pattern(pattern, pattern_hash):
    """Verify a pattern against its hash"""
    return hash_pattern(pattern) == pattern_hash

# Enhanced AI Assistant
class AIAssistant:
    def __init__(self):
        try:
            import speech_recognition as sr
            import pyttsx3
            self.recognizer = sr.Recognizer()
            self.tts_engine = pyttsx3.init()
            self.available = True
        except ImportError:
            self.available = False
            print("AI Assistant packages not available. Text-based assistant will be used.")
        
        # Comprehensive knowledge base for safety questions
        self.knowledge_base = {
            # Emergency questions
            'emergency': {
                'keywords': ['emergency', 'help', 'danger', 'panic', 'urgent', 'crisis', 'immediate'],
                'response': "🚨 EMERGENCY PROTOCOL ACTIVATED!\n\nI'm triggering all emergency features:\n• Loud siren alarm to attract attention\n• Sharing your live location with emergency contacts\n• Notifying authorities\n• Initiating fake call for your safety\n\nStay calm. Help is on the way. Your location is being shared now."
            },
            'siren': {
                'keywords': ['siren', 'alarm', 'loud', 'noise', 'alert'],
                'response': "🔊 Activating emergency siren...\n\nThe loud alarm will:\n• Attract attention from nearby people\n• Potentially deter attackers\n• Alert those around you that you need help\n\nYou can stop the siren anytime by pressing the Stop button. Use this feature when you feel unsafe or threatened."
            },
            'fake_call': {
                'keywords': ['fake call', 'fake', 'call', 'pretend call', 'simulation'],
                'response': "📞 Fake call feature activated!\n\nIn 10 seconds, you will receive a fake incoming call from Emergency Contact.\n\nThis helps you:\n• Excuse yourself from uncomfortable situations\n• Create a reason to leave\n• Feel safer in potentially dangerous scenarios\n\nYou can answer or decline the call. The call will auto-decline after 15 seconds."
            },
            'location': {
                'keywords': ['location', 'share location', 'track location', 'gps', 'where am i', 'current location'],
                'response': "📍 Location tracking activated!\n\nYour live location is being:\n• Shared with your emergency contacts\n• Stored securely for safety records\n• Updated at your chosen interval\n\nYou can start/stop tracking anytime. The map shows your current position with accuracy indicator."
            },
            'safe_shelters': {
                'keywords': ['safe shelter', 'safe place', 'shelter', 'safe house', 'refuge', 'women shelter', 'nearby shelter'],
                'response': "🏠 Finding safe shelters...\n\nI've found several safe shelters near you:\n• Women Safety Center - Central (5km away)\n• Safe Haven Shelter (8km away)\n• Women Protection Home (12km away)\n\nEach shelter offers:\n• 24/7 security\n• Medical facilities\n• Counseling services\n• Legal aid\n\nTap 'Find Nearby' to see them on the map and get directions."
            },
            'complaints': {
                'keywords': ['complaint', 'report', 'harassment', 'crime', 'incident', 'file complaint', 'submit complaint'],
                'response': "📋 Complaint Filing System\n\nYou can report:\n• Harassment (verbal, physical, digital)\n• Safety concerns in your area\n• Suspicious activities\n• Emergencies\n• Other incidents\n\nTo file a complaint:\n1. Go to Complaints section\n2. Fill in the title and description\n3. Select category\n4. Add location and time (if known)\n5. Attach evidence (photos/videos)\n6. Submit\n\nYour complaint is confidential and will be processed by authorities."
            },
            'emergency_numbers': {
                'keywords': ['emergency numbers', 'helpline', 'hotline', 'contact numbers', 'police', 'ambulance', 'fire'],
                'response': "📞 Emergency Contact Numbers:\n\n🚔 Police: 100 (24/7)\n🚑 Ambulance: 108\n🚒 Fire Brigade: 101\n👩 Women Helpline: 1091\n\nChild Helpline: 1098\nWomen's Helpline (All India): 181\n\nAll these numbers are free to call from any mobile. Save them in your contacts for quick access."
            },
            'safety_tips': {
                'keywords': ['safety tips', 'safety advice', 'stay safe', 'protection tips', 'self safety', 'prevent'],
                'response': "🛡️ Personal Safety Tips:\n\n📍 General Safety:\n• Stay alert of your surroundings always\n• Trust your instincts - if something feels wrong, leave\n• Keep your phone charged and accessible\n• Share your location with trusted contacts when going out\n\n🚶 Travel Safety:\n• Use well-lit, busy routes\n• Avoid walking alone at night when possible\n• Use reputable transport services\n• Keep someone informed of your travel plans\n\n🏠 Home Safety:\n• Install security locks and cameras\n• Don't open doors to strangers\n• Have emergency numbers saved\n\n📱 Digital Safety:\n• Use strong, unique passwords\n• Enable two-factor authentication\n• Be careful with personal information online"
            },
            'features': {
                'keywords': ['features', 'what can you do', 'capabilities', 'functions', 'help me'],
                'response': "🤖 I can help you with:\n\n🚨 Emergency Features:\n• Emergency alert (activates all safety features)\n• Siren alarm\n• Fake call simulation\n• Emergency location sharing\n\n📍 Location Tracking:\n• Live location tracking\n• Location history\n• Share location with contacts\n\n🏠 Safety Resources:\n• Find nearby safe shelters\n• Safety tips and advice\n• Emergency contact numbers\n\n📋 Reporting:\n• File complaints\n• Report incidents\n• Track complaint status\n\n💬 General Questions:\n• Answer safety-related questions\n• Provide guidance in emergencies\n• Offer safety advice and tips\n\nJust ask me anything related to your safety!"
            },
            'profile': {
                'keywords': ['profile', 'account', 'settings', 'my account', 'user profile', 'edit profile'],
                'response': "👤 Profile & Settings\n\nTo access profile features:\n• Click your avatar in the top-right corner\n• View your account information\n• Update emergency contacts\n• Adjust notification preferences\n• Customize location tracking settings\n\nYour profile includes:\n• Username and email\n• Phone number\n• Emergency contact information\n• Security settings\n\nYou can also logout from the header menu."
            },
            'notifications': {
                'keywords': ['notifications', 'alerts', 'messages', 'updates', 'notification settings'],
                'response': "🔔 Notifications System\n\nI keep you informed about:\n• Emergency alerts\n• Location updates\n• Complaint status changes\n• Safety tips\n• System notifications\n\nNotification types:\n• Unread notifications\n• Important alerts\n• Emergency broadcasts\n\nYou can:\n• Mark all as read\n• Filter by type\n• Clear all notifications\n• Adjust notification settings\n\nClick the bell icon to view your notifications."
            },
            'about': {
                'keywords': ['about', 'what is this', 'safeguard', 'women security', 'app purpose'],
                'response': "🛡️ About SafeGuard - Women Security System\n\nSafeGuard is a comprehensive women's safety application designed to empower women with tools and resources for personal security.\n\nFeatures include:\n• AI-powered safety assistant\n• Emergency alert system\n• Live location tracking\n• Safe shelter finder\n• Complaint filing system\n• Safety tips and resources\n\nOur mission: To create a safer environment for women through technology and community support.\n\nEmergency Helpline: 1091"
            },
            'how_to_use': {
                'keywords': ['how to use', 'how does this work', 'getting started', 'tutorial', 'guide'],
                'response': "📖 How to Use SafeGuard:\n\n1️⃣ Getting Started:\n• Create an account or login\n• Set up emergency contacts\n• Enable location services\n\n2️⃣ During Normal Use:\n• Keep the app running in background\n• Use quick commands with the AI assistant\n• Check safety tips regularly\n\n3️⃣ In Emergency:\n• Press the floating Emergency button OR\n• Say Emergency to the AI assistant\n• All safety features will activate\n\n4️⃣ Daily Safety:\n• Start location tracking when going out\n• Use fake call feature when feeling unsafe\n• Report any incidents via complaints\n\nNeed help with something specific? Just ask me!"
            },
            'self_defense': {
                'keywords': ['self defense', 'defense', 'protect yourself', 'fighting', 'defensive'],
                'response': "🥊 Self-Defense Tips:\n\nRemember: Your safety is the priority. Avoid confrontation when possible.\n\nBasic Techniques:\n• Palm strike to attacker's nose or chin\n• Knee kick to groin\n• Elbow strike to face or ribs\n• Finger poke to eyes\n\nUse Everyday Items as Weapons:\n• Keys between fingers\n• Umbrella\n• Hair spray or pepper spray\n• Heavy bag or purse\n\nEscape Techniques:\n• Run to well-lit, populated areas\n• Make noise to attract attention\n• Drop to the ground if grabbed\n• Scream \"Fire\" or \"Not my father\"\n\nConsider taking professional self-defense classes for better preparedness."
            },
            'travel_safety': {
                'keywords': ['travel safety', 'travel', 'journey', 'transport', 'bus', 'train', 'taxi'],
                'response': "🧳 Travel Safety Guidelines:\n\n🚗 General Tips:\n• Share your travel itinerary with someone\n• Book verified transport services\n• Check driver details before boarding\n• Sit in the back seat\n\n🚕 Taxis/Rideshare:\n• Verify license plate and driver photo\n• Share ride status with family/friends\n• Track your route on GPS\n• Don't travel alone late at night if possible\n\n🚂 Public Transport:\n• Stay in well-lit, crowded areas\n• Keep belongings secure\n• Know your route in advance\n• Avoid isolated stations\n\n✈️ Air Travel:\n• Keep valuables in carry-on\n• Stay aware of surroundings\n• Don't accept drinks from strangers\n\nStay connected with family during travel."
            },
            'digital_safety': {
                'keywords': ['digital safety', 'online', 'cyber', 'social media', 'privacy', 'stalking'],
                'response': "💻 Digital Safety Tips:\n\n📱 Social Media:\n• Review privacy settings regularly\n• Don't share real-time location updates\n• Be careful with \"check-ins\"\n• Don't accept requests from strangers\n\n📧 Email & Messaging:\n• Use strong, unique passwords\n• Enable two-factor authentication\n• Don't click suspicious links\n• Be wary of phishing attempts\n\n🔐 General Tips:\n• Keep your devices updated\n• Use VPN on public WiFi\n• Review app permissions\n• Log out from shared devices\n\nIf experiencing online harassment:\n• Block and report the person\n• Screenshot evidence\n• Report to platform administrators\n• Contact cyber crime cell if severe"
            },
            'workplace_safety': {
                'keywords': ['workplace safety', 'work', 'office', 'harassment at work', 'colleague'],
                'response': "🏢 Workplace Safety Guidelines:\n\nIf you experience harassment:\n• Document all incidents (dates, times, witnesses)\n• Report to HR immediately\n• Know your company's anti-harassment policy\n• Contact external authorities if internal reporting fails\n\nPhysical Safety at Work:\n• Know emergency exits\n• Don't work alone late if possible\n• Keep personal items secure\n• Trust your instincts about people\n\nUseful Contacts:\n• Internal HR\n• Internal security\n• External HR complaint: 1800-1234-5678\n\nKnow your rights under POSH Act (Prevention of Sexual Harassment)."
            },
            'night_safety': {
                'keywords': ['night safety', 'night', 'dark', 'late night', 'after dark'],
                'response': "🌙 Night Safety Guidelines:\n\n🚶 Walking Outside:\n• Stick to well-lit, busy routes\n• Walk confidently and aware\n• Avoid headphones or keep volume low\n• Let someone know your whereabouts\n\n🏠 Coming Home:\n• Have keys ready before reaching the door\n• Check the back seat before entering car\n• Do not linger at entrances\n\n🚗 Driving:\n• Park in well-lit, visible areas\n• Lock doors immediately upon entering\n• If followed, drive to a police station\n• Do not pick up hitchhikers\n\n🚌 Public Transport:\n• Try to travel during peak hours\n• Sit near driver or other passengers\n• Stay awake and alert\n\nIf you feel unsafe, find a shop or public place and call for help."
            },
            'home_safety': {
                'keywords': ['home safety', 'house', 'apartment', 'security at home', 'burglar'],
                'response': "🏠 Home Safety Tips:\n\n🚪 Door Security:\n• Use heavy-duty locks\n• Install door viewer/peephole\n• Don't open door to strangers\n• Use chain latch when opening door\n\n🪟 Window Security:\n• Lock all windows when leaving\n• Install security bars or grills\n• Consider window alarms\n\n📱 Technology:\n• Install security cameras\n• Use smart doorbells\n• Set up motion-sensor lights\n\n📞 Emergency:\n• Save emergency numbers on speed dial\n• Have a safe room prepared\n• Know your neighbors' contact\n\n🔑 When Moving In:\n• Change all locks\n• Check for spare keys\n• Review building security\n\nFor domestic safety concerns, contact women helpline 1091."
            },
            'helpline': {
                'keywords': ['helpline', 'women helpline', 'support', 'counseling', 'help line'],
                'response': "📞 Women Safety Helplines:\n\n🚺 Women Helpline (All India): 1091\n📱 Women Helpline (Domestic Abuse): 181\n👶 Child Helpline: 1098\n🚔 Police Emergency: 100\n🚑 Ambulance: 108\n🚒 Fire: 101\n\nWhat These Services Offer:\n• 24/7 emergency response\n• Legal guidance and support\n• Counseling services\n• Rescue operations coordination\n• Medical assistance\n\nAll calls are free and confidential. Don't hesitate to reach out if you need help."
            }
        }
        
    def get_response(self, query):
        """Get AI response for a user query"""
        query_lower = query.lower()
        
        # Check each category
        for category, data in self.knowledge_base.items():
            if any(keyword in query_lower for keyword in data['keywords']):
                return data['response']
        
        # Default response for unrecognized queries
        return self.get_default_response(query)
    
    def get_default_response(self, query):
        """Handle queries not in the knowledge base"""
        # Check for greeting
        greetings = ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'howdy']
        if any(greet in query.lower() for greet in greetings):
            return "👋 Hello! I'm your SafeGuard AI Assistant. I'm here to help you stay safe.\n\nYou can ask me about:\n• Emergency procedures\n• Safety tips\n• How to use features\n• Location tracking\n• Safe shelters\n• Filing complaints\n• And more!\n\nWhat would you like to know about?"
        
        # Check for thanks
        thanks = ['thank', 'thanks', 'appreciate']
        if any(word in query.lower() for word in thanks):
            return "You're welcome! 😊\n\nYour safety is my priority. Don't hesitate to ask if you need anything else.\n\nStay safe!"
        
        # Check for goodbye
        bye = ['bye', 'goodbye', 'see you', 'tata', 'ciao']
        if any(word in query.lower() for word in bye):
            return "Goodbye! Stay safe out there! 🛡️\n\nRemember, I'm here 24/7 if you need help. Just open the app and ask!"
        
        # Check for feelings of unsafety
        unsafe_words = ['scared', 'afraid', 'unsafe', 'frightened', 'terrified', 'nervous', 'anxious']
        if any(word in query.lower() for word in unsafe_words):
            return "I understand you're feeling unsafe. Let's take action to help you feel more secure:\n\n1. 🌐 Go to Location section and start tracking\n2. 📞 Use Fake Call feature if you need an excuse to leave\n3. 🏠 Find nearest safe shelter\n4. 📞 Call women helpline 1091 if you need someone to talk to\n5. 🚨 Use Emergency Alert if you feel in immediate danger\n\nYou're not alone. Help is available 24/7."
        
        # Default response
        return "I'm here to help with your safety! 🛡️\n\nI can assist you with:\n• Emergency alerts and procedures\n• Location tracking and sharing\n• Finding safe shelters\n• Filing complaints\n• Safety tips and advice\n• Answering questions about using the app\n\nTry asking:\n• \"How do I use emergency features?\"\n• \"What are safety tips?\"\n• \"How to file a complaint?\"\n• \"Find nearby shelters\"\n\nWhat would you like to know?"
    
    def process_command(self, command):
        """Process voice/text command - returns action to take"""
        command = command.lower()
        
        # Check for emergency keywords first
        if any(word in command for word in ['emergency', 'help', 'danger', 'panic', 'sos', 'save me']):
            return {
                'type': 'emergency',
                'action': 'emergencyAlert()',
                'message': "🚨 Emergency detected! Activating all safety features..."
            }
        elif any(word in command for word in ['siren', 'alarm', 'loud noise']):
            return {
                'type': 'siren',
                'action': 'activateSiren()',
                'message': "🔊 Activating siren alarm..."
            }
        elif any(word in command for word in ['fake call', 'fake call', 'pretend call', 'call me']):
            return {
                'type': 'fake_call',
                'action': 'initiateFakeCall()',
                'message': "📞 Initiating fake call..."
            }
        elif any(word in command for word in ['location', 'track', 'where am i', 'gps']):
            return {
                'type': 'location',
                'action': 'startLocationTracking()',
                'message': "📍 Starting location tracking..."
            }
        elif any(word in command for word in ['safe place', 'shelter', 'safe house', 'refuge']):
            return {
                'type': 'shelter',
                'action': 'showSection(\"shelters\")',
                'message': "🏠 Finding safe shelters..."
            }
        elif any(word in command for word in ['complaint', 'report', 'file']):
            return {
                'type': 'complaint',
                'action': 'showSection(\"complaints\")',
                'message': "📋 Opening complaint section..."
            }
        elif any(word in command for word in ['tips', 'advice', 'safety', 'how to stay safe']):
            return {
                'type': 'tips',
                'action': 'showSection(\"tips\")',
                'message': "💡 Loading safety tips..."
            }
        elif any(word in command for word in ['map', 'navigation', 'directions']):
            return {
                'type': 'map',
                'action': 'showSection(\"location\")',
                'message': "🗺️ Opening map..."
            }
        elif any(word in command for word in ['contact', 'helpline', 'phone', 'call']):
            return {
                'type': 'emergency',
                'action': 'showSection(\"emergency\")',
                'message': "📞 Showing emergency contacts..."
            }
        else:
            return {
                'type': 'info',
                'action': None,
                'message': self.get_response(command)
            }
    
    def listen_and_respond(self):
        if not self.available:
            return "AI Assistant not available. Please use text input instead."
        
        try:
            import speech_recognition as sr
            with sr.Microphone() as source:
                print("Listening...")
                audio = self.recognizer.listen(source, timeout=5)
                text = self.recognizer.recognize_google(audio)
                response = self.process_command(text)
                self.speak(response['message'] if isinstance(response, dict) else response)
                return response
        except Exception as e:
            return f"Sorry, I didn't catch that. Error: {str(e)}"
    
    def speak(self, text):
        if not self.available:
            return
        
        try:
            import pyttsx3
            self.tts_engine.say(text)
            self.tts_engine.runAndWait()
        except:
            pass

try:
    ai_assistant = AIAssistant()
except:
    ai_assistant = None
    print("AI Assistant initialization failed. App will run without voice features.")

# Routes
@app.route('/')
def index():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('landing-fixed.html')

@app.route('/landing')
def landing():
    return render_template('landing-fixed.html')

@app.route('/login-page')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/signin')
def signin():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('signin.html')

@app.route('/signup')
def signup():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    return render_template('signup.html')

@app.route('/auth-forms')
def auth_forms():
    """Return authentication forms for modal display"""
    return render_template('auth-modal.html')

@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username', '')
    email = data.get('email', '')
    password = data.get('password', '')
    pattern = data.get('pattern')
    phone = data.get('phone', '')
    first_name = data.get('firstName', '')
    last_name = data.get('lastName', '')
    
    # Validate required fields
    if not username or not email:
        return jsonify({'success': False, 'message': 'Username and email are required!'})
    
    # Validate authentication method
    if not password and not pattern:
        return jsonify({'success': False, 'message': 'Either password or pattern lock is required!'})
    
    # Validate pattern if provided
    if pattern and (not isinstance(pattern, list) or len(pattern) < 4):
        return jsonify({'success': False, 'message': 'Pattern must contain at least 4 dots!'})
    
    conn = sqlite3.connect('security_system.db')
    cursor = conn.cursor()
    
    try:
        # Hash pattern if provided
        pattern_hash = hash_pattern(pattern) if pattern else None
        
        cursor.execute('''
            INSERT INTO users (username, email, password_hash, pattern_hash, phone_number, emergency_contact)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (username, email, hash_password(password) if password else None, pattern_hash, phone, f"{first_name} {last_name}".strip()))
        conn.commit()
        return jsonify({'success': True, 'message': 'Registration successful! Please log in with your credentials.'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': 'Username or email already exists!'})
    finally:
        conn.close()

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username', '')
    password = data.get('password', '')
    
    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required!'})
    
    conn = sqlite3.connect('security_system.db')
    cursor = conn.cursor()
    
    # Try to find user by username or email
    cursor.execute('SELECT id, password_hash, username FROM users WHERE username = ? OR email = ?', (username, username))
    user = cursor.fetchone()
    conn.close()
    
    if user and verify_password(password, user[1]):
        session['user_id'] = user[0]
        session['username'] = user[2]  # Use the stored username
        return jsonify({'success': True, 'message': 'Login successful! Redirecting to dashboard...'})
    else:
        return jsonify({'success': False, 'message': 'Invalid username/email or password!'})

@app.route('/login-pattern', methods=['POST'])
def login_pattern():
    """Login using pattern lock"""
    data = request.get_json()
    username = data.get('username', '')
    pattern = data.get('pattern', [])
    
    if not username or not pattern:
        return jsonify({'success': False, 'message': 'Username and pattern are required!'})
    
    # Validate pattern format
    if not isinstance(pattern, list) or len(pattern) < 4:
        return jsonify({'success': False, 'message': 'Pattern must contain at least 4 dots!'})
    
    conn = sqlite3.connect('security_system.db')
    cursor = conn.cursor()
    
    # Find user by username or email
    cursor.execute('SELECT id, pattern_hash, username FROM users WHERE username = ? OR email = ?', (username, username))
    user = cursor.fetchone()
    conn.close()
    
    if user and user[1] and verify_pattern(pattern, user[1]):
        session['user_id'] = user[0]
        session['username'] = user[2]  # Use the stored username
        return jsonify({'success': True, 'message': 'Pattern login successful! Redirecting to dashboard...'})
    else:
        return jsonify({'success': False, 'message': 'Invalid username/email or pattern!'})

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    return render_template('dashboard.html')

@app.route('/api/location', methods=['POST'])
def update_location():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    latitude = data['latitude']
    longitude = data['longitude']
    
    conn = sqlite3.connect('security_system.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO location_tracking (user_id, latitude, longitude)
        VALUES (?, ?, ?)
    ''', (session['user_id'], latitude, longitude))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True})

@app.route('/api/complaints', methods=['POST'])
def submit_complaint():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    title = data['title']
    description = data['description']
    category = data.get('category', 'general')
    location = data.get('location', '')
    
    conn = sqlite3.connect('security_system.db')
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO complaints (user_id, title, description, category)
        VALUES (?, ?, ?, ?)
    ''', (session['user_id'], title, description, category))
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Complaint submitted successfully!'})

@app.route('/api/complaints/history', methods=['GET'])
def get_complaint_history():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    conn = sqlite3.connect('security_system.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT id, title, description, category, status, created_at
        FROM complaints
        WHERE user_id = ?
        ORDER BY created_at DESC
    ''', (session['user_id'],))
    
    complaints = cursor.fetchall()
    conn.close()
    
    complaint_list = []
    for complaint in complaints:
        complaint_list.append({
            'id': complaint[0],
            'title': complaint[1],
            'description': complaint[2],
            'category': complaint[3],
            'status': complaint[4],
            'created_at': complaint[5]
        })
    
    return jsonify(complaint_list)

@app.route('/api/shelters')
def get_shelters():
    conn = sqlite3.connect('security_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM safe_shelters')
    shelters = cursor.fetchall()
    conn.close()
    
    shelter_list = []
    for shelter in shelters:
        shelter_list.append({
            'id': shelter[0],
            'name': shelter[1],
            'address': shelter[2],
            'latitude': shelter[3],
            'longitude': shelter[4],
            'phone': shelter[5],
            'capacity': shelter[6],
            'facilities': shelter[7],
            'rating': shelter[8]
        })
    
    return jsonify(shelter_list)

@app.route('/api/tips')
def get_tips():
    conn = sqlite3.connect('security_system.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM emergency_tips ORDER BY created_at DESC')
    tips = cursor.fetchall()
    conn.close()
    
    tip_list = []
    for tip in tips:
        tip_list.append({
            'id': tip[0],
            'title': tip[1],
            'content': tip[2],
            'category': tip[3]
        })
    
    return jsonify(tip_list)

@app.route('/api/ai-assistant', methods=['POST'])
def ai_assistant_endpoint():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.get_json()
    command = data.get('command', '')
    
    # Use the enhanced AI assistant to process the command
    if ai_assistant:
        result = ai_assistant.process_command(command)
        if isinstance(result, dict):
            return jsonify({
                'response': result['message'],
                'type': result['type'],
                'action': result.get('action')
            })
        else:
            return jsonify({'response': result, 'type': 'info', 'action': None})
    else:
        # Fallback for when AI assistant is not available
        command_lower = command.lower()
        if any(word in command_lower for word in ['emergency', 'help', 'danger']):
            return jsonify({'response': '🚨 Emergency activated! Sharing location and calling emergency contacts.', 'type': 'emergency', 'action': 'emergencyAlert()'})
        elif 'location' in command_lower:
            return jsonify({'response': '📍 Location sharing activated with trusted contacts.', 'type': 'location', 'action': 'startLocationTracking()'})
        elif 'fake call' in command_lower:
            return jsonify({'response': '📞 Fake call will be initiated in 10 seconds.', 'type': 'fake_call', 'action': 'initiateFakeCall()'})
        elif 'siren' in command_lower:
            return jsonify({'response': '🔊 Siren alarm activated to alert nearby people.', 'type': 'siren', 'action': 'activateSiren()'})
        elif 'shelter' in command_lower or 'safe place' in command_lower:
            return jsonify({'response': '🏠 Finding nearest safe shelters...', 'type': 'shelter', 'action': 'showSection("shelters")'})
        else:
            return jsonify({'response': "🛡️ I'm here to help with safety and emergency assistance.\n\nYou can ask me about:\n• Emergency procedures\n• Safety tips\n• Location tracking\n• Safe shelters\n• Filing complaints\n• And more!", 'type': 'info', 'action': None})

@app.route('/api/siren', methods=['POST'])
def activate_siren():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # This would trigger audio alert and potentially notify authorities
    return jsonify({'success': True, 'message': 'Siren activated!'})

@app.route('/api/fake-call', methods=['POST'])
def fake_call():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    return jsonify({'success': True, 'message': 'Fake call initiated! You will receive a call in 10 seconds.'})

if __name__ == '__main__':
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)