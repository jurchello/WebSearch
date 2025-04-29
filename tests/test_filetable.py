#
# Gramps - a GTK+/GNOME based genealogy program
#
# Copyright (C) 2025 Yurii Liubymyi <jurchello@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

# ----------------------------------------------------------------------------

"""
Unit tests for the FileTable class.

This module tests the core functionality of the FileTable class, including:
- Creating records with uniqueness and required field validation
- Bulk creation with duplicate handling
- Updating records with enforcement of unique constraints
- Deleting records by ID and by field
- Finding, filtering, and counting records
- Checking for record existence
- Ordering records by fields
- Migrating records (adding and removing fields)

Mocks are used to avoid real file operations during tests.
Each test ensures that the file table behaves correctly according to its configuration.
"""

import unittest
import os
from unittest.mock import patch
from models import DBFileTableConfig
from constants import DuplicateHandlingMode, DB_FILE_TABLE_DIR
from db_file_table import (
    DBFileTable,
    DuplicateEntryError,
)


class TestDBFileTable(unittest.TestCase):
    """Test cases for DBFileTable class."""

    def setUp(self):
        """Set up mock configuration and mock file data."""
        self.config = DBFileTableConfig(
            filename="mock_file.json",
            cache_fields=["id", "email"],
            unique_fields=["email"],
            required_fields=["name"],
            on_bulk_duplicate=DuplicateHandlingMode.THROW_ERROR.value,
            timestamps=True,
        )
        self.filepath = os.path.join(DB_FILE_TABLE_DIR, self.config.filename)
        self.db = DBFileTable(self.config)

    def tearDown(self):
        """Clean up created files after each test."""
        if os.path.exists(self.filepath):
            os.remove(self.filepath)

    @patch("db_file_table.DBFileTable._load_data", return_value=[])
    @patch("db_file_table.DBFileTable._save_data")
    def test_create_record(self, mock_save, _mock_load):
        """Test the creation of a new record."""
        record = {"name": "John", "email": "john@example.com"}
        self.db.create(record)

        self.assertIn("id", record)
        self.assertEqual(record["email"], "john@example.com")
        self.assertEqual(record["name"], "John")
        self.assertIn("created_at", record)
        self.assertIn("updated_at", record)
        mock_save.assert_called_once()

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "email": "john@example.com"}],
    )
    def test_create_record_with_duplicate_email(self, _mock_load):
        """Test creating a record with a duplicate email."""
        record = {"name": "Jane", "email": "john@example.com"}

        with self.assertRaises(DuplicateEntryError):
            self.db.create(record)

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "email": "john@example.com"}],
    )
    @patch("db_file_table.DBFileTable._save_data")
    def test_update_record(self, mock_save, _mock_load):
        """Test updating an existing record."""
        record_id = "123"
        updates = {"name": "John Doe"}

        updated = self.db.update(record_id, updates)
        self.assertTrue(updated)
        mock_save.assert_called_once()

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[
            {"id": "123", "email": "john@example.com", "name": "John"},
            {"id": "456", "email": "jane@example.com", "name": "Jane"},
        ],
    )
    @patch("db_file_table.DBFileTable._save_data")
    def test_update_record_with_duplicate_email(self, _mock_save, _mock_load):
        """Test updating a record to duplicate email from another record."""
        updates = {"email": "john@example.com"}

        with self.assertRaises(DuplicateEntryError):
            self.db.update("456", updates)

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "email": "john@example.com", "name": "John"}],
    )
    @patch("db_file_table.DBFileTable._save_data")
    def test_delete_record(self, mock_save, _mock_load):
        """Test deleting a record."""
        deleted = self.db.delete("123")
        self.assertTrue(deleted)
        mock_save.assert_called_once()

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "email": "john@example.com", "name": "John"}],
    )
    def test_delete_non_existent_record(self, _mock_load):
        """Test deleting a non-existent record."""
        deleted = self.db.delete("999")
        self.assertFalse(deleted)

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "email": "john@example.com", "name": "John"}],
    )
    def test_get_by_field(self, _mock_load):
        """Test getting records by a specific field."""
        result = self.db.get_by_field("email", "john@example.com")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["email"], "john@example.com")

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "email": "john@example.com", "name": "John"}],
    )
    def test_filter(self, _mock_load):
        """Test filtering records by multiple conditions."""
        result = self.db.filter(name="John", email="john@example.com")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["name"], "John")

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "email": "john@example.com", "name": "John"}],
    )
    def test_count(self, _mock_load):
        """Test counting records."""
        total = self.db.count()
        self.assertEqual(total, 1)

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "email": "john@example.com", "name": "John"}],
    )
    def test_exists(self, _mock_load):
        """Test checking if a record exists."""
        exists = self.db.exists("email", "john@example.com")
        self.assertTrue(exists)

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "email": "john@example.com", "name": "John"}],
    )
    def test_order_by(self, _mock_load):
        """Test ordering records by a field."""
        result = self.db.order_by("name", reverse=True)
        self.assertEqual(result[0]["name"], "John")

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "name": "John"}],
    )
    def test_migrate_add_field(self, _mock_load):
        """Test adding a new field to existing records."""
        self.db.migrate_add_field("phone", "unknown")
        data = self.db.all()
        self.assertTrue(all("phone" in record for record in data))

    @patch(
        "db_file_table.DBFileTable._load_data",
        return_value=[{"id": "123", "name": "John"}],
    )
    def test_migrate_remove_field(self, _mock_load):
        """Test removing a field from records."""
        self.db.migrate_remove_field("name")
        data = self.db.all()
        self.assertTrue(all("name" not in record for record in data))


if __name__ == "__main__":
    unittest.main()
