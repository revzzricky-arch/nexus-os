"""
Worker Entrypoint - Phase 3 PR 3.1 Dedicated Worker Process
- Separate process from API (API != Worker)
- Creates/uses AsyncSessionLocal
- Instantiates MissionWorker with unique worker_id
- Calls await worker.run_forever(AsyncSessionLocal)
- Handles graceful shutdown via SIGTERM/SIGINT
- Never starts FastAPI
- Never executes as FastAPI background task
"""

import asyncio
import logging
import os
import signal
import uuid

from app.db.session import AsyncSessionLocal
from app.worker import MissionWorker

logger = logging.getLogger(__name__)

# Configure logging for worker process
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


async def main():
    worker_id = os.getenv("WORKER_ID") or f"worker-{uuid.uuid4().hex[:8]}"
    poll_interval = float(os.getenv("WORKER_POLL_INTERVAL", "2.0"))
    lease_timeout = int(os.getenv("WORKER_LEASE_TIMEOUT", "60"))
    heartbeat_interval = float(os.getenv("WORKER_HEARTBEAT_INTERVAL", "20"))

    worker = MissionWorker(
        worker_id=worker_id,
        poll_interval=poll_interval,
        lease_timeout=lease_timeout,
        heartbeat_interval=heartbeat_interval,
        session_factory=AsyncSessionLocal,
    )

    # Graceful shutdown handling
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def handle_signal(signum, frame=None):
        logger.info(f"Worker {worker_id} received signal {signum}, shutting down...")
        worker.stop()
        stop_event.set()

    # Register signal handlers for SIGTERM and SIGINT
    # In asyncio, we use loop.add_signal_handler where available (Unix)
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda s=sig: handle_signal(s))
    except NotImplementedError:
        # Windows or loop doesn't support add_signal_handler, fallback to signal.signal
        signal.signal(signal.SIGTERM, handle_signal)
        signal.signal(signal.SIGINT, handle_signal)

    logger.info(f"Starting dedicated worker {worker_id} (API != Worker, separate process)")
    logger.info(f"Config: poll_interval={poll_interval}s lease_timeout={lease_timeout}s heartbeat_interval={heartbeat_interval}s")

    # Run forever until stopped
    worker_task = asyncio.create_task(worker.run_forever(AsyncSessionLocal))

    # Wait for stop signal
    await stop_event.wait()

    logger.info(f"Worker {worker_id} stop requested, waiting for current job to finish...")
    worker.stop()

    try:
        await asyncio.wait_for(worker_task, timeout=30.0)
    except asyncio.TimeoutError:
        logger.warning(f"Worker {worker_id} did not stop within 30s, cancelling...")
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass

    logger.info(f"Worker {worker_id} shutdown complete")


def run():
    """Sync entrypoint for python -m app.worker_main"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Worker interrupted by KeyboardInterrupt")


if __name__ == "__main__":
    run()
