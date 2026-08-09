"""
Main FastAPI application for WordPress Auth Service.
"""

import html
import json
import os
from fastapi import FastAPI, HTTPException, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from wp_auth_lib.cache import Cache
from .config import settings
from .storage import APIKeyStorage
from .endpoint_storage import EndpointStorage
from .activity_storage import ActivityStorage
from .api.middleware import APIKeyAuthMiddleware
from .container import ServiceContainer
from .api import router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.
    
    Returns:
        Configured FastAPI application instance
    """
    app = FastAPI(
        title="WordPress Auth Service",
        description="Standalone authentication service for WordPress Application Passwords flow",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Initialize cache
    if settings.redis_url:
        cache = Cache.create_redis(settings.redis_url)
    else:
        cache = Cache()
    
    # Initialize storage instances
    storage_file = os.path.join(os.path.dirname(__file__), "api_keys.json")
    api_key_storage = APIKeyStorage(storage_file)

    endpoint_file = os.path.join(os.path.dirname(__file__), "endpoints.json")
    endpoint_storage = EndpointStorage(endpoint_file)

    activity_file = os.path.join(os.path.dirname(__file__), "activity_logs.json")
    activity_storage = ActivityStorage(activity_file)
    
    # Initialize API key middleware
    api_key_middleware = APIKeyAuthMiddleware(api_key_storage)
    
    # Encapsulate all app services in ServiceContainer attached to app.state
    app.state.services = ServiceContainer(
        cache=cache,
        api_key_storage=api_key_storage,
        api_key_middleware=api_key_middleware,
        endpoint_storage=endpoint_storage,
        activity_storage=activity_storage,
    )
    
    # Include API router
    app.include_router(router)
    
    # Root-level /auth callback handler for WordPress Application Password flow.
    @app.get("/auth", response_class=HTMLResponse)
    async def auth_callback_handler(request: FastAPIRequest):
        """
        Capture WordPress Application Password callback credentials.
        
        WordPress redirects here after user approves the application.
        Query params: user_login, password, site_url
        """
        user_login = request.query_params.get("user_login")
        password = request.query_params.get("password")
        site_url = request.query_params.get("site_url")

        if user_login and password:
            services: ServiceContainer = request.app.state.services
            services.credential_store.set_credentials(user_login, password, site_url)

            safe_user_login = html.escape(user_login)
            json_user_login = json.dumps(user_login)

            return HTMLResponse(content=f"""
            <html>
                <head><title>Authorization Successful</title></head>
                <body style="font-family: system-ui, sans-serif; text-align: center; padding-top: 60px; background: #0f172a; color: #f8fafc;">
                    <div style="max-width: 440px; margin: 0 auto; padding: 20px; background: #1e293b; border-radius: 12px; border: 1px solid #334155;">
                        <h2 style="color: #22c55e; font-size: 1.5rem; margin-top: 0;">&#10004; Authorization Successful!</h2>
                        <p style="color: #94a3b8;">Credentials captured for Wordpress User '<strong style="color: #f8fafc;">{safe_user_login}</strong>'</p>
                        <p style="color: #64748b; font-size: 0.875rem;">Your credentials have been securely stored in the dashboard.</p>
                        <div style="margin-top: 24px;">
                            <button onclick="if(window.opener){{try{{window.opener.focus();}}catch(e){{}}}}window.close();" style="background: #2563eb; color: #ffffff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.9rem;">Return to Dashboard & Close Tab</button>
                        </div>
                    </div>
                    <script>
                        if (window.opener) {{
                            try {{
                                window.opener.postMessage({{ type: 'WP_AUTH_SUCCESS', user_login: {json_user_login} }}, '*');
                            }} catch(e) {{}}
                        }}
                    </script>
                </body>
            </html>
            """)

        return HTMLResponse(status_code=400, content="""
        <html>
            <head><title>Authorization Failed</title></head>
            <body style="font-family: system-ui, sans-serif; text-align: center; padding-top: 60px; background: #0f172a; color: #f8fafc;">
                <h2 style="color: #ef4444;">&#10060; Authorization Failed</h2>
                <p style="color: #94a3b8;">Missing credentials in callback URL parameters.</p>
            </body>
        </html>
        """)

    # Serve static files (frontend)
    static_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # SPA clean route fallback (serves index.html for /onboarding, /endpoints, /api-keys, /activity, /test)
    @app.get("/{full_path:path}", response_class=HTMLResponse)
    async def serve_spa_frontend(request: FastAPIRequest, full_path: str):
        # Ignore API, health, auth, docs endpoints
        if full_path.startswith("api/") or full_path in ["health", "auth", "docs", "redoc"]:
            raise HTTPException(status_code=404, detail="Not Found")
        
        # Check static file match first (e.g. /js/app.js)
        target_file = os.path.join(static_dir, full_path)
        if os.path.isfile(target_file):
            return FileResponse(target_file)

        index_file = os.path.join(static_dir, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "r", encoding="utf-8") as f:
                return HTMLResponse(content=f.read())
        raise HTTPException(status_code=404, detail="Frontend index.html not found")

    # Health check endpoint at root
    @app.get("/health")
    async def health():
        return {
            "status": "healthy",
            "service": "WordPress Auth Service",
            "version": "1.0.0",
            "cache_type": "redis" if settings.redis_url else "in-memory",
        }
    
    return app



# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn
    import sys

    port = settings.service_port
    if len(sys.argv) > 1 and sys.argv[1].isdigit():
        port = int(sys.argv[1])
    elif os.getenv("PORT") and os.getenv("PORT").isdigit():
        port = int(os.getenv("PORT"))

    uvicorn.run(
        "wp_auth_service.main:app",
        host=settings.service_host,
        port=port,
        reload=True,
        log_level=settings.log_level.lower(),
    )
