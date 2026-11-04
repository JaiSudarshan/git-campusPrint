# CampusPrint

Campus Print is a Flask-based web app for students to upload documents and get their copies directly delivered to their classrooms without needing to wait in queue at the Xerox shop. The app records each print order, validates file types and page/copy limits, stores files in Supabase, and lets a runner review and take print.

## Features

- Upload PDF, PNG, JPG, and JPEG files
- Choose black-and-white or color printing
- Set number of copies per file
- View a confirmation page after placing an order
- Runner dashboard for tracking and updating print jobs
- Local SQLite development mode or Postgres/Supabase production-ready storage

## Project structure

- `main.py` — main Flask application and routes
- `models.py` — database models for orders and order items
- `media.py` — file inspection and thumbnail generation
- `storage.py` — storage backend for local uploads or Supabase
- `templates/` — HTML pages for the student and runner views
- `static/` — frontend assets and styles
- `render.yaml` and `Procfile` — deployment configuration for hosting

## Local setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate   # Windows: .venv\Scripts\activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example environment file and configure it:

   ```bash
   cp .env.example .env
   ```

   Edit `.env` and set values such as `SECRET_KEY` and `RUNNER_PASSWORD`. For local development, you can leave the database variables blank to use the default SQLite database.

4. Run the app:

   ```bash
   python main.py
   ```

   The app will start on `http://localhost:5001` by default.

## Environment variables

- `SECRET_KEY` — secret key for Flask sessions
- `RUNNER_PASSWORD` — password for the runner dashboard
- `DATABASE_URL` — optional Postgres connection string
- `SUPABASE_URL` — optional Supabase project URL
- `SUPABASE_SERVICE_KEY` — optional Supabase service key
- `SUPABASE_BUCKET` — storage bucket name, defaults to `uploads`

## Deployment

This repository includes deployment config for Render (`render.yaml`) and a `Procfile`, making it suitable for hosting on cloud platforms that run a Flask app.

## License

This project is provided as-is for educational and campus-use purposes.
