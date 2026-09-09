"""Run the FastAPI backend from the project root: python app.py."""
from pathlib import Path
import sys

if __name__ == '__main__':
    import uvicorn
    backend = Path(__file__).resolve().parent / 'backend'
    sys.path.insert(0, str(backend))
    uvicorn.run('app.main:app', host='127.0.0.1', port=8000, reload=True, reload_dirs=[str(backend / 'app')])
