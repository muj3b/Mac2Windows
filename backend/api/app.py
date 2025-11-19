import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.api.globals import providers, conversion_manager, event_logger
from backend.api.routes import system, settings as settings_routes, community, backups, conversion

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)

app = FastAPI(
  title='Mac ↔ Windows Universal Converter Backend',
  version='0.2.0',
  description='Provides project detection, AI provider discovery, and resource monitoring services.'
)

# CORS
app.add_middleware(
  CORSMiddleware,
  allow_origins=['*'],
  allow_credentials=True,
  allow_methods=['*'],
  allow_headers=['*']
)

# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
  logger.error(f"Global exception: {exc}", exc_info=True)
  return JSONResponse(
    status_code=500,
    content={"message": "Internal Server Error", "detail": str(exc)},
  )

# Include Routers
app.include_router(system.router, tags=['System'])
app.include_router(settings_routes.router, tags=['Settings'])
app.include_router(community.router, tags=['Community'])
app.include_router(backups.router, tags=['Backups'])
app.include_router(conversion.router, tags=['Conversion'])

@app.on_event('startup')
async def startup_event() -> None:
  providers.refresh()
  logger.info('Backend started on %s:%s', settings.backend_host, settings.backend_port)

@app.on_event('shutdown')
async def shutdown_event() -> None:
  await conversion_manager.close()

@app.get('/')
async def root():
  return {"message": "Mac ↔ Windows Universal Converter Backend API v0.2.0"}
