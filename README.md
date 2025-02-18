# Medical Appointment Scheduler - POC

A proof-of-concept application that demonstrates an AI-powered medical appointment scheduling system. The system analyzes patient symptoms using Google's Gemini AI, recommends appropriate specialists, and manages appointments through Google Calendar integration.

## Features

- 🤖 AI-powered symptom analysis using Gemini-Pro
- 👩‍⚕️ Specialist recommendation based on symptoms
- 📅 Real-time calendar integration with Google Calendar
- 🔄 Interactive chat interface for patient communication
- ⏰ Automated time slot management
- 📧 Email notifications for appointments
- 🔒 Basic patient information management

## Getting Started

### Prerequisites

- Python 3.8+
- Google Cloud Platform account
- OpenAI API access
- Google Calendar API credentials

### Environment Setup

1. Clone the repository:
```bash
git clone https://github.com/Sunil-1234/Ai-agent-Appointment.git
cd Ai-agent-Appointment
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Create a `.env` file with the following variables:
```
GOOGLE_API_KEY=your_gemini_api_key

```

5. Set up Google Calendar credentials:
- Place your `calender_credential.json` in the project root
- Note: This file should not be committed to version control

### Running the Application

```bash
streamlit run app.py
```

## Current Limitations (POC Only)

This is a Proof of Concept implementation and has several limitations that would need to be addressed for a production environment:

### Technical Debt
- Code needs significant refactoring for better organization and maintainability
- Error handling needs to be more robust
- Logging system needs enhancement
- Test coverage needed

### Architecture Improvements Needed
- Should be split into microservices for better scalability
- Need proper API gateway implementation
- Database integration required for doctor and patient management
- Authentication and authorization system needs to be implemented
- HIPAA compliance considerations needed

### Data Management
- Doctor information should be stored in a database instead of hardcoded
- Patient data needs proper storage and encryption
- Appointment history and medical records management needed


### Additional Features Needed
- Patient medical history tracking
- Prescription management
- Payment integration
- Multiple language support
- Appointment rescheduling/cancellation
- Waiting list management
- Emergency case prioritization



## Acknowledgments

- Google Gemini AI for symptom analysis
- OpenAI for embeddings
- Streamlit for the web interface
- Google Calendar API for appointment management

## Disclaimer

This is a proof of concept and should not be used in production without significant improvements in security, reliability, and compliance with healthcare regulations.
