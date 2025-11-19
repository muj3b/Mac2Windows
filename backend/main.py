import argparse
import uvicorn
from backend.config import settings

def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description='Backend service for the converter.')
  parser.add_argument('--host', default=settings.backend_host, help='Host interface to bind.')
  parser.add_argument('--port', default=settings.backend_port, type=int, help='Port to serve on.')
  parser.add_argument('--reload', action='store_true', help='Enable autoreload (development only).')
  parser.add_argument('--log-level', default=settings.log_level, help='Uvicorn log level.')
  return parser.parse_args()

def main() -> None:
  args = parse_args()
  uvicorn.run(
    'backend.api.app:app',
    host=args.host,
    port=args.port,
    log_level=args.log_level,
    reload=args.reload
  )

if __name__ == '__main__':
  main()
