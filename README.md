# SolaceSquad - Wellbeing Platform

A comprehensive wellbeing and wellness platform connecting users with professional consultants.

## Features

- 🏥 **Health Monitoring**: Track vitals, mood, and overall wellbeing
- 👨‍⚕️ **Consultant Booking**: Schedule appointments with verified consultants
- 💬 **AI Assistant**: Get instant support and guidance
- 📞 **Video Calls**: Secure video consultations
- 📊 **Health Dashboard**: Visualize your health trends
- 📱 **Progressive Web App**: Works on all devices

## Technology Stack

- **Backend**: FastAPI (Python)
- **Database**: SQLite (development), PostgreSQL (production)
- **AI**: OpenAI GPT-4o-mini (will migrate to Vertex AI)
- **Hosting**: Google Cloud Run
- **Real-time**: Socket.IO for video calls

## Deployment

This app is configured for automatic deployment to Google Cloud Run via Cloud Build.

### Prerequisites

- Google Cloud Project
- Cloud Run API enabled
- Cloud Build API enabled

### Automatic Deployment

Push to the `main` branch to trigger automatic deployment.

## Local Development

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload
```

Visit: http://localhost:8000

## Environment Variables

Required environment variables:
- `DATABASE_URL`: Database connection string
- `SECRET_KEY`: Session secret key
- `OPENAI_API_KEY`: OpenAI API key (optional)
- `ENVIRONMENT`: production/development
- `DEBUG`: True/False

## License

Proprietary - SolaceSquad

## Contact

For support: sg@solacesquad.com
