# Live Q&A and Polling Platform for Educators

A Django web application that replicates the core functionality of Slido, allowing users to create events, manage live polls, and host Q&A sessions with real-time updates.

## 🚀 Features

### Core Functionality
- **Event Creation**: Logged-in users can create events with unique codes, titles, and descriptions
- **Live Q&A**: 
  - Anonymous participants can join events using unique event codes
  - Submit questions and upvote existing ones
  - Real-time question updates and voting
  - Host can mark questions as answered
- **Interactive Polling**:
  - Multiple choice polls with real-time vote counting
  - Rating polls (1-5 stars)
  - Word cloud polls for text responses
  - Real-time result updates
- **User Authentication**: Registration and login for event hosts
- **Real-time Updates**: WebSocket-powered live updates for all participants

### Technical Features
- **Responsive Design**: Built with Bootstrap 5 for mobile and desktop
- **REST API**: Django REST Framework for all CRUD operations
- **WebSocket Support**: Django Channels for real-time features
- **Session Tracking**: Anonymous participant tracking via session IDs
- **Admin Interface**: Django admin for event and data management

## 🛠 Technology Stack

- **Backend**: Django 5.2.6 with Django REST Framework
- **Real-time**: Django Channels with Redis
- **Frontend**: HTML, CSS, Vanilla JavaScript, Bootstrap 5
- **Database**: SQLite (development) / PostgreSQL (production)
- **WebSockets**: Django Channels with Redis backend

## 📋 Prerequisites

- Python 3.11+
- Redis server (for WebSocket functionality)
- Git

## 🔧 Installation & Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd slido_clone
   ```

2. **Create and activate virtual environment**:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Install and start Redis** (required for WebSockets):
   ```bash
   # macOS with Homebrew
   brew install redis
   brew services start redis
   
   # Ubuntu/Debian
   sudo apt-get install redis-server
   sudo service redis-server start
   
   # Windows - Download from https://redis.io/download
   ```

5. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

6. **Run database migrations**:
   ```bash
   python manage.py migrate
   ```

7. **Create a superuser** (optional):
   ```bash
   python manage.py createsuperuser
   ```

8. **Collect static files**:
   ```bash
   python manage.py collectstatic
   ```

9. **Start the development server**:
   ```bash
   python manage.py runserver
   ```

The application will be available at `http://127.0.0.1:8000/`

## 🎯 Usage Guide

### For Event Hosts

1. **Register/Login**: Create an account or login at `/auth/register/` or `/auth/login/`
2. **Create Events**: Go to Dashboard and click "Create Event"
3. **Share Event Code**: Give participants the unique event code (e.g., "DJ4R")
4. **Manage Q&A**: 
   - View incoming questions in real-time
   - Mark questions as answered
   - Sort by popularity (upvotes)
5. **Create Polls**:
   - Multiple choice with custom options
   - Rating polls for feedback
   - Word cloud for open responses
6. **Monitor Live**: Host view shows real-time participation and results

### For Participants

1. **Join Event**: Enter event code on homepage
2. **Ask Questions**: Submit questions anonymously
3. **Vote**: Upvote interesting questions
4. **Participate in Polls**: 
   - Vote on multiple choice options
   - Rate with star system
   - Submit words for word clouds
5. **Real-time Updates**: See new questions and poll results instantly

## 🏗 Project Structure

```
slido_clone/
├── slidoclone/                 # Main Django project
│   ├── settings.py            # Django settings
│   ├── urls.py                # Main URL configuration
│   ├── asgi.py                # ASGI configuration for WebSockets
│   └── wsgi.py                # WSGI configuration
├── slido/                     # Main Django app
│   ├── models.py              # Database models
│   ├── views.py               # Template views
│   ├── api_views.py           # REST API views
│   ├── serializers.py         # DRF serializers
│   ├── consumers.py           # WebSocket consumers
│   ├── routing.py             # WebSocket URL routing
│   ├── auth_views.py          # Authentication views
│   ├── urls.py                # App URL patterns
│   ├── auth_urls.py           # Authentication URLs
│   ├── api_urls.py            # API URL patterns
│   └── admin.py               # Django admin configuration
├── templates/                 # HTML templates
│   ├── base.html              # Base template
│   ├── auth/                  # Authentication templates
│   └── slido/                 # App templates
├── static/                    # Static files
│   ├── css/                   # Custom CSS
│   └── js/                    # Custom JavaScript
├── requirements.txt           # Python dependencies
├── manage.py                  # Django management script
└── README.md                  # This file
```

## 🗄 Database Models

### Core Models

- **Event**: Stores event information (title, description, event_code, host, is_active)
- **Question**: User-submitted questions linked to events
- **QuestionUpvote**: Tracks upvotes on questions by session
- **Poll**: Polls created by event hosts (multiple types)
- **PollOption**: Options for multiple-choice polls
- **Vote**: Votes on poll options
- **WordCloudResponse**: Text responses for word cloud polls
- **RatingResponse**: Rating submissions for rating polls

## 🔌 API Endpoints

### Events
- `GET/POST /api/events/` - List/create events
- `GET /api/events/{event_code}/` - Get event details
- `POST /api/events/{event_code}/toggle_active/` - Toggle event status

### Questions
- `GET/POST /api/events/{event_code}/questions/` - List/create questions
- `POST /api/questions/{id}/upvote/` - Toggle question upvote
- `POST /api/questions/{id}/mark_answered/` - Mark as answered (host only)

### Polls
- `GET/POST /api/events/{event_code}/polls/` - List/create polls
- `POST /api/polls/{id}/toggle_active/` - Activate/deactivate poll
- `POST /api/votes/` - Submit poll votes

## 🔄 WebSocket Events

### Client → Server
- `question_submit` - Submit new question
- `question_upvote` - Upvote/downvote question
- `poll_vote` - Submit poll vote
- `poll_activate` - Activate poll (host only)
- `question_mark_answered` - Mark question as answered (host only)

### Server → Client
- `question_new` - New question submitted
- `question_upvote_update` - Question upvote count changed
- `question_answered_update` - Question marked as answered
- `poll_activated` - New poll activated
- `poll_results_update` - Poll results updated

## 🧪 Testing

Run the Django test suite:
```bash
python manage.py test
```

Test WebSocket functionality:
1. Start the server with Redis running
2. Open multiple browser tabs/windows
3. Create an event as host
4. Join as participant in other tabs
5. Test real-time question submission and polling

## 🚀 Deployment

### Production Settings

1. **Environment Variables**:
   ```bash
   DEBUG=False
   SECRET_KEY=your-secret-key
   DATABASE_URL=postgresql://user:pass@host:port/dbname
   REDIS_URL=redis://localhost:6379/0
   ```

2. **Database**: Use PostgreSQL for production
3. **Redis**: Set up Redis server for WebSocket support
4. **Static Files**: Configure proper static file serving
5. **Security**: Update `ALLOWED_HOSTS` and security settings

### Deployment Options

- **Railway**: Easy deployment with automatic PostgreSQL and Redis
- **DigitalOcean**: App Platform with managed databases
- **AWS**: EC2 with RDS PostgreSQL and ElastiCache Redis
- **Docker**: Containerized deployment

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Commit changes: `git commit -am 'Add feature'`
4. Push to branch: `git push origin feature-name`
5. Submit a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Django and Django REST Framework teams
- Django Channels for WebSocket support
- Bootstrap for responsive design
- Font Awesome for icons

## 📞 Support

For support, email support@example.com or create an issue in the repository.

---

**Note**: This is a demo application for learning purposes. For production use, implement additional security measures, error handling, and performance optimizations.
