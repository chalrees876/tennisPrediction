## Public Database Access

This project now has a publicly accessible read-only database for demo purposes.

### Setup

1. Clone the repository
```bash
git clone https://github.com/chalrees876/tennisPrediction.git
cd tennisPrediction
```

2. Create and activate virtual environment
```bash
python -m venv venv
source venv/bin/activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Set up environment variables
```bash
cp .env.example .env
```

5. Add the database URL to `.env`:
```
DATABASE_URL = 'postgresql://readonly_user:limited_password@ep-proud-tooth-ahsdsq47-pooler.c-3.us-east-1.aws.neon.tech/neondb?sslmode=require&channel_binding=require'
SECRET_KEY = ';alksjdf;alksdjf;asdkljf'
```

6. Run the application
```bash
python manage.py runserver
```

### Database Access

The public `DATABASE_URL` provided above is **read-only**. You can view data but cannot modify it.
```

**Create `.env.example` in your original repo:**
```
DATABASE_URL=postgresql://readonly_user:limited_password@your-neon-host/dbname