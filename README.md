# DD Instrumenter Agent

A FastAPI-based server for the DD Instrumenter Agent.

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Unix/macOS
# or
.\venv\Scripts\activate  # On Windows
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

To start the server, run:
```bash
python main.py
```

The server will start on `http://localhost:8000`

## Available Endpoints

- `GET /`: Root endpoint that returns a welcome message
- `GET /health`: Health check endpoint that returns the server status

## API Documentation

Once the server is running, you can access:
- Swagger UI documentation at `http://localhost:8000/docs`
- ReDoc documentation at `http://localhost:8000/redoc` 