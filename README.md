# Ethical Phishing Simulation Platform

A safe, controlled platform for conducting phishing simulation tests to improve security awareness training within organizations.

## 🎯 Purpose

This platform enables security professionals to:
- Create and manage ethical phishing simulation campaigns
- Track user interactions (email opens, link clicks, form submissions)
- Generate comprehensive analytics and reports
- Provide immediate educational feedback to users
- Maintain compliance with security and ethical standards

## 🚀 Features

### Core Functionality
- **Campaign Management**: Create, schedule, and manage phishing simulation campaigns
- **Target Management**: Import and manage target users via CSV upload
- **Template System**: Create and customize phishing email templates with variable substitution
- **Email Tracking**: Track email opens, link clicks, and form submissions in real-time
- **Analytics Dashboard**: Comprehensive metrics and visualizations
- **Educational Training**: Immediate feedback and training pages for users who interact with phishing emails
- **Export & Reporting**: CSV exports and detailed reporting capabilities

### Security & Ethics
- **Consent Management**: Mandatory consent verification for all campaigns
- **Data Protection**: No storage of actual credentials or sensitive information
- **Audit Logging**: Comprehensive audit trails for compliance
- **Rate Limiting**: Protection against abuse and system overload
- **Security Headers**: OWASP-compliant security headers
- **Input Validation**: Comprehensive input sanitization and validation

### Technical Features
- **Responsive Design**: Mobile-friendly Bootstrap-based interface
- **Docker Support**: Full containerization for easy deployment
- **Background Processing**: Asynchronous email sending with rate limiting
- **Database Support**: PostgreSQL with migration support
- **Logging System**: Comprehensive application and security logging
- **Error Handling**: Robust error handling with user-friendly error pages

## 📋 Requirements

- Python 3.11+
- PostgreSQL 12+
- Redis (optional, for background tasks)
- SMTP server (Gmail, SendGrid, Mailgun, etc.)

## 🛠️ Installation

### Quick Start with Docker

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd Ethical_Phishing_Simulation_Platform
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

3. **Run with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Access the application**:
   - Web Interface: http://localhost:5000
   - Default admin credentials will be created automatically

### Manual Installation

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set up PostgreSQL database**:
   ```sql
   CREATE DATABASE phishing_db;
   CREATE USER phishuser WITH PASSWORD 'yourpassword';
   GRANT ALL PRIVILEGES ON DATABASE phishing_db TO phishuser;
   ```

3. **Configure environment variables**:
   ```bash
   export FLASK_ENV=development
   export DATABASE_URL=postgresql://phishuser:yourpassword@localhost:5432/phishing_db
   export SECRET_KEY=your-secret-key-here
   ```

4. **Initialize the database**:
   ```bash
   python app.py
   ```

## 🔧 Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_ENV` | Application environment | `development` |
| `SECRET_KEY` | Flask secret key | Required |
| `DATABASE_URL` | PostgreSQL connection string | Required |
| `BASE_URL` | Application base URL | `http://localhost:5000` |
| `MAIL_SERVER` | SMTP server | `smtp.gmail.com` |
| `MAIL_PORT` | SMTP port | `587` |
| `MAIL_USE_TLS` | Use TLS for SMTP | `true` |
| `MAIL_USERNAME` | SMTP username | Required |
| `MAIL_PASSWORD` | SMTP password | Required |
| `CAMPAIGN_CONSENT_REQUIRED` | Require consent for campaigns | `true` |
| `DATA_RETENTION_DAYS` | Data retention period | `90` |
| `MAX_EMAILS_PER_HOUR` | Email sending rate limit | `100` |

## 📊 Usage

### Creating a Campaign

1. **Navigate to Campaigns**: Click "Campaigns" in the navigation menu
2. **Create New Campaign**: Fill in campaign details and select an email template
3. **Add Targets**: Import targets via CSV file or add manually
4. **Verify Consent**: Confirm you have obtained proper consent
5. **Send Campaign**: Launch the campaign to start sending emails

### CSV Target Import Format

```csv
email,first_name,last_name,department
john.doe@example.com,John,Doe,IT
jane.smith@example.com,Jane,Smith,HR
```

### Tracking Results

- **Real-time Dashboard**: View live campaign metrics and user interactions
- **Detailed Analytics**: Track open rates, click-through rates, and submission rates
- **Individual User Tracking**: Monitor each target's interaction timeline
- **Department Analytics**: Compare performance across departments

## 🎓 Educational Features

When users interact with phishing emails, they receive:

- **Immediate Feedback**: Explanation of what made the email suspicious
- **Educational Content**: Best practices for identifying phishing attempts
- **Interactive Quiz**: Test their knowledge with security-related questions
- **Additional Resources**: Links to further security training materials

## 🔒 Security Considerations

### Ethical Usage
- **Consent Required**: All campaigns require explicit consent from targets
- **Test Mode**: Always use test accounts before targeting real users
- **Data Privacy**: No credential storage, automatic data retention policies
- **Audit Trails**: Complete logging of all administrative actions

### Technical Security
- **Input Validation**: Comprehensive sanitization of all user inputs
- **SQL Injection Protection**: ORM-based database queries
- **XSS Protection**: Content Security Policy and input sanitization
- **CSRF Protection**: Token-based CSRF protection on all forms
- **Rate Limiting**: Protection against brute force and abuse

## 📈 Analytics & Reporting

### Available Metrics
- **Delivery Rates**: Email delivery success rates
- **Open Rates**: Unique email open tracking
- **Click-Through Rates**: Link click tracking
- **Submission Rates**: Form submission tracking
- **Time-to-Engagement**: Average time to open/click emails
- **Department Comparison**: Performance by department

### Export Options
- **CSV Export**: Campaign result exports with detailed user interaction data
- **Compliance Reports**: Audit and compliance reporting
- **Analytics API**: JSON API for integration with external systems

## 🐳 Docker Deployment

### Production Deployment

1. **Configure production environment**:
   ```bash
   cp .env.example .env.production
   # Edit .env.production with production values
   ```

2. **Deploy with production profile**:
   ```bash
   docker-compose --profile production up -d
   ```

### Scaling

- **Web Workers**: Adjust the `--workers` parameter in Dockerfile
- **Database**: Consider using managed PostgreSQL service for production
- **Redis**: Use external Redis service for better performance
- **Load Balancer**: Place behind nginx or cloud load balancer

## 🧪 Testing

### Manual Testing

1. **Create test accounts** in your email system
2. **Import test targets** via CSV
3. **Create a test campaign** with small target list
4. **Verify email delivery** and tracking functionality
5. **Test educational pages** and user experience

### Automated Testing

```bash
# Run unit tests
python -m pytest tests/

# Run with coverage
python -m pytest --cov=app tests/
```

## 📝 License

This project is intended for authorized security awareness training only. Users must:
- Obtain explicit consent from all campaign targets
- Comply with all applicable laws and regulations
- Use the platform only for ethical security training purposes
- Never attempt malicious activities with this platform

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For issues, questions, or security concerns:
- Create an issue in the repository
- Contact the security team for urgent matters
- Review the comprehensive documentation in the `/docs` directory

## 🎯 Project Structure

```
Ethical_Phishing_Simulation_Platform/
├── app.py                      # Main Flask application
├── config.py                   # Configuration settings
├── requirements.txt            # Python dependencies
├── docker-compose.yml          # Docker orchestration
├── Dockerfile                  # Application container
├── database/                   # Database models and migrations
├── routes/                     # Flask route handlers
├── services/                   # Business logic services
├── utils/                      # Utility functions
├── templates/                  # Jinja2 templates
├── static/                     # Static assets (CSS, JS, images)
└── logs/                       # Application log files
```

---

**⚠️ Important**: This platform is designed exclusively for authorized security awareness training. Always ensure you have proper consent and comply with all applicable laws and organizational policies.