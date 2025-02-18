import streamlit as st
import google.generativeai as genai
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import json
import os
import pickle
from typing import Dict, List, Optional
from dotenv import load_dotenv
import pytz
from google.oauth2 import service_account

# If modifying these scopes, delete the file token.pickle.
SCOPES = ['https://www.googleapis.com/auth/calendar','https://www.googleapis.com/auth/calendar.events']

class GeminiAI:
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Get API key from environment variable
        api_key = os.getenv('GOOGLE_API_KEY')
        if not api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
            
        # Configure Gemini
        genai.configure(api_key=api_key)
        
        # Initialize the model
        try:
            self.model = genai.GenerativeModel('gemini-pro')
        except Exception as e:
            st.error(f"Error initializing Gemini model: {str(e)}")
            raise

    def analyze_symptoms(self, symptoms: str) -> Dict:
        """Analyze symptoms using Gemini AI"""
        try:
            prompt = f"""You are a medical scheduling assistant. Analyze these symptoms and provide a response in valid JSON format with no additional text.
            
              Use ONLY these specialization options:
        - Orthopedist (for bone, joint, muscle issues)
        - Cardiologist (for heart issues)
        - General Practitioner (for general health issues)
        

            Symptoms: {symptoms}

            Respond with ONLY this exact JSON structure:
            {{
                "isEmergency": false,
                "specialization": "appropriate medical specialist",
                "urgency": "low/medium/high",
                "advice": "immediate advice for the patient",
                "explanation": "explanation of why this specialist is recommended"
            }}"""

            response = self.model.generate_content(prompt)
            response_text = response.text.strip()
            
            # Remove any markdown formatting if present
            if response_text.startswith("```json"):
                response_text = response_text.replace("```json", "").replace("```", "").strip()
            
            try:
                # Parse the JSON response
                analysis = json.loads(response_text)
                
                # Validate required fields
                required_fields = ["isEmergency", "specialization", "urgency", "advice", "explanation"]
                if not all(field in analysis for field in required_fields):
                    raise ValueError("Missing required fields in response")
                
                return analysis
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON response: {response_text}")
                st.error(f"JSON Error: {str(e)}")
                return {
                    "isEmergency": False,
                    "specialization": "General Practitioner",
                    "urgency": "medium",
                    "advice": "Please consult with a doctor for proper evaluation.",
                    "explanation": "Unable to analyze symptoms properly. Recommending general consultation."
                }
                
        except Exception as e:
            st.error(f"Error analyzing symptoms: {str(e)}")
            return {
                "isEmergency": False,
                "specialization": "General Practitioner",
                "urgency": "medium",
                "advice": "Please consult with a doctor for proper evaluation.",
                "explanation": "Unable to analyze symptoms properly. Recommending general consultation."
            }

class GoogleCalendarAPI:
    def __init__(self, user_email=None):
        self.creds = None
        self.service = None
        self.user_email = user_email

        self.setup_credentials()

    def setup_credentials(self):
        """Set up Google Calendar credentials"""
        SCOPES = ['https://www.googleapis.com/auth/calendar']
        
        # Create a unique token file for each user if email is provided
        token_filename = (f'token_{self.user_email}.pickle' 
                          if self.user_email 
                          else 'token.pickle')
        
        # The file stores the user's access and refresh tokens
        if os.path.exists(token_filename):
            with open(token_filename, 'rb') as token:
                self.creds = pickle.load(token)
        
        # If there are no (valid) credentials available, let the user log in
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                if not os.path.exists('calender_credential.json'):
                    st.error("calender_credential.json not found! Please set up Google Calendar API credentials.")
                    st.stop()
                    
                flow = InstalledAppFlow.from_client_secrets_file(
                    '/Users/sunil_modi/Documents/Ai_Agent/Appointment_agent/calender_credential.json', 
                    SCOPES)
                
                # Use standard local server flow
                self.creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open(token_filename, 'wb') as token:
                pickle.dump(self.creds, token)

        try:
            self.service = build('calendar', 'v3', credentials=self.creds)
            # Test the connection
            self.service.calendarList().list().execute()
            
            # Additional logging for multi-user support
            if self.user_email:
                st.success(f"Successfully connected to Google Calendar for {self.user_email}!")
            else:
                st.success("Successfully connected to Google Calendar!")
        
        except Exception as e:
            st.error(f"Error connecting to Google Calendar: {str(e)}")
            st.info("Please make sure you've completed the Google Calendar API setup")
            st.stop()

    def get_available_slots(self, doctor_id: int, date: str) -> List[str]:
        """
        Get available time slots from Google Calendar   
        
        Args:
            doctor_id (int): ID of the doctor
            date (str): Date in 'YYYY-MM-DD' format
        
        Returns:
            List[str]: Available time slots as formatted strings
        """
        try:
            st.write(f"Checking availability for doctor ID: {doctor_id}")
            calendar_id = self.get_doctor_calendar_id(doctor_id)
            if not calendar_id:
                st.error(f"No calendar found for doctor ID: {doctor_id}")
                return []

            # Define timezone (using Asia/Kolkata as specified in original code)
            kolkata_tz = pytz.timezone('Asia/Kolkata')
            
            # Convert date string to datetime in Kolkata timezone
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            date_obj = kolkata_tz.localize(date_obj)
            
            # Set working hours (9 AM to 5 PM) in Kolkata timezone
            start_time = date_obj.replace(hour=9, minute=0, second=0, microsecond=0)
            end_time = date_obj.replace(hour=17, minute=0, second=0, microsecond=0)

            st.write(f"Checking calendar {calendar_id} from {start_time} to {end_time}")

            # Convert times to UTC for Google Calendar API
            start_time_utc = start_time.astimezone(pytz.UTC)
            end_time_utc = end_time.astimezone(pytz.UTC)

            # Get busy periods from Google Calendar
            events_result = self.service.freebusy().query(
                body={
                    "timeMin": start_time_utc.isoformat(),
                    "timeMax": end_time_utc.isoformat(),
                    "timeZone": 'Asia/Kolkata',
                    "items": [{"id": calendar_id}]
                }
            ).execute()

            st.write("Successfully queried calendar API")
            busy_periods = events_result['calendars'][calendar_id]['busy']
            st.write(f"Found {len(busy_periods)} busy periods")

            # Generate available slots
            available_slots = []
            current_slot = start_time
            while current_slot < end_time:
                # Create 30-minute slot
                slot_end = current_slot + timedelta(minutes=30)
                
                # Check slot availability
                is_available = True
                for busy in busy_periods:
                    # Convert busy times to Kolkata timezone for consistent comparison
                    busy_start = datetime.fromisoformat(busy['start']).astimezone(kolkata_tz)
                    busy_end = datetime.fromisoformat(busy['end']).astimezone(kolkata_tz)
                    
                    # Check for overlap between current slot and busy periods
                    if (current_slot >= busy_start and current_slot < busy_end) or \
                       (slot_end > busy_start and slot_end <= busy_end) or \
                       (busy_start >= current_slot and busy_start < slot_end):
                        is_available = False
                        break
                
                # Add available slot
                if is_available:
                    available_slots.append(current_slot.strftime("%I:%M %p"))
                
                # Move to next slot
                current_slot = slot_end

            st.write(f"Found {len(available_slots)} available slots")
            return available_slots

        except Exception as e:
            # Detailed error logging
            error_message = f"Error fetching calendar availability: {str(e)}"
            st.error(error_message)
            
            # Log additional context if possible
            if hasattr(e, '__traceback__'):
                import traceback
                error_details = traceback.format_exc()
                st.error(f"Error Details:\n{error_details}")
            
            return []

    def schedule_appointment(self, doctor_id: int, date: str, time: str, patient_name: str, patient_email: str, patient_phone: str, symptoms: str) -> bool:
        """Schedule appointment in Google Calendar"""
        try:
            calendar_id = self.get_doctor_calendar_id(doctor_id)
            if not calendar_id:
                st.error(f"No calendar found for doctor ID: {doctor_id}")
                return False

            # Combine date and time
            datetime_str = f"{date} {time}"
            start_time = datetime.strptime(datetime_str, "%Y-%m-%d %I:%M %p")
            end_time = start_time + timedelta(minutes=30)

            # Create event with patient details
            event = {
                'summary': f'Patient Appointment: {patient_name}',
                'description': f"""
                Patient Details:
                Name: {patient_name}
                Email: {patient_email}
                Phone: {patient_phone}
                
                Symptoms: {symptoms}
                """,
                'start': {
                    'dateTime': start_time.isoformat(),
                    'timeZone': 'Asia/Kolkata',
                },
                'end': {
                    'dateTime': end_time.isoformat(),
                    'timeZone': 'Asia/Kolkata',
                },
                'attendees': [
                    {'email': patient_email},  # Send invitation to patient
                ],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 30},
                    ],
                },
            }

            # Add event to calendar
            event = self.service.events().insert(
                calendarId=calendar_id,
                body=event,
                sendUpdates='all'  # Send email notifications
            ).execute()

            st.success(f"Appointment scheduled! You will receive a confirmation email at {patient_email}")
            return True

        except Exception as e:
            st.error(f"Error scheduling appointment: {str(e)}")
            return False
    
    def get_doctor_calendar_id(self, doctor_id: int) -> str:
        """Get Google Calendar ID for a doctor"""
        # Map of doctor IDs to their calendar IDs (email addresses)
        doctors_db = {
            1: {
                'name': 'Dr. Sunil',
                'calendar_id': 'sunilshourya9570@gmail.com',
                'specialization': 'Cardiologist'
            },
            2: {
                'name': 'Dr. Ankit',
                'calendar_id': 'ankityono@gmail.com',
                'specialization': 'Cardiologist'
            },
            3: {
                'name': 'Dr. SSSH',
                'calendar_id': 'sshsofttech3@gmail.com',
                'specialization': 'Orthopedist'
            },
            4: {
                'name': 'Dr. SHREYANSH',
                'calendar_id': 'shreyanshranjan5@gmail.com',
                'specialization': 'General Practitioner'
            }
        }
        
        doctor = doctors_db.get(doctor_id)
        return doctor['calendar_id'] if doctor else None
    
class MedicalScheduler:
    def __init__(self):
        self.calendar_api = GoogleCalendarAPI(user_email='sunilshourya9570@gmail.com')
        self.gemini_ai = GeminiAI()
        
        # Initialize patient session state
        if 'patient_logged_in' not in st.session_state:
            st.session_state.patient_logged_in = False
        if 'patient_info' not in st.session_state:
            st.session_state.patient_info = {}
        
        # Initialize chat session state
        if 'messages' not in st.session_state:
            st.session_state.messages = []
        if 'current_state' not in st.session_state:
            st.session_state.current_state = {
                "symptoms": None,
                "specialization": None,
                "selected_doctor": None,
                "selected_date": None,
                "selected_time": None
            }

    def patient_login(self):
        """Handle patient login"""
        st.title("Medical Appointment Scheduler")
        
        with st.form("patient_login"):
            patient_name = st.text_input("Patient Full Name")
            patient_email = st.text_input("Email")
            patient_phone = st.text_input("Phone Number")
            
            submitted = st.form_submit_button("Start Consultation")
            if submitted and patient_name and patient_email and patient_phone:
                st.session_state.patient_logged_in = True
                st.session_state.patient_info = {
                    "name": patient_name,
                    "email": patient_email,
                    "phone": patient_phone
                }
                st.session_state.messages = [
                    {"role": "assistant", "content": f"Hello {patient_name}! I'm your medical scheduling assistant. Please describe your symptoms or health concerns."}
                ]
                st.rerun()
    def analyze_symptoms(self, symptoms: str) -> Dict:
        """Analyze symptoms using Gemini AI"""
        with st.spinner("Analyzing your symptoms..."):
            analysis = self.gemini_ai.analyze_symptoms(symptoms)
            
            if analysis:
                if analysis["isEmergency"]:
                    emergency_message = f"⚠️ EMERGENCY: {analysis['explanation']}\n\nPlease seek immediate medical attention or call emergency services."
                    st.session_state.messages.append({"role": "assistant", "content": emergency_message})
                    return None
                
                # For non-emergency cases, return the analysis
                return analysis
            
            # If analysis failed, return a default response
            return {
                "isEmergency": False,
                "specialization": "General Practitioner",
                "urgency": "medium",
                "advice": "Please consult with a doctor for proper evaluation.",
                "explanation": "Unable to analyze symptoms properly. Recommending general consultation."
            }
    def fetch_doctors(self, specialization: str) -> List[Dict]:
        """Fetch doctors based on specialization"""
        # This would typically be a database query or API call
        # Using mock data for demonstration
        specialization_mapping = {
        "Orthopedic": "Orthopedist",
        "Orthopedist": "Orthopedist",
        "Cardiologist": "Cardiologist",
        "Cardiology": "Cardiologist",
        "General Practitioner": "General Practitioner",
        "General Physician": "General Practitioner",
        "GP": "General Practitioner"
    }

    # Normalize the specialization
        normalized_specialization = specialization_mapping.get(specialization, "General Practitioner")

        doctors_db = {
            "Cardiologist": [
                {"id": 1, "name": "Dr. Sunil", "specialization": "Cardiologist", 
                 "experience": "15 years", "expertise": "Heart Disease, Cardiac Surgery"},
                {"id": 2, "name": "Dr. Ankit", "specialization": "Cardiologist", 
                 "experience": "12 years", "expertise": "Preventive Cardiology"}
            ],
            "Orthopedist": [
                {"id": 3, "name": "Dr. SSSH", "specialization": "Orthopedist", 
                 "experience": "10 years", "expertise": "Sports Medicine, Joint Replacement"},
                   ],
            "General Practitioner": [
                {"id": 5, "name": "Dr. SHREYANSH", "specialization": "General Practitioner", 
                 "experience": "20 years", "expertise": "Family Medicine"},
                ]
        }
        st.write(f"Requested specialization: {specialization}")
        st.write(f"Normalized specialization: {normalized_specialization}")

        doctors = doctors_db.get(normalized_specialization, doctors_db["General Practitioner"])
        return doctors

    def get_available_slots(self, doctor_id: int, date: str) -> List[str]:
        """Get available time slots from Google Calendar"""
        return self.calendar_api.get_available_slots(doctor_id, date)

    def schedule_appointment(self, doctor_id: int, date: str, time: str) -> bool:
        """Schedule appointment in Google Calendar"""
        return self.calendar_api.schedule_appointment(
            doctor_id=doctor_id,
            date=date,
            time=time,
            patient_name=st.session_state.patient_info['name'],
            patient_email=st.session_state.patient_info['email'],
            patient_phone=st.session_state.patient_info['phone'],
            symptoms=st.session_state.current_state["symptoms"]
        )
    
    def run(self):

        if not st.session_state.patient_logged_in:
            self.patient_login()
            return
        
        """Main Streamlit UI"""
        st.title("Medical Appointment Scheduler")
        st.write("---")

        with st.sidebar:
            st.write(f"Patient: {st.session_state.patient_info['name']}")
            if st.button("Logout"):
                st.session_state.patient_logged_in = False
                st.session_state.patient_info = {}
                st.session_state.messages = []
                st.session_state.current_state = {
                    "symptoms": None,
                    "specialization": None,
                    "selected_doctor": None,
                    "selected_date": None,
                    "selected_time": None
                }
                st.rerun()

        # Display chat messages
        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.write(message["content"])
                # If this message contains doctor list, show the buttons
                if message == st.session_state.messages[-1] and "specialists" in message["content"].lower():
                    doctors = self.fetch_doctors(st.session_state.current_state["specialization"])
                    
                    # Display doctor selection buttons in a clean layout
                    for doctor in doctors:
                        if st.button(
                            f"{doctor['name']} - {doctor['experience']} - {doctor['expertise']}", 
                            key=f"doc_{doctor['id']}"
                        ):
                            st.session_state.current_state["selected_doctor"] = doctor
                            confirm_msg = f"You've selected {doctor['name']}. Let me check their availability."
                            st.session_state.messages.append({"role": "assistant", "content": confirm_msg})
                            self.show_calendar(doctor)
                            st.rerun()

        # Handle chat input
        if prompt := st.chat_input("Type your symptoms or health concerns here..."):
            # Add user message to chat
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.write(prompt)

            # Process user input based on current state
            if not st.session_state.current_state["symptoms"]:
                # Analyze symptoms
                with st.spinner("Analyzing your symptoms..."):
                    analysis = self.analyze_symptoms(prompt)
                
                if analysis:
                    if analysis["isEmergency"]:
                        emergency_message = f"⚠️ EMERGENCY: {analysis['explanation']}\n\nPlease seek immediate medical attention or call emergency services."
                        st.session_state.messages.append({"role": "assistant", "content": emergency_message})
                        with st.chat_message("assistant"):
                            st.write(emergency_message)
                            st.error("This is a medical emergency. Please call emergency services.")
                    else:
                        st.session_state.current_state["symptoms"] = prompt
                        st.session_state.current_state["specialization"] = analysis["specialization"]
                        
                        # Fetch and display available doctors
                        doctors = self.fetch_doctors(analysis["specialization"])
                        response = f"{analysis['explanation']}\n\nI recommend seeing a {analysis['specialization']}. Here are available specialists:"
                        
                        st.session_state.messages.append({"role": "assistant", "content": response})
                        with st.chat_message("assistant"):
                            st.write(response)
                            
                            # Display doctor selection buttons
                            for doctor in doctors:
                                if st.button(
                                    f"{doctor['name']} - {doctor['experience']} - {doctor['expertise']}", 
                                    key=f"doc_{doctor['id']}"
                                ):
                                    st.session_state.current_state["selected_doctor"] = doctor
                                    self.show_calendar(doctor)
                                    st.rerun()

        # Show calendar if doctor is selected but date isn't
        if st.session_state.current_state["selected_doctor"] and not st.session_state.current_state["selected_date"]:
            self.show_calendar(st.session_state.current_state["selected_doctor"])

        # Show time slots if date is selected but time isn't
        if st.session_state.current_state["selected_date"] and not st.session_state.current_state["selected_time"]:
            self.show_time_slots()

        # Show current appointment status if everything is selected
        if all(st.session_state.current_state.values()):
            doctor = st.session_state.current_state["selected_doctor"]
            date = st.session_state.current_state["selected_date"]
            time = st.session_state.current_state["selected_time"]
            st.success(f"✅ Appointment scheduled with {doctor['name']} for {date} at {time}")

        # Add a reset button
        if st.button("Start New Appointment"):
            st.session_state.current_state = {
                "symptoms": None,
                "specialization": None,
                "selected_doctor": None,
                "selected_date": None,
                "selected_time": None
            }
            st.session_state.messages = [
                {"role": "assistant", "content": "Hello! I'm your medical scheduling assistant. Please describe your symptoms or health concerns."}
            ]
            st.rerun()

    def show_calendar(self, doctor: Dict):
        """Display calendar for date selection"""
        st.write(f"Select an appointment date for {doctor['name']}:")
        
        # Show next 7 days
        today = datetime.now()
        dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        
        cols = st.columns(len(dates))
        for i, date in enumerate(dates):
            with cols[i]:
                if st.button(date, key=f"date_{date}"):
                    st.session_state.current_state["selected_date"] = date
                    st.rerun()

    def show_time_slots(self):
        """Display available time slots"""
        doctor = st.session_state.current_state["selected_doctor"]
        date = st.session_state.current_state["selected_date"]
        
        st.write(f"Available time slots for {doctor['name']} on {date}:")
        
        slots = self.get_available_slots(doctor['id'], date)
        cols = st.columns(3)
        for i, slot in enumerate(slots):
            with cols[i % 3]:
                if st.button(slot, key=f"slot_{slot}"):
                    st.session_state.current_state["selected_time"] = slot
                    if self.schedule_appointment(doctor['id'], date, slot):
                        confirmation = f"✅ Appointment scheduled with {doctor['name']} for {date} at {slot}"
                        st.session_state.messages.append({"role": "assistant", "content": confirmation})
                        with st.chat_message("assistant"):
                            st.success(confirmation)
                            st.write("You'll receive a confirmation email shortly with appointment details.")
                    else:
                        st.error("Failed to schedule appointment. Please try again.")

if __name__ == "__main__":
    scheduler = MedicalScheduler()
    scheduler.run()