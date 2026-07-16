"""WhatsApp QR code and status endpoints with SSE support."""

import asyncio
import hashlib
import logging
import os
import tempfile
import time
from collections import defaultdict
from collections.abc import AsyncIterable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import BaseModel

from whaagent.config import WhatsAppTenantConfig, get_config
from whaagent.logging_config import TenantLogAdapter
from whaagent.registry import AgentRegistry
from whaagent.services.audio_transcriber import AudioTranscriber
from whaagent.services.audio_transcription_cache import AudioTranscriptionCache
from whaagent.services.wake_word import check_wake_word
from whaagent.storage.tenant_manager import TenantManager
from whaagent.whatsapp import WhatsAppRegistry

router = APIRouter()

# Global WhatsApp registry instance
_whatsapp_registry: WhatsAppRegistry | None = None


def get_whatsapp_registry() -> WhatsAppRegistry:
    """Get or initialize the WhatsApp registry from config."""
    global _whatsapp_registry
    if _whatsapp_registry is None:
        config = get_config()
        _whatsapp_registry = WhatsAppRegistry(config.whatsapp.tenants)
    return _whatsapp_registry


# Global tenant manager for persistent memory
_tenant_manager: TenantManager | None = None


def _get_tenant_manager() -> TenantManager:
    """Get or create the TenantManager for persistent agent memory."""
    global _tenant_manager
    if _tenant_manager is None:
        config = get_config()
        base = config.storage.base_path
        _tenant_manager = TenantManager(base_path=base)
    return _tenant_manager


def _get_tenant_config(tenant_id: str) -> WhatsAppTenantConfig | None:
    """Return the tenant config for *tenant_id*, or None if not found."""
    for tenant in get_config().whatsapp.tenants:
        if tenant.id == tenant_id:
            return tenant
    return None


def _unwrap_exception_group(exc: BaseException, depth: int = 0) -> str:
    """Recursively unwrap ExceptionGroups into a readable string."""
    if hasattr(exc, "exceptions") and exc.exceptions:
        inner = [_unwrap_exception_group(sub, depth + 1) for sub in exc.exceptions]
        prefix = "  " * depth
        return f"{prefix}{type(exc).__name__}:\n" + "\n".join(inner)
    return f"{'  ' * depth}{type(exc).__name__}: {exc}"


async def _run_agent(
    request: Request,
    tenant_id: str,
    agent_name: str,
    message: str,
    phone: str,
    tenant_logger: TenantLogAdapter,
) -> str:
    """Run *agent_name* for a tenant and return the response string.

    Handles pool retrieval, stale-connection retry, and the 300s timeout.
    Raises asyncio.TimeoutError or any other exception to the caller.
    """
    config = get_config()
    allowed_mcp = AgentRegistry.get_mcp_servers(agent_name)
    tool_categories = AgentRegistry.get_tool_categories(agent_name)
    thread_id = f"whatsapp:{tenant_id}:{phone}"

    pool = request.app.state.agent_pool
    agent_cls = AgentRegistry.get(agent_name)

    if not agent_cls:
        tenant_logger.error("Agent '%s' not found for tenant %s", agent_name, tenant_id)
        raise HTTPException(status_code=500, detail="Agent not found")

    tenant_db = _get_tenant_manager().get_database(tenant_id)

    async def _send_progress(msg: str) -> None:
        tenant_logger.debug("Progress: %s", msg)

    agent_kwargs: dict[str, Any] = dict(
        _agent_name=agent_name,
        tool_categories=tool_categories,
        model_name=config.llm.model,
        temperature=config.llm.temperature,
        thread_id=thread_id,
        db_path=str(tenant_db._db_path),
        progress_callback=_send_progress,
    )
    if allowed_mcp:
        agent_kwargs["mcp_server_names"] = allowed_mcp

    agent = await pool.get_or_create(
        tenant_id=tenant_id,
        agent_name=agent_name,
        agent_cls=agent_cls,
        agent_kwargs=agent_kwargs,
    )

    try:
        result = await asyncio.wait_for(
            agent.run(message, config={"configurable": {"thread_id": thread_id}}),
            timeout=300,
        )
    except (ValueError, ConnectionError, OSError) as e:
        if "no active connection" not in str(e).lower() and "connection" not in str(e).lower():
            raise
        tenant_logger.warning("Stale connection for %s agent, evicting and retrying: %s", agent_name, e)
        await pool.evict(tenant_id, agent_name)
        agent = await pool.get_or_create(
            tenant_id=tenant_id,
            agent_name=agent_name,
            agent_cls=agent_cls,
            agent_kwargs=agent_kwargs,
        )
        result = await asyncio.wait_for(
            agent.run(message, config={"configurable": {"thread_id": thread_id}}),
            timeout=300,
        )

    return str(result) if result is not None else ""


# In-memory storage for QR codes and connection status
# In production, this should be replaced with Redis or similar
qr_codes: dict[str, dict[str, str]] = defaultdict(dict)
connection_status: dict[str, dict[str, str]] = defaultdict(dict)
# Event queues for SSE clients
sse_queues: dict[str, list[asyncio.Queue]] = defaultdict(list)
# Timestamps for cleanup
_last_activity: dict[str, float] = {}
_MAX_INACTIVE_TENANTS = 100  # Maximum number of inactive tenant entries to keep


def _cleanup_stale_entries() -> None:
    """Remove entries for inactive tenants to prevent unbounded memory growth."""
    now = time.time()
    if len(_last_activity) <= _MAX_INACTIVE_TENANTS:
        return

    # Remove entries older than 1 hour
    cutoff = now - 3600
    stale = [tid for tid, ts in _last_activity.items() if ts < cutoff]
    for tid in stale:
        qr_codes.pop(tid, None)
        connection_status.pop(tid, None)
        sse_queues.pop(tid, None)
        del _last_activity[tid]


class QRCodeRequest(BaseModel):
    """Request model for QR code submission."""

    image: str


class StatusRequest(BaseModel):
    """Request model for connection status updates."""

    status: str
    phone: str | None = None


@router.get("/qr/{tenant_id}/page", response_class=HTMLResponse)
async def qr_page(tenant_id: str) -> str:
    """Return a simple HTML page for displaying QR codes.

    Args:
        tenant_id: The tenant ID.

    Returns:
        HTML page with QR code display.
    """
    # Use a multiline string with line breaks to avoid E501
    html_parts = [
        "<!DOCTYPE html>",
        "<html>",
        "<head>",
        f"    <title>WhatsApp QR Code - {tenant_id}</title>",
        "    <style>",
        "        body {",
        "            font-family: Arial, sans-serif;",
        "            display: flex;",
        "            flex-direction: column;",
        "            align-items: center;",
        "            justify-content: center;",
        "            min-height: 100vh;",
        "            margin: 0;",
        "            background-color: #f5f5f5;",
        "        }",
        "        .container {",
        "            background: white;",
        "            padding: 2rem;",
        "            border-radius: 8px;",
        "            box-shadow: 0 2px 10px rgba(0,0,0,0.1);",
        "            text-align: center;",
        "        }",
        "        h1 {",
        "            color: #333;",
        "        }",
        "        #qr-code {",
        "            margin: 2rem 0;",
        "        }",
        "        #qr-code img {",
        "            max-width: 300px;",
        "            border: 2px solid #ddd;",
        "            border-radius: 4px;",
        "        }",
        "        #status {",
        "            margin-top: 1rem;",
        "            padding: 1rem;",
        "            border-radius: 4px;",
        "            font-weight: bold;",
        "        }",
        "        .connected {",
        "            background-color: #d4edda;",
        "            color: #155724;",
        "        }",
        "        .disconnected {",
        "            background-color: #f8d7da;",
        "            color: #721c24;",
        "        }",
        "        .loading {",
        "            background-color: #fff3cd;",
        "            color: #856404;",
        "        }",
        "    </style>",
        "</head>",
        "<body>",
        '    <div class="container">',
        f"        <h1>WhatsApp QR Code - {tenant_id}</h1>",
        '        <div id="status" class="loading">Waiting for QR code...</div>',
        '        <div id="qr-code"></div>',
        "        <p>Scan this QR code with WhatsApp to connect</p>",
        "    </div>",
        "    <script>",
        f"        const eventSource = new EventSource('/api/v1/whatsapp/qr/{tenant_id}');",
        "        eventSource.addEventListener('qr_code', function(e) {",
        "            const data = JSON.parse(e.data);",
        "            const img = document.createElement('img');",
        "            img.src = 'data:image/png;base64,' + data.image;",
        "            img.alt = 'QR Code';",
        "            document.getElementById('qr-code').innerHTML = '';",
        "            document.getElementById('qr-code').appendChild(img);",
        "            document.getElementById('status').className = 'loading';",
        "            document.getElementById('status').textContent = 'QR Code received - scan now!';",
        "        });",
        "        eventSource.addEventListener('connected', function(e) {",
        "            const data = JSON.parse(e.data);",
        "            document.getElementById('qr-code').innerHTML = '';",
        "            document.getElementById('status').className = 'connected';",
        "            document.getElementById('status').textContent = 'Connected as ' + data.phone;",
        "            eventSource.close();",
        "        });",
        "        eventSource.addEventListener('disconnected', function(e) {",
        "            document.getElementById('status').className = 'disconnected';",
        "            document.getElementById('status').textContent = 'Disconnected from WhatsApp';",
        "        });",
        "        eventSource.onerror = function(e) {",
        "            console.error('EventSource error:', e);",
        "            document.getElementById('status').className = 'disconnected';",
        "            document.getElementById('status').textContent = 'Connection error - please refresh';",
        "        };",
        "    </script>",
        "</body>",
        "</html>",
    ]
    return "\n".join(html_parts)


@router.get("/qr/{tenant_id}", response_class=EventSourceResponse)
async def qr_stream(tenant_id: str, request: Request) -> AsyncIterable[ServerSentEvent]:
    """SSE endpoint for streaming QR codes and connection status.

    Uses FastAPI's native EventSourceResponse with ServerSentEvent objects.
    Built-in keep-alive pings every 15 seconds, proper Cache-Control headers,
    and graceful cancellation handling.

    Args:
        tenant_id: The tenant ID.
        request: The FastAPI request.

    Returns:
        AsyncIterable of ServerSentEvent objects.
    """
    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
    sse_queues[tenant_id].append(queue)

    try:
        # Send current QR code if available
        if tenant_id in qr_codes and "image" in qr_codes[tenant_id]:
            yield ServerSentEvent(
                data={"image": qr_codes[tenant_id]["image"]},
                event="qr_code",
            )

        # Send current status if available
        if tenant_id in connection_status and connection_status[tenant_id].get("status") == "connected":
            phone = connection_status[tenant_id].get("phone", "")
            yield ServerSentEvent(data={"phone": phone}, event="connected")

        # Keep connection alive and send new events
        while not await request.is_disconnected():
            try:
                event = await asyncio.wait_for(queue.get(), timeout=15.0)
                event_type = event.get("type", "message")
                event_data = event.get("data", {})
                yield ServerSentEvent(data=event_data, event=event_type)
            except asyncio.TimeoutError:
                # Native EventSourceResponse sends keep-alive pings automatically
                # but we yield a comment to keep the connection active
                yield ServerSentEvent(comment="keepalive")

    except asyncio.CancelledError:
        return
    finally:
        if queue in sse_queues.get(tenant_id, []):
            sse_queues[tenant_id].remove(queue)


@router.post("/qr/{tenant_id}")
async def receive_qr_code(tenant_id: str, request: QRCodeRequest) -> dict[str, str]:
    """Receive QR code from Go gateway and cache it.

    Args:
        tenant_id: The tenant ID.
        request: The QR code request.

    Returns:
        Success message.
    """
    qr_codes[tenant_id]["image"] = request.image

    # Notify all SSE clients
    for queue in sse_queues[tenant_id]:
        await queue.put({"type": "qr_code", "data": {"image": request.image}})

    return {"status": "ok", "message": "QR code received"}


@router.post("/status/{tenant_id}")
async def receive_status(tenant_id: str, request: StatusRequest) -> dict[str, str]:
    """Receive connection status from Go gateway.

    Args:
        tenant_id: The tenant ID.
        request: The status request.

    Returns:
        Success message.
    """
    connection_status[tenant_id]["status"] = request.status
    if request.phone:
        connection_status[tenant_id]["phone"] = request.phone

    # Notify all SSE clients
    if request.status == "connected" and request.phone:
        for queue in sse_queues[tenant_id]:
            await queue.put({"type": "connected", "data": {"phone": request.phone}})
    elif request.status == "disconnected":
        for queue in sse_queues[tenant_id]:
            await queue.put({"type": "disconnected", "data": {}})

    # Track activity and cleanup
    _last_activity[tenant_id] = time.time()
    _cleanup_stale_entries()

    return {"status": "ok", "message": "Status updated"}


# Webhook router for channels endpoints (different prefix from whatsapp router)
channels_router = APIRouter()


@channels_router.post("/whatsapp/message")
async def whatsapp_webhook(
    request: Request, registry: WhatsAppRegistry = Depends(get_whatsapp_registry)
) -> dict[str, str]:
    """Receive WhatsApp message from Go gateway and route to tenant's agent.

    Args:
        request: The FastAPI request containing message data.
        registry: WhatsApp registry instance.

    Returns:
        Agent response with tenant_id.

    Raises:
        HTTPException: If authentication fails or tenant not found.
    """
    logger = logging.getLogger(__name__)

    # Check API key against keys (not values) of api_keys dict
    api_key = request.headers.get("X-API-Key")
    config = get_config()

    if not api_key or api_key not in config.auth.api_keys:
        logger.warning("Invalid API key attempted for WhatsApp webhook")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Parse request body
    try:
        body = await request.json()
        phone = body.get("from")
        message = body.get("message")
        tenant_id = body.get("tenant_id")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid request body")

    if not phone or not message:
        raise HTTPException(status_code=400, detail="Missing 'from' or 'message' in request body")

    # Look up tenant by phone number
    resolved_tenant_id = registry.lookup_by_phone(phone)

    # If tenant_id provided in body, use it for validation
    if tenant_id:
        if resolved_tenant_id != tenant_id:
            logger.error("Phone number maps to different tenant")
            raise HTTPException(
                status_code=400,
                detail="Phone number does not match provided tenant_id",
            )
    else:
        tenant_id = resolved_tenant_id

    if not tenant_id:
        logger.error("No tenant found for phone number")
        raise HTTPException(status_code=404, detail="No tenant found for phone number")

    # Get logger with tenant context
    tenant_logger = TenantLogAdapter(logger, tenant_id)
    tenant_logger.info("Received WhatsApp message")

    tenant_config = _get_tenant_config(tenant_id)
    if not tenant_config:
        tenant_logger.error("Tenant configuration not found: %s", tenant_id)
        raise HTTPException(status_code=404, detail="Tenant configuration not found")

    if tenant_config.allowed_contacts and phone not in tenant_config.allowed_contacts:
        tenant_logger.warning("Phone number not in allowed contacts for tenant %s", tenant_id)
        raise HTTPException(status_code=403, detail="Phone number not in allowed contacts")

    thread_id = f"whatsapp:{tenant_id}:{phone}"
    tenant_logger.info("Using persistent memory for thread: %s", thread_id)

    try:
        result = await _run_agent(request, tenant_id, tenant_config.default_agent, message, phone, tenant_logger)
        tenant_logger.info("Successfully processed WhatsApp message for tenant %s", tenant_id)
        return {"response": result, "tenant_id": tenant_id}
    except asyncio.TimeoutError:
        tenant_logger.error("Agent timed out after 300s for tenant %s", tenant_id)
        raise HTTPException(status_code=504, detail="Agent response timed out. Please try again.")
    except Exception as e:
        detail = _unwrap_exception_group(e)
        tenant_logger.error("Failed to process WhatsApp message for tenant %s:\n%s", tenant_id, detail)
        raise HTTPException(status_code=500, detail="Internal error processing message")


@channels_router.post("/whatsapp/audio")
async def whatsapp_audio_webhook(
    request: Request, registry: WhatsAppRegistry = Depends(get_whatsapp_registry)
) -> dict[str, str]:
    """Receive audio message from Go gateway, transcribe and process with agent.

    Args:
        request: The FastAPI request containing audio data as multipart form.
        registry: WhatsApp registry instance.

    Returns:
        Agent response with tenant_id.

    Raises:
        HTTPException: If authentication fails or processing fails.
    """
    logger = logging.getLogger(__name__)

    # Check API key
    api_key = request.headers.get("X-API-Key")
    config = get_config()
    if not api_key or api_key not in config.auth.api_keys:
        logger.warning("Invalid API key attempted for WhatsApp audio webhook")
        raise HTTPException(status_code=401, detail="Invalid API key")

    # Parse multipart form
    form = await request.form()
    audio_file_raw = form.get("audio")
    tenant_id_raw = form.get("tenant_id", "")
    phone_raw = form.get("phone", "")
    mime_type_raw = form.get("mime_type", "audio/ogg")

    if not audio_file_raw:
        raise HTTPException(status_code=400, detail="Missing audio file")

    # Handle file - could be UploadFile from FastAPI or similar from test client
    audio_file: Any = audio_file_raw

    if not phone_raw:
        raise HTTPException(status_code=400, detail="Missing phone in request")

    # Convert form values to strings
    phone = str(phone_raw) if phone_raw else ""
    tenant_id: str | None = str(tenant_id_raw) if tenant_id_raw else None
    mime_type = str(mime_type_raw) if mime_type_raw else "audio/ogg"

    # Look up tenant
    resolved_tenant_id = registry.lookup_by_phone(phone)
    if tenant_id:
        if resolved_tenant_id != tenant_id:
            raise HTTPException(status_code=400, detail="Phone number does not match tenant_id")
    else:
        tenant_id = resolved_tenant_id

    if not tenant_id:
        raise HTTPException(status_code=404, detail="No tenant found for phone number")

    tenant_logger = TenantLogAdapter(logger, tenant_id)
    tenant_logger.info("Received WhatsApp audio message")

    audio_bytes = await audio_file.read()
    audio_hash = hashlib.sha256(audio_bytes).hexdigest()

    cache = AudioTranscriptionCache()
    cached = cache.get(audio_hash, tenant_id)

    if cached:
        tenant_logger.info("Using cached transcription for audio hash %s", audio_hash[:8])
        transcribed_text = cached["transcription"]
    else:
        # Save to temp file for transcription
        ext_map = {"audio/ogg": ".ogg", "audio/opus": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a"}
        ext = ext_map.get(mime_type, ".ogg")
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name

        try:
            transcriber = AudioTranscriber()
            transcribed_text = await transcriber.transcribe_audio(tmp_path, mime_type)
            if transcribed_text.startswith("Error:"):
                tenant_logger.error("Transcription failed: %s", transcribed_text)
                raise HTTPException(status_code=500, detail=transcribed_text)
            # Cache the transcription
            cache.set(
                audio_hash=audio_hash,
                transcription=transcribed_text,
                mime_type=mime_type,
                tenant_id=tenant_id,
            )
            tenant_logger.info("Transcribed audio (%s bytes)", len(audio_bytes))
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    tenant_config = _get_tenant_config(tenant_id)
    matched, cleaned_text = check_wake_word(transcribed_text, tenant_config.wake_word if tenant_config else None)

    if not matched:
        wake_word = tenant_config.wake_word if tenant_config else None
        tenant_logger.info("Wake word '%s' not found in transcription, ignoring audio", wake_word)
        return {"response": "", "tenant_id": tenant_id, "wake_word_matched": "false"}

    if not cleaned_text:
        tenant_logger.info("Wake word matched but no text after stripping")
        return {"response": "", "tenant_id": tenant_id, "wake_word_matched": "true"}

    agent_name = tenant_config.default_agent if tenant_config else "developer"
    tenant_logger.info("Wake word matched, routing to agent (%s chars)", len(cleaned_text))

    try:
        result = await _run_agent(request, tenant_id, agent_name, cleaned_text, phone, tenant_logger)
        tenant_logger.info("Successfully processed audio for tenant %s", tenant_id)
        return {"response": result, "tenant_id": tenant_id, "wake_word_matched": "true"}
    except asyncio.TimeoutError:
        tenant_logger.error("Agent timed out after 300s for tenant %s", tenant_id)
        raise HTTPException(status_code=504, detail="Agent response timed out. Please try again.")
    except Exception as e:
        detail = _unwrap_exception_group(e)
        tenant_logger.error("Failed to process WhatsApp audio for tenant %s:\n%s", tenant_id, detail)
        raise HTTPException(status_code=500, detail="Internal error processing message")
