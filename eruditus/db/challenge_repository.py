"""Repository for Challenge database operations."""

import re
from typing import Any, Optional

from bson import ObjectId
from config import CHALLENGE_COLLECTION
from db.base import BaseRepository


class ChallengeRepository(BaseRepository):
    """Repository for Challenge collection operations."""

    def __init__(self) -> None:
        """Initialize the Challenge repository."""
        super().__init__(CHALLENGE_COLLECTION)

    def create(self, document: dict[str, Any]) -> None:
        """Create a new challenge.

        Args:
            document: The challenge document to insert.
        """
        self.insert_one(document)

    def delete(self, challenge_id: ObjectId) -> None:
        """Delete a challenge from the database.

        Args:
            challenge_id: The challenge's ObjectId.
        """
        self.delete_by_id(challenge_id)

    def find_by_name(self, name: str) -> Optional[dict]:
        """Find a challenge by name (case-insensitive).

        Args:
            name: The challenge name to search for.

        Returns:
            The challenge document or None if not found.
        """
        pattern = re.compile(f"^{re.escape(name.strip())}$", re.IGNORECASE)
        return self.find_one({"name": pattern})

    def find_by_thread(self, thread_id: int) -> Optional[dict]:
        """Find a challenge by its Discord thread ID.

        Args:
            thread_id: The Discord thread ID.

        Returns:
            The challenge document or None if not found.
        """
        return self.find_one({"thread": thread_id})

    def find_by_platform_id(self, platform_id: str) -> Optional[dict]:
        """Find a challenge by its platform-specific ID.

        Args:
            platform_id: The challenge ID from the CTF platform.

        Returns:
            The challenge document or None if not found.
        """
        return self.find_one({"id": platform_id})

    def find_unsolved(self) -> list[dict]:
        """Find all unsolved challenges.

        Returns:
            List of unsolved challenge documents.
        """
        return self.find({"solved": False})

    def find_solved(self) -> list[dict]:
        """Find all solved challenges.

        Returns:
            List of solved challenge documents.
        """
        return self.find({"solved": True})

    def find_by_category(self, category: str) -> list[dict]:
        """Find challenges by category (case-insensitive).

        Args:
            category: The challenge category.

        Returns:
            List of matching challenge documents.
        """
        pattern = re.compile(f"^{re.escape(category.strip())}$", re.IGNORECASE)
        return self.find({"category": pattern})

    def mark_solved(
        self,
        challenge_id: ObjectId,
        solved: bool = True,
        blooded: bool = False,
        solve_time: Optional[Any] = None,
        solve_announcement: Optional[int] = None,
    ) -> None:
        """Mark a challenge as solved or unsolved.

        Args:
            challenge_id: The challenge's ObjectId.
            solved: Whether the challenge is solved.
            blooded: Whether this was a first blood.
            solve_time: The time of the solve.
            solve_announcement: The Discord message ID of the solve announcement.
        """
        update = {
            "$set": {
                "solved": solved,
                "blooded": blooded,
                "solve_time": solve_time,
                "solve_announcement": solve_announcement,
            }
        }
        self.update_by_id(challenge_id, update)

    def add_player(self, challenge_id: ObjectId, player_id: int) -> None:
        """Add a player to a challenge.

        Args:
            challenge_id: The challenge's ObjectId.
            player_id: The Discord user ID of the player.
        """
        self.update_by_id(challenge_id, {"$addToSet": {"players": player_id}})

    def remove_player(self, challenge_id: ObjectId, player_id: int) -> None:
        """Remove a player from a challenge.

        Args:
            challenge_id: The challenge's ObjectId.
            player_id: The Discord user ID of the player.
        """
        self.update_by_id(challenge_id, {"$pull": {"players": player_id}})

    def set_players(self, challenge_id: ObjectId, players: list) -> None:
        """Set the players list for a challenge.

        Args:
            challenge_id: The challenge's ObjectId.
            players: List of player names.
        """
        self.update_by_id(challenge_id, {"$set": {"players": players}})

    def set_name(self, challenge_id: ObjectId, name: str) -> None:
        """Rename a challenge.

        Args:
            challenge_id: The challenge's ObjectId.
            name: The new challenge name.
        """
        self.update_by_id(challenge_id, {"$set": {"name": name}})

    def remove_player_from_all(self, player_name: str) -> int:
        """Remove a player from all challenges they're working on.

        Args:
            player_name: The player's name to remove.

        Returns:
            Number of challenges updated.
        """
        result = self._collection.update_many(
            {"players": player_name}, {"$pull": {"players": player_name}}
        )
        return result.modified_count

    def update_solve_details(
        self,
        challenge_id: ObjectId,
        solved: bool,
        blooded: bool,
        solve_time: Optional[int],
        solve_announcement: Optional[int],
        players: list,
        flag: Optional[str] = None,
    ) -> None:
        """Update all solve-related details for a challenge.

        Args:
            challenge_id: The challenge's ObjectId.
            solved: Whether the challenge is solved.
            blooded: Whether this was a first blood.
            solve_time: Unix timestamp of the solve.
            solve_announcement: Discord message ID of the announcement.
            players: List of player names who solved it.
            flag: The flag that was submitted.
        """
        update: dict[str, Any] = {
            "solved": solved,
            "blooded": blooded,
            "solve_time": solve_time,
            "solve_announcement": solve_announcement,
            "players": players,
        }
        if flag is not None:
            update["flag"] = flag
        self.update_by_id(challenge_id, {"$set": update})

    def get_challenge_info(self, **search_fields: Any) -> Optional[dict]:
        """Retrieve a challenge from the database with flexible search.

        This method maintains backward compatibility with the original
        get_challenge_info function from lib/util.py.

        Args:
            **search_fields: Field-value pairs to search by.
                The 'name' and 'category' fields are matched case-insensitively.

        Returns:
            The challenge document, or None if not found.
        """
        query = {}
        for field, value in search_fields.items():
            if field in {"name", "category"}:
                query[field] = re.compile(
                    f"^{re.escape(value.strip())}$", re.IGNORECASE
                )
                continue
            query[field] = value
        return self.find_one(query)
