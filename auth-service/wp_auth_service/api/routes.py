"""
API routes for WordPress Auth Service.
"""

import html
import io
import json
import os
import zipfile
from typing import Optional, Dict, Any, List

import httpx
from fastapi import APIRouter, HTTPException, Depends, Request, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field

from wp_auth_lib import (
    generate_auth_url,
    parse_callback_url,
    validate_credentials,
    health_check as wp_health_check,
    get_session,
    save_session,
    delete_session,
    CallbackResult,
    UserProfile,
    ValidationResult,
    AuthError,
    ValidationError,
    NetworkError,
    AuthenticationError,
)
from wp_auth_lib.cache import Cache
from ..config import settings
from ..storage import APIKeyStorage
from ..endpoint_storage import EndpointStorage
from ..activity_storage import ActivityStorage
from ..container import ServiceContainer, CredentialStore
from .middleware import APIKeyAuthMiddleware

SERVICE_VERSION = "1.1.0"

# --- Pydantic Models ---

class AuthURLRequest(BaseModel):
    """Request model for generating auth URL."""
    wp_root_url: str = Field(..., description="WordPress site URL")
    app_name: str = Field(..., description="Application name")
    callback_url: str = Field(..., description="Callback URL")


class AuthURLResponse(BaseModel):
    """Response model for auth URL generation."""
    auth_url: str = Field(..., description="Generated authorization URL")


class CallbackRequest(BaseModel):
    """Request model for parsing callback."""
    callback_url: str = Field(..., description="Callback URL from WordPress")


class CallbackResponse(BaseModel):
    """Response model for callback parsing."""
    user_login: Optional[str] = Field(None, description="WordPress username")
    password: Optional[str] = Field(None, description="Application password")
    success_url: Optional[str] = Field(None, description="Success URL")
    site_url: Optional[str] = Field(None, description="WordPress site URL")
    is_valid: bool = Field(..., description="Whether callback was successfully parsed")


class ValidateRequest(BaseModel):
    """Request model for credential validation."""
    user_login: str = Field(..., description="WordPress username")
    password: str = Field(..., description="Application password")
    wp_root_url: str = Field(..., description="WordPress site URL")


class ValidateResponse(BaseModel):
    """Response model for credential validation."""
    is_valid: bool = Field(..., description="Whether credentials are valid")
    user_id: Optional[int] = Field(None, description="User ID if valid")
    username: Optional[str] = Field(None, description="Username if valid")
    email: Optional[str] = Field(None, description="Email if valid")
    roles: List[str] = Field(default_factory=list, description="User roles if valid")
    error_message: Optional[str] = Field(None, description="Error message if failed")
    error_code: Optional[int] = Field(None, description="HTTP status code if failed")


class ConfigRequest(BaseModel):
    """Request model for setting configuration."""
    wp_root_url: Optional[str] = Field(None, description="WordPress site URL")
    app_name: Optional[str] = Field(None, description="Application name")
    callback_url: Optional[str] = Field(None, description="Callback URL")


class ConfigResponse(BaseModel):
    """Response model for configuration."""
    wp_root_url: str = Field(..., description="WordPress site URL")
    app_name: str = Field(..., description="Application name")
    callback_url: str = Field(..., description="Callback URL")
    is_configured: bool = Field(..., description="Whether configuration is complete")


class EndpointProfileRequest(BaseModel):
    """Request model for creating/updating endpoint profile."""
    name: str = Field(..., description="Descriptive profile name")
    wp_root_url: str = Field(..., description="WordPress site URL")
    app_name: str = Field(..., description="Application name")
    callback_url: str = Field(..., description="Callback URL")
    is_active: bool = Field(default=False, description="Whether endpoint is set active")


class EndpointProfileResponse(BaseModel):
    """Response model for endpoint profile."""
    id: str
    name: str
    wp_root_url: str
    app_name: str
    callback_url: str
    status: str
    is_active: bool
    created_at: str
    updated_at: str


class SessionFetchRequest(BaseModel):
    wp_root_url: str
    user_login: str
    password: str
    app_id: str
    session_key: str


class SessionSaveRequest(BaseModel):
    wp_root_url: str
    user_login: str
    password: str
    app_id: str
    session_key: str
    payload: Dict[str, Any]


# Router instance
router = APIRouter(prefix="/api/v1", tags=["auth"])


# --- Dependency Injection Functions ---

def get_services(request: Request) -> ServiceContainer:
    """Retrieve ServiceContainer from FastAPI app state."""
    services = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Services container not initialized"
        )
    return services


def get_cache(services: ServiceContainer = Depends(get_services)) -> Cache:
    """Dependency to get Cache instance."""
    return services.cache


def get_api_key_storage(services: ServiceContainer = Depends(get_services)) -> APIKeyStorage:
    """Dependency to get APIKeyStorage instance."""
    return services.api_key_storage


def get_endpoint_storage(services: ServiceContainer = Depends(get_services)) -> EndpointStorage:
    """Dependency to get EndpointStorage instance."""
    return services.endpoint_storage


def get_activity_storage(services: ServiceContainer = Depends(get_services)) -> ActivityStorage:
    """Dependency to get ActivityStorage instance."""
    return services.activity_storage


def get_credential_store(services: ServiceContainer = Depends(get_services)) -> CredentialStore:
    """Dependency to get CredentialStore instance."""
    return services.credential_store


async def verify_api_key(request: Request, services: ServiceContainer = Depends(get_services)):
    """Dependency to verify API key. Raises 401/403 if invalid."""
    return await services.api_key_middleware(request)


async def verify_api_key_or_bootstrap(request: Request, services: ServiceContainer = Depends(get_services)):
    """
    Dependency that allows unauthenticated access when no API keys exist yet.
    Once any key is stored, normal key validation is enforced.
    """
    if services.api_key_storage.get_key_count() == 0:
        return None
    return await services.api_key_middleware(request)


# --- Route Handlers ---

@router.post("/auth/url", response_model=AuthURLResponse)
async def generate_auth_url_endpoint(
    request_data: AuthURLRequest,
    services: ServiceContainer = Depends(get_services)
):
    """
    Generate WordPress authorization URL.
    """
    try:
        auth_url = generate_auth_url(
            request_data.wp_root_url,
            request_data.app_name,
            request_data.callback_url
        )
        services.logger.log(
            action="generate_auth_url",
            status="success",
            details={"wp_root_url": request_data.wp_root_url, "app_name": request_data.app_name, "callback_url": request_data.callback_url}
        )
        return AuthURLResponse(auth_url=auth_url)
    except ValidationError as e:
        services.logger.log("generate_auth_url", "failed", details={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        services.logger.log("generate_auth_url", "failed", details={"error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate auth URL: {str(e)}"
        )


@router.post("/auth/callback", response_model=CallbackResponse)
async def parse_callback_endpoint(request_data: CallbackRequest):
    """
    Parse WordPress authorization callback URL.
    """
    try:
        result: CallbackResult = parse_callback_url(request_data.callback_url)
        return CallbackResponse(
            user_login=result.user_login,
            password=result.password,
            success_url=result.success_url,
            site_url=result.site_url,
            is_valid=result.is_valid
        )
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse callback: {str(e)}"
        )


@router.get("/auth/callback-ui", response_class=HTMLResponse)
async def handle_browser_callback(
    request: Request,
    credential_store: CredentialStore = Depends(get_credential_store)
):
    """
    Browser GET callback handler for round-trip proxy/relay flow.
    Extracts credentials from WP authorization redirect query parameters safely.
    """
    full_url = str(request.url)
    try:
        result: CallbackResult = parse_callback_url(full_url)
        if result.is_valid and result.user_login and result.password:
            credential_store.set_credentials(
                user_login=result.user_login,
                password=result.password,
                site_url=result.site_url
            )
            safe_login = html.escape(result.user_login)
            json_login = json.dumps(result.user_login)

            return f"""
            <html>
                <head><title>Authorization Successful</title></head>
                <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background: #0f172a; color: #f8fafc;">
                    <div style="max-width: 440px; margin: 0 auto; padding: 20px; background: #1e293b; border-radius: 12px; border: 1px solid #334155;">
                        <h2 style="color: #22c55e;">✔ Authorization Successful!</h2>
                        <p>Credentials captured for Wordpress User '{safe_login}'</p>
                        <p style="color: #64748b; font-size: 0.875rem;">Your credentials have been securely stored in the dashboard.</p>
                        <div style="margin-top: 24px;">
                            <button onclick="if(window.opener){{try{{window.opener.focus();}}catch(e){{}}}}window.close();" style="background: #2563eb; color: #ffffff; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-weight: 600; font-size: 0.9rem;">Return to Dashboard & Close Tab</button>
                        </div>
                    </div>
                    <script>
                        if (window.opener) {{
                            try {{
                                window.opener.postMessage({{ type: 'WP_AUTH_SUCCESS', user_login: {json_login} }}, '*');
                            }} catch(e) {{}}
                        }}
                    </script>
                </body>
            </html>
            """
    except Exception:
        pass
        
    return """
    <html>
        <head><title>Authorization Failed</title></head>
        <body style="font-family: sans-serif; text-align: center; padding-top: 50px; background: #0f172a; color: #f8fafc;">
            <h2 style="color: #ef4444;">❌ Authorization Failed</h2>
            <p>Could not extract credentials from callback URL parameters.</p>
        </body>
    </html>
    """


@router.get("/auth/latest-credentials")
async def get_latest_captured_credentials(
    credential_store: CredentialStore = Depends(get_credential_store)
):
    """Retrieve the latest captured credentials from thread-safe store."""
    return credential_store.get_credentials()


@router.post("/auth/validate", response_model=ValidateResponse)
async def validate_credentials_endpoint(
    request_data: ValidateRequest,
    cache_instance: Cache = Depends(get_cache),
    services: ServiceContainer = Depends(get_services),
    api_key: str = Depends(verify_api_key)
):
    """
    Validate WordPress credentials.
    """
    try:
        cache_key = f"validate:{request_data.user_login}:{request_data.wp_root_url}"
        cached_result = cache_instance.get(cache_key)
        
        if cached_result:
            return ValidateResponse(**cached_result)
        
        result: ValidationResult = validate_credentials(
            request_data.user_login,
            request_data.password,
            request_data.wp_root_url,
            timeout=30
        )
        
        val_response = ValidateResponse(
            is_valid=result.is_valid,
            user_id=result.user_profile.id if result.user_profile else None,
            username=result.user_profile.username if result.user_profile else None,
            email=result.user_profile.email if result.user_profile else None,
            roles=result.user_profile.roles if result.user_profile else [],
            error_message=result.error_message,
            error_code=result.error_code,
        )

        response_data = val_response.model_dump()
        
        if result.is_valid:
            cache_instance.set(cache_key, response_data, ttl=settings.cache_ttl)
            services.logger.log("validate_credentials", "success", details={
                "user_login": request_data.user_login,
                "wp_root_url": request_data.wp_root_url,
                "user_id": val_response.user_id,
                "roles": val_response.roles
            })
        else:
            services.logger.log("validate_credentials", "failed", details={
                "user_login": request_data.user_login,
                "wp_root_url": request_data.wp_root_url,
                "error": result.error_message
            })
        
        return val_response
        
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except NetworkError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(e)
        )
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to validate credentials: {str(e)}"
        )


@router.post("/config", response_model=ConfigResponse)
async def set_config_endpoint(
    request_data: ConfigRequest,
    api_key: str = Depends(verify_api_key)
):
    """
    Set WordPress site configuration.
    """
    if request_data.wp_root_url is not None:
        settings.wp_root_url = request_data.wp_root_url
    if request_data.app_name is not None:
        settings.app_name = request_data.app_name
    if request_data.callback_url is not None:
        settings.callback_url = request_data.callback_url
    
    return ConfigResponse(
        wp_root_url=settings.wp_root_url or "",
        app_name=settings.app_name or "",
        callback_url=settings.callback_url or "",
        is_configured=settings.is_configured()
    )


@router.get("/config", response_model=ConfigResponse)
async def get_config_endpoint(api_key: str = Depends(verify_api_key)):
    """
    Get current WordPress site configuration.
    """
    return ConfigResponse(
        wp_root_url=settings.wp_root_url or "",
        app_name=settings.app_name or "",
        callback_url=settings.callback_url or "",
        is_configured=settings.is_configured()
    )


@router.post("/api-keys/generate")
async def generate_api_key(
    name: str = "default",
    storage: APIKeyStorage = Depends(get_api_key_storage)
):
    """
    Generate a new API key.
    """
    try:
        api_key = storage.generate_key(name)
        return {"api_key": api_key, "name": name}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate API key: {str(e)}"
        )


@router.get("/api-keys")
async def list_api_keys(storage: APIKeyStorage = Depends(get_api_key_storage)):
    """
    List all API keys.
    """
    try:
        keys = storage.list_keys()
        return {"keys": keys, "count": storage.get_key_count()}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list API keys: {str(e)}"
        )


@router.delete("/api-keys/{api_key}")
async def revoke_api_key(
    api_key: str,
    storage: APIKeyStorage = Depends(get_api_key_storage)
):
    """
    Revoke an API key.
    """
    try:
        success = storage.revoke_key(api_key)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="API key not found"
            )
        return {"message": "API key revoked successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to revoke API key: {str(e)}"
        )


@router.get("/health")
async def health_check_service(wp_root_url: Optional[str] = None):
    """
    Health check endpoint.
    Returns service health and optional WordPress site reachability diagnostic.
    """
    res = {
        "status": "ok",
        "service": "WordPress Auth Service",
        "version": SERVICE_VERSION
    }
    if wp_root_url:
        res["wordpress_diagnostic"] = wp_health_check(wp_root_url)
    return res


@router.post("/session/get")
async def api_get_session(
    req: SessionFetchRequest,
    services: ServiceContainer = Depends(get_services)
):
    """Fetch session state payload from WordPress DB via plugin bridge."""
    try:
        session = get_session(req.wp_root_url, req.user_login, req.password, req.app_id, req.session_key)
        services.logger.log("session_get", "success", details={"app_id": req.app_id, "session_key": req.session_key, "user_login": req.user_login})
        return {
            "success": True,
            "session": {
                "id": session.id,
                "user_id": session.user_id,
                "app_id": session.app_id,
                "session_key": session.session_key,
                "payload": session.payload,
                "created_at": session.created_at,
                "updated_at": session.updated_at
            }
        }
    except AuthError as e:
        services.logger.log("session_get", "failed", details={"error": str(e), "app_id": req.app_id, "session_key": req.session_key})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        services.logger.log("session_get", "failed", details={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/session/save")
async def api_save_session(
    req: SessionSaveRequest,
    services: ServiceContainer = Depends(get_services)
):
    """Save or update session state payload in WordPress DB via plugin bridge."""
    try:
        res = save_session(req.wp_root_url, req.user_login, req.password, req.app_id, req.session_key, req.payload)
        services.logger.log("session_save", "success", details={"app_id": req.app_id, "session_key": req.session_key, "user_login": req.user_login, "payload": req.payload})
        return res
    except AuthError as e:
        services.logger.log("session_save", "failed", details={"error": str(e), "app_id": req.app_id, "session_key": req.session_key})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        services.logger.log("session_save", "failed", details={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post("/session/delete")
async def api_delete_session(
    req: SessionFetchRequest,
    services: ServiceContainer = Depends(get_services)
):
    """Delete session state payload from WordPress DB via plugin bridge."""
    try:
        res = delete_session(req.wp_root_url, req.user_login, req.password, req.app_id, req.session_key)
        services.logger.log("session_delete", "success", details={"app_id": req.app_id, "session_key": req.session_key, "user_login": req.user_login})
        return res
    except AuthError as e:
        services.logger.log("session_delete", "failed", details={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        services.logger.log("session_delete", "failed", details={"error": str(e)})
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# --- Endpoint Profile Management Routes ---

@router.get("/endpoints", response_model=List[EndpointProfileResponse])
async def list_endpoints(
    ep_storage: EndpointStorage = Depends(get_endpoint_storage),
    api_key: str = Depends(verify_api_key_or_bootstrap)
):
    """List all saved WordPress endpoint profiles."""
    return [EndpointProfileResponse(**p) for p in ep_storage.list_profiles()]


@router.post("/endpoints", response_model=EndpointProfileResponse)
async def create_endpoint_profile(
    data: EndpointProfileRequest,
    ep_storage: EndpointStorage = Depends(get_endpoint_storage),
    api_key: str = Depends(verify_api_key_or_bootstrap)
):
    """Create a new WordPress endpoint profile (status defaults to unconfirmed)."""
    profile = ep_storage.create_profile(
        name=data.name,
        wp_root_url=data.wp_root_url,
        app_name=data.app_name,
        callback_url=data.callback_url,
        is_active=data.is_active
    )
    if profile.get("is_active"):
        settings.wp_root_url = profile["wp_root_url"]
        settings.app_name = profile["app_name"]
        settings.callback_url = profile["callback_url"]
    return EndpointProfileResponse(**profile)


@router.put("/endpoints/{endpoint_id}", response_model=EndpointProfileResponse)
async def update_endpoint_profile(
    endpoint_id: str,
    data: EndpointProfileRequest,
    ep_storage: EndpointStorage = Depends(get_endpoint_storage),
    api_key: str = Depends(verify_api_key)
):
    """Update an existing WordPress endpoint profile."""
    updated = ep_storage.update_profile(
        endpoint_id=endpoint_id,
        name=data.name,
        wp_root_url=data.wp_root_url,
        app_name=data.app_name,
        callback_url=data.callback_url,
        status="unconfirmed"
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint profile not found")
        
    if data.is_active:
        updated = ep_storage.set_active(endpoint_id)
        settings.wp_root_url = updated["wp_root_url"]
        settings.app_name = updated["app_name"]
        settings.callback_url = updated["callback_url"]
        
    return EndpointProfileResponse(**updated)


@router.post("/endpoints/{endpoint_id}/clone", response_model=EndpointProfileResponse)
async def clone_endpoint_profile(
    endpoint_id: str,
    ep_storage: EndpointStorage = Depends(get_endpoint_storage),
    api_key: str = Depends(verify_api_key)
):
    """Clone an existing endpoint profile into a new profile."""
    cloned = ep_storage.clone_profile(endpoint_id)
    if not cloned:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint profile not found")
    return EndpointProfileResponse(**cloned)


@router.delete("/endpoints/{endpoint_id}")
async def delete_endpoint_profile(
    endpoint_id: str,
    ep_storage: EndpointStorage = Depends(get_endpoint_storage),
    api_key: str = Depends(verify_api_key)
):
    """Delete an endpoint profile."""
    success = ep_storage.delete_profile(endpoint_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint profile not found")
    return {"message": "Endpoint profile deleted successfully"}


@router.post("/endpoints/{endpoint_id}/active", response_model=EndpointProfileResponse)
async def set_active_endpoint(
    endpoint_id: str,
    ep_storage: EndpointStorage = Depends(get_endpoint_storage),
    api_key: str = Depends(verify_api_key)
):
    """Set an endpoint profile as the active endpoint."""
    activated = ep_storage.set_active(endpoint_id)
    if not activated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint profile not found")
        
    settings.wp_root_url = activated["wp_root_url"]
    settings.app_name = activated["app_name"]
    settings.callback_url = activated["callback_url"]
    return EndpointProfileResponse(**activated)


@router.post("/endpoints/{endpoint_id}/confirm", response_model=EndpointProfileResponse)
async def confirm_endpoint_reachability(
    endpoint_id: str,
    ep_storage: EndpointStorage = Depends(get_endpoint_storage),
    api_key: str = Depends(verify_api_key)
):
    """Perform a reachability check on WordPress site URL and update status."""
    profile = ep_storage.get_profile(endpoint_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint profile not found")

    wp_url = profile["wp_root_url"].rstrip("/")
    target_url = f"{wp_url}/wp-json/"
    
    is_reachable = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            res = await client.get(target_url)
            if res.status_code < 500:
                is_reachable = True
    except Exception:
        is_reachable = False

    new_status = "confirmed" if is_reachable else "unconfirmed"
    updated = ep_storage.update_profile(endpoint_id, status=new_status)
    return EndpointProfileResponse(**updated)


@router.post("/endpoints/{endpoint_id}/plugin-check")
async def check_plugin_liveness(
    endpoint_id: str,
    ep_storage: EndpointStorage = Depends(get_endpoint_storage)
):
    """Check if the Belchamber Auth Bridge plugin is active and installed on the endpoint site."""
    profile = ep_storage.get_profile(endpoint_id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Endpoint profile not found")

    wp_url = profile["wp_root_url"].rstrip("/")
    parent_url = "/".join(wp_url.split("/")[:-1]) if "/cms" in wp_url or wp_url.count("/") > 3 else wp_url

    candidate_urls = [
        f"{wp_url}/?rest_route=/auth-bridge/v1/health",
        f"{wp_url}/index.php?rest_route=/auth-bridge/v1/health",
        f"{wp_url}/wp-json/auth-bridge/v1/health",
        f"{parent_url}/wp-json/auth-bridge/v1/health" if parent_url != wp_url else "",
        f"{wp_url}/?rest_route=/",
        f"{wp_url}/wp-json/"
    ]
    candidate_urls = [u for u in candidate_urls if u]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) WP-Auth-Service/1.1'}

    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=True, headers=headers) as client:
            last_status = 0
            for target_url in candidate_urls:
                try:
                    res = await client.get(target_url)
                    last_status = res.status_code
                    if res.status_code == 200:
                        try:
                            data = res.json()
                            if isinstance(data, dict):
                                if data.get("plugin") == "belchamber-auth-bridge":
                                    return {"is_plugin_active": True, "details": data, "active_url": target_url}
                                if "namespaces" in data and "auth-bridge/v1" in data.get("namespaces", []):
                                    return {"is_plugin_active": True, "details": {"namespaces": data["namespaces"], "version": "1.1.0 (via REST index)"}, "active_url": target_url}
                        except Exception:
                            pass
                except Exception:
                    continue

            return {
                "is_plugin_active": False,
                "status_code": last_status,
                "tried_urls": candidate_urls
            }
    except Exception as e:
        return {"is_plugin_active": False, "error": str(e)}


@router.get("/plugin/download")
async def download_plugin_zip():
    """Dynamically build and return the latest belchamber-auth-bridge.zip file."""
    plugin_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "belchamber-auth-bridge")
    if not os.path.exists(plugin_dir):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plugin directory not found")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(plugin_dir):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, os.path.dirname(plugin_dir))
                zf.write(full_path, rel_path)

    zip_buffer.seek(0)
    return Response(
        content=zip_buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=belchamber-auth-bridge.zip"}
    )


# --- Activity Log Routes ---

@router.get("/activity")
async def list_activity_logs(
    limit: int = 50,
    filter_type: str = "all",
    act_storage: ActivityStorage = Depends(get_activity_storage),
    api_key: str = Depends(verify_api_key_or_bootstrap)
):
    """Retrieve list of persistent service activity logs with optional filtering."""
    return act_storage.list_activities(limit=limit, filter_type=filter_type)


@router.delete("/activity")
async def delete_activity_logs(
    test_only: bool = False,
    act_storage: ActivityStorage = Depends(get_activity_storage),
    api_key: str = Depends(verify_api_key_or_bootstrap)
):
    """Delete activity logs (optionally delete test/probe logs only)."""
    deleted_count = act_storage.clear_activities(test_only=test_only)
    return {
        "success": True,
        "deleted_count": deleted_count,
        "test_only": test_only
    }


@router.get("/activity/{log_id}")
async def get_activity_log_detail(
    log_id: str,
    act_storage: ActivityStorage = Depends(get_activity_storage),
    api_key: str = Depends(verify_api_key_or_bootstrap)
):
    """Fetch full detail of a specific activity log entry."""
    entry = act_storage.get_activity_detail(log_id)
    if not entry:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Activity log entry not found")
    return entry
