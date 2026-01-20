"""Base repository with common CRUD operations."""

from typing import Any, Optional

from bson import ObjectId
from config import DBNAME, MONGO
from pymongo.collection import Collection
from pymongo.results import DeleteResult, InsertOneResult, UpdateResult


class BaseRepository:
    """Base repository providing common database operations.

    Attributes:
        collection: The MongoDB collection this repository operates on.
    """

    def __init__(self, collection_name: str) -> None:
        """Initialize the repository with a collection.

        Args:
            collection_name: Name of the MongoDB collection.
        """
        self._collection: Collection = MONGO[DBNAME][collection_name]

    @property
    def collection(self) -> Collection:
        """Get the underlying MongoDB collection."""
        return self._collection

    def find_one(self, query: dict[str, Any]) -> Optional[dict]:
        """Find a single document matching the query.

        Args:
            query: MongoDB query dictionary.

        Returns:
            The matching document or None if not found.
        """
        return self._collection.find_one(query)

    def find(self, query: dict[str, Any]) -> list[dict]:
        """Find all documents matching the query.

        Args:
            query: MongoDB query dictionary.

        Returns:
            List of matching documents.
        """
        return list(self._collection.find(query))

    def find_by_id(self, oid: ObjectId) -> Optional[dict]:
        """Find a document by its ObjectId.

        Args:
            oid: The document's ObjectId.

        Returns:
            The matching document or None if not found.
        """
        return self.find_one({"_id": oid})

    def insert_one(self, document: dict[str, Any]) -> InsertOneResult:
        """Insert a single document.

        Args:
            document: The document to insert.

        Returns:
            The insert result containing the inserted_id.
        """
        return self._collection.insert_one(document)

    def update_one(self, query: dict[str, Any], update: dict[str, Any]) -> UpdateResult:
        """Update a single document.

        Args:
            query: Query to find the document.
            update: Update operations (e.g., {"$set": {...}}).

        Returns:
            The update result.
        """
        return self._collection.update_one(query, update)

    def update_by_id(self, oid: ObjectId, update: dict[str, Any]) -> UpdateResult:
        """Update a document by its ObjectId.

        Args:
            oid: The document's ObjectId.
            update: Update operations (e.g., {"$set": {...}}).

        Returns:
            The update result.
        """
        return self.update_one({"_id": oid}, update)

    def delete_one(self, query: dict[str, Any]) -> DeleteResult:
        """Delete a single document.

        Args:
            query: Query to find the document to delete.

        Returns:
            The delete result.
        """
        return self._collection.delete_one(query)

    def delete_by_id(self, oid: ObjectId) -> DeleteResult:
        """Delete a document by its ObjectId.

        Args:
            oid: The document's ObjectId.

        Returns:
            The delete result.
        """
        return self.delete_one({"_id": oid})

    def count(self, query: Optional[dict[str, Any]] = None) -> int:
        """Count documents matching the query.

        Args:
            query: MongoDB query dictionary. If None, counts all documents.

        Returns:
            Number of matching documents.
        """
        return self._collection.count_documents(query or {})
