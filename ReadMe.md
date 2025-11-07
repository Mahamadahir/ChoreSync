# ChoreSync

ChoreSync is a coordination platform for households and teams, pairing a FastAPI backend with a Vite/TypeScript frontend to manage shared chores, schedules, and communication.

## Repo Structure
- `backend/` service APIs and domain scaffolding
- `frontend/` SPA controllers and client stubs

Detailed project and implementation trackers live in `ProgressTracker.html`.

## Getting Started

### Backend (FastAPI + Django scaffolding)
1. Create and activate a Python 3.11+ virtual environment.
2. Install dependencies (and test tooling) from the backend project:
   ```powershell
   python -m pip install --upgrade pip
   python -m pip install -e backend[dev]
   ```
3. Run the Django system check and pytest suite to verify the install:
   ```powershell
   python backend/manage.py check
   python -m pytest
   ```
4. Launch the FastAPI app with Uvicorn:
   ```powershell
   uvicorn chore_sync.app:app --app-dir backend --reload
   ```

### Frontend (Vite + TypeScript stubs)
1. Install Node.js 20+ and npm.
2. Install project dependencies from the `frontend/` directory:
   ```powershell
   Push-Location frontend
   npm install
   Pop-Location
   ```
3. Run the Vitest placeholder suite and start the dev server when you are ready to implement UI logic (commands executed from `frontend/`):
   ```powershell
   npm run test
   npm run dev
   ```
