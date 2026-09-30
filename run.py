import sys
from pathlib import Path

# Ensure project root is on sys.path (fixes ModuleNotFoundError: No module named 'app')
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
