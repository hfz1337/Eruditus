"""Repository for CTF database operations."""

import re
from typing import Any, Optional

from bson import ObjectId
from config import CTF_COLLECTION
from db.base import BaseRepository


class CTFRepository(BaseRepository):
    """Repository for CTF collection operations."""

    def __init__(self) -> None:
        """Initialize the CTF repository."""
        super().__init__(CTF_COLLECTION)

    def find_by_name(self, name: str) -> Optional[dict]:
        """Find a CTF by name (case-insensitive).

        Args:
            name: The CTF name to search for.

        Returns:
            The CTF document or None if not found.
        """
        pattern = re.compile(f"^{re.escape(name.strip())}$", re.IGNORECASE)
        return self.find_one({"name": pattern})

    def find_by_guild_category(self, category_id: int) -> Optional[dict]:
        """Find a CTF by its Discord guild category ID.

        Args:
            category_id: The Discord category channel ID.

        Returns:
            The CTF document or None if not found.
        """
        return self.find_one({"guild_category": category_id})

    def find_by_guild_channel(self, channel_id: int) -> Optional[dict]:
        """Find a CTF that contains a specific channel.

        Args:
            channel_id: The Discord channel ID.

        Returns:
            The CTF document or None if not found.
        """
        return self.find_one(
            {
                "$or": [
                    {"guild_channels.announcements": channel_id},
                    {"guild_channels.credentials": channel_id},
                    {"guild_channels.scoreboard": channel_id},
                    {"guild_channels.solves": channel_id},
                    {"guild_channels.notes": channel_id},
                    {"guild_channels.bot-cmds": channel_id},
                ]
            }
        )

    def find_active(self) -> list[dict]:
        """Find all active (non-archived, non-ended) CTFs.

        Returns:
            List of active CTF documents.
        """
        return self.find({"archived": False, "ended": False})

    def find_not_ended(self) -> list[dict]:
        """Find all CTFs that haven't ended yet.

        Returns:
            List of CTF documents.
        """
        return self.find({"ended": False})

    def find_not_archived(self) -> list[dict]:
        """Find all CTFs that aren't archived.

        Returns:
            List of non-archived CTF documents.
        """
        return self.find({"archived": False})

    def add_challenge(self, ctf_id: ObjectId, challenge_id: ObjectId) -> None:
        """Add a challenge reference to a CTF.

        Args:
            ctf_id: The CTF's ObjectId.
            challenge_id: The challenge's ObjectId to add.
        """
        self.update_by_id(ctf_id, {"$push": {"challenges": challenge_id}})

    def update_credentials(self, ctf_id: ObjectId, credentials: dict[str, Any]) -> None:
        """Update a CTF's credentials.

        Args:
            ctf_id: The CTF's ObjectId.
            credentials: The new credentials dictionary.
        """
        self.update_by_id(ctf_id, {"$set": {"credentials": credentials}})

    def set_ended(self, ctf_id: ObjectId, ended: bool = True) -> None:
        """Mark a CTF as ended or not ended.

        Args:
            ctf_id: The CTF's ObjectId.
            ended: Whether the CTF has ended.
        """
        self.update_by_id(ctf_id, {"$set": {"ended": ended}})

    def set_archived(
        self, ctf_id: ObjectId, archived: bool = True, ended: Optional[bool] = None
    ) -> None:
        """Mark a CTF as archived or not archived.

        Args:
            ctf_id: The CTF's ObjectId.
            archived: Whether the CTF is archived.
            ended: Whether the CTF has ended (optional).
        """
        update = {"archived": archived}
        if ended is not None:
            update["ended"] = ended
        self.update_by_id(ctf_id, {"$set": update})

    def delete(self, ctf_id: ObjectId) -> None:
        """Delete a CTF from the database.

        Args:
            ctf_id: The CTF's ObjectId.
        """
        self.delete_by_id(ctf_id)

    def set_privacy(self, ctf_id: ObjectId, private: bool) -> None:
        """Set the privacy status of a CTF.

        Args:
            ctf_id: The CTF's ObjectId.
            private: Whether the CTF is private.
        """
        self.update_by_id(ctf_id, {"$set": {"private": private}})

    def set_name(self, ctf_id: ObjectId, name: str) -> None:
        """Rename a CTF.

        Args:
            ctf_id: The CTF's ObjectId.
            name: The new CTF name.
        """
        self.update_by_id(ctf_id, {"$set": {"name": name}})

    def remove_challenge(self, ctf_id: ObjectId, challenge_id: ObjectId) -> None:
        """Remove a challenge reference from a CTF.

        Args:
            ctf_id: The CTF's ObjectId.
            challenge_id: The challenge's ObjectId to remove.
        """
        self.update_by_id(ctf_id, {"$pull": {"challenges": challenge_id}})

    def get_ctf_info(self, **search_fields: Any) -> Optional[dict]:
        """Retrieve information for a CTF with flexible search.

        This method maintains backward compatibility with the original
        get_ctf_info function from lib/util.py.

        Args:
            **search_fields: Field-value pairs to search by.
                The 'name' field is matched case-insensitively.

        Returns:
            The CTF document, or None if no such CTF exists.
        """
        query = {}
        for field, value in search_fields.items():
            if field == "name":
                query[field] = re.compile(
                    f"^{re.escape(value.strip())}$", re.IGNORECASE
                )
                continue
            query[field] = value
        return self.find_one(query)
