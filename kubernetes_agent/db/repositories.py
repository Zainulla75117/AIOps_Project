"""MongoDB repository classes for chat, incidents, and scan history.

Each repository wraps a single MongoDB collection and provides
clean async CRUD methods. All repositories degrade gracefully
if MongoDB is not connected (operations become no-ops).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from kubernetes_agent.db.mongo_client import MongoClient
from kubernetes_agent.utils.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    """Return timezone-aware UTC now."""
    return datetime.now(timezone.utc)


class ChatRepository:
    """Persistence layer for chat conversations."""

    def __init__(self, mongo: MongoClient) -> None:
        self._mongo = mongo

    async def save_message(
        self,
        session_id: str,
        query: str,
        reply: str,
        context_summary: dict[str, Any] | None = None,
        response_time_ms: float = 0.0,
    ) -> str | None:
        """Save a chat message pair and return the inserted document ID."""
        coll = self._mongo.chat_history
        if coll is None:
            return None

        doc = {
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "query": query,
            "reply": reply,
            "context_summary": context_summary or {},
            "response_time_ms": response_time_ms,
            "timestamp": _utcnow(),
        }

        try:
            result = await coll.insert_one(doc)
            logger.debug("chat_message_saved", session_id=session_id)
            return str(result.inserted_id)
        except Exception as exc:
            logger.warning("chat_message_save_failed", error=str(exc))
            return None

    async def get_history(
        self,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Get recent chat messages, optionally filtered by session."""
        coll = self._mongo.chat_history
        if coll is None:
            return []

        query: dict[str, Any] = {}
        if session_id:
            query["session_id"] = session_id

        try:
            cursor = coll.find(
                query,
                {"_id": 0},  # Exclude MongoDB _id
            ).sort("timestamp", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as exc:
            logger.warning("chat_history_fetch_failed", error=str(exc))
            return []

    async def get_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        """Get unique chat sessions with their message counts."""
        coll = self._mongo.chat_history
        if coll is None:
            return []

        try:
            pipeline = [
                {"$group": {
                    "_id": "$session_id",
                    "message_count": {"$sum": 1},
                    "first_message": {"$min": "$timestamp"},
                    "last_message": {"$max": "$timestamp"},
                    "first_query": {"$first": "$query"},
                }},
                {"$sort": {"last_message": -1}},
                {"$limit": limit},
                {"$project": {
                    "_id": 0,
                    "session_id": "$_id",
                    "message_count": 1,
                    "first_message": 1,
                    "last_message": 1,
                    "first_query": 1,
                }},
            ]
            return await coll.aggregate(pipeline).to_list(length=limit)
        except Exception as exc:
            logger.warning("chat_sessions_fetch_failed", error=str(exc))
            return []


class IncidentRepository:
    """Persistence layer for incident audit trail."""

    def __init__(self, mongo: MongoClient) -> None:
        self._mongo = mongo

    async def save_incident(self, incident_data: dict[str, Any]) -> str | None:
        """Save a new incident or update an existing one."""
        coll = self._mongo.incidents
        if coll is None:
            return None

        incident_id = incident_data.get("id") or incident_data.get("incident_id")
        if not incident_id:
            logger.warning("incident_save_skipped", reason="no_incident_id")
            return None

        doc = {
            **incident_data,
            "incident_id": incident_id,
            "created_at": incident_data.get("timestamp", _utcnow()),
            "updated_at": _utcnow(),
        }
        # Remove duplicate keys
        doc.pop("id", None)

        try:
            result = await coll.update_one(
                {"incident_id": incident_id},
                {"$set": doc},
                upsert=True,
            )
            logger.debug("incident_saved", incident_id=incident_id)
            return incident_id
        except Exception as exc:
            logger.warning("incident_save_failed", error=str(exc))
            return None

    async def resolve_incident(self, incident_id: str) -> bool:
        """Mark an incident as resolved."""
        coll = self._mongo.incidents
        if coll is None:
            return False

        try:
            now = _utcnow()
            result = await coll.update_one(
                {"incident_id": incident_id},
                {"$set": {
                    "status": "resolved",
                    "resolved_at": now,
                    "updated_at": now,
                }},
            )
            return result.modified_count > 0
        except Exception as exc:
            logger.warning("incident_resolve_failed", error=str(exc))
            return False

    async def get_history(
        self,
        limit: int = 50,
        status: str | None = None,
        severity: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get incident history with optional filters."""
        coll = self._mongo.incidents
        if coll is None:
            return []

        query: dict[str, Any] = {}
        if status and status != "all":
            query["status"] = status
        if severity and severity != "all":
            query["severity"] = severity

        try:
            cursor = coll.find(
                query,
                {"_id": 0},
            ).sort("created_at", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as exc:
            logger.warning("incident_history_fetch_failed", error=str(exc))
            return []

    async def get_by_id(self, incident_id: str) -> dict[str, Any] | None:
        """Get a single incident by ID."""
        coll = self._mongo.incidents
        if coll is None:
            return None

        try:
            return await coll.find_one(
                {"incident_id": incident_id},
                {"_id": 0},
            )
        except Exception as exc:
            logger.warning("incident_fetch_failed", error=str(exc))
            return None


class ScanRepository:
    """Persistence layer for scan metrics history."""

    def __init__(self, mongo: MongoClient) -> None:
        self._mongo = mongo

    async def save_scan(self, scan_data: dict[str, Any]) -> str | None:
        """Save a scan result."""
        coll = self._mongo.scan_history
        if coll is None:
            return None

        doc = {
            **scan_data,
            "timestamp": scan_data.get("timestamp", _utcnow()),
        }

        try:
            result = await coll.insert_one(doc)
            logger.debug("scan_saved", scan_id=scan_data.get("scan_id"))
            return str(result.inserted_id)
        except Exception as exc:
            logger.warning("scan_save_failed", error=str(exc))
            return None

    async def get_history(self, limit: int = 100) -> list[dict[str, Any]]:
        """Get recent scan history."""
        coll = self._mongo.scan_history
        if coll is None:
            return []

        try:
            cursor = coll.find(
                {},
                {"_id": 0},
            ).sort("timestamp", -1).limit(limit)
            return await cursor.to_list(length=limit)
        except Exception as exc:
            logger.warning("scan_history_fetch_failed", error=str(exc))
            return []

    async def get_metrics(self, hours: int = 24) -> list[dict[str, Any]]:
        """Get aggregated scan metrics for the last N hours."""
        coll = self._mongo.scan_history
        if coll is None:
            return []

        since = datetime.now(timezone.utc).replace(
            microsecond=0
        ) - __import__("datetime").timedelta(hours=hours)

        try:
            cursor = coll.find(
                {"timestamp": {"$gte": since}},
                {"_id": 0},
            ).sort("timestamp", 1)
            return await cursor.to_list(length=10000)
        except Exception as exc:
            logger.warning("scan_metrics_fetch_failed", error=str(exc))
            return []
