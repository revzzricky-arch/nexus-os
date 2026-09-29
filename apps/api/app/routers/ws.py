"""
WebSocket Router - Scaffold Placeholder
Per security: Do NOT use ?token=SECRET in URL
Chosen approach: Initial auth message after connection
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import json

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Scaffold WS endpoint - placeholder
    Auth approach: client connects without token in URL, sends first message {type: "auth", token: "..."}
    No real event streaming yet
    """
    await websocket.accept()

    # In scaffold, we don't enforce auth strictly, just document approach
    # Real impl would wait for auth message and validate via SecurityService

    try:
        # Send welcome with auth instructions
        await websocket.send_text(
            json.dumps(
                {
                    "type": "welcome",
                    "message": "NEXUS WS scaffold - no real streaming yet",
                    "auth_approach": "Send {type: 'auth', token: 'Bearer <dev-token>'} as first message, NOT ?token= in URL",
                    "codename": "NEXUS - temporary, public name TBD",
                }
            )
        )

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("type") == "auth":
                    # Scaffold: accept any auth for now, real validation in Phase 2
                    await websocket.send_text(
                        json.dumps({"type": "authenticated", "message": "Scaffold auth accepted"})
                    )
                elif msg.get("type") == "subscribe":
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "subscribed",
                                "channels": msg.get("channels", []),
                                "message": "Scaffold subscription - no real events yet",
                            }
                        )
                    )
                elif msg.get("type") == "ping":
                    await websocket.send_text(json.dumps({"type": "pong"}))
                else:
                    await websocket.send_text(
                        json.dumps({"type": "echo", "received": msg, "scaffold": True})
                    )
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({"type": "error", "message": "Invalid JSON"}))

    except WebSocketDisconnect:
        pass
