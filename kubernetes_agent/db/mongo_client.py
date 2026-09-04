"""Async MongoDB client wrapper using Motor.

Provides a singleton async client that integrates with FastAPI's
lifespan events for clean startup and shutdown.
"""

from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from kubernetes_agent.config import AgentConfig, get_config
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


class MongoClient:
    """Async MongoDB client wrapper.

    Uses Motor (async driver built on PyMongo) for non-blocking
    database operations within FastAPI's event loop.
    """

    def __init__(self, cfg: AgentConfig | None = None) -> None:
        self._cfg = cfg or get_config()
        self._client: AsyncIOMotorClient | None = None
        self._db: AsyncIOMotorDatabase | None = None

    async def connect(self) -> None:
        """Connect to MongoDB and create indexes."""
        uri = self._cfg.mongo_uri
        db_name = self._cfg.mongo_db_name

        logger.info("mongodb_connecting", uri=uri, database=db_name)

        client = AsyncIOMotorClient(
            uri,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
        )

        # Verify connectivity before storing references
        try:
            await client.admin.command("ping")
            logger.info("mongodb_connected", database=db_name)
        except Exception as exc:
            logger.error("mongodb_connection_failed", error=str(exc))
            # Close the client to stop background heartbeat threads
            client.close()
            # Don't crash the app — DB features will degrade gracefully
            self._client = None
            self._db = None
            return

        self._client = client
        self._db = client[db_name]

        # Create indexes
        await self._ensure_indexes()

    async def _ensure_indexes(self) -> None:
        """Create TTL and query-performance indexes."""
        if self._db is None:
            return

        try:
            # chat_history: TTL 30 days, query by session and timestamp
            chat = self._db.chat_history
            await chat.create_index("timestamp", expireAfterSeconds=30 * 24 * 3600)
            await chat.create_index("session_id")
            await chat.create_index([("timestamp", -1)])

            # incidents: query by status, severity, timestamp
            incidents = self._db.incidents
            await incidents.create_index("incident_id", unique=True)
            await incidents.create_index("status")
            await incidents.create_index("severity")
            await incidents.create_index([("created_at", -1)])

            # scan_history: TTL 90 days, query by timestamp
            scans = self._db.scan_history
            await scans.create_index("timestamp", expireAfterSeconds=90 * 24 * 3600)
            await scans.create_index([("timestamp", -1)])

            logger.info("mongodb_indexes_created")
        except Exception as exc:
            logger.warning("mongodb_index_creation_failed", error=str(exc))

    async def close(self) -> None:
        """Close the MongoDB connection."""
        if self._client is not None:
            self._client.close()
            logger.info("mongodb_disconnected")

    @property
    def db(self) -> AsyncIOMotorDatabase | None:
        """Return the database instance, or None if not connected."""
        return self._db

    @property
    def is_connected(self) -> bool:
        """Return True if the client is connected."""
        return self._db is not None

    # ---- Collection accessors ----

    @property
    def chat_history(self):
        """The chat_history collection."""
        if self._db is None:
            return None
        return self._db.chat_history

    @property
    def incidents(self):
        """The incidents collection."""
        if self._db is None:
            return None
        return self._db.incidents

    @property
    def scan_history(self):
        """The scan_history collection."""
        if self._db is None:
            return None
        return self._db.scan_history


# Module-level singleton
_mongo: MongoClient | None = None


async def get_mongo_client() -> MongoClient:
    """Return the global MongoClient singleton, creating it on first call."""
    global _mongo
    if _mongo is None:
        _mongo = MongoClient()
        await _mongo.connect()
    return _mongo


def get_mongo_client_sync() -> MongoClient | None:
    """Return the existing MongoClient singleton without creating it."""
    return _mongo


def set_mongo_client(client: MongoClient) -> None:
    """Set the global MongoClient singleton (used during app startup)."""
    global _mongo
    _mongo = client


async def reset_mongo_client() -> None:
    """Reset and close the singleton (for tests)."""
    global _mongo
    if _mongo is not None:
        await _mongo.close()
    _mongo = None
