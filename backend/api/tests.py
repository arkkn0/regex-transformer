from io import BytesIO
import csv
from unittest.mock import patch

import pandas as pd
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from .storage import _EXPORT_CSV, _STORE


def csv_upload(content: str, name: str = "sample.csv") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, content.encode("utf-8"), content_type="text/csv")


class RegexTransformerApiTests(TestCase):
    def setUp(self):
        _STORE.clear()
        _EXPORT_CSV.clear()
        self.client = APIClient()

    def upload_sample(self) -> str:
        response = self.client.post(
            "/api/upload/",
            {"file": csv_upload("ID,Email\n1,john@example.com\n2,jane@test.org\n")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)
        return response.json()["file_id"]

    def test_upload_csv_returns_columns_preview_and_text_columns(self):
        response = self.client.post(
            "/api/upload/",
            {"file": csv_upload("\ufeffID,Email\n1,john@example.com\n")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["columns"], ["ID", "Email"])
        self.assertEqual(body["preview_rows"][0]["Email"], "john@example.com")
        self.assertIn("Email", body["detected_text_columns"])
        self.assertEqual(body["warnings"], [])

    @override_settings(MAX_CELL_CHARS=10)
    def test_upload_preserves_large_text_cells_but_returns_warning(self):
        long_value = "x" * 25
        response = self.client.post(
            "/api/upload/",
            {"file": csv_upload(f"ID,Notes\n1,{long_value}\n")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["preview_rows"][0]["Notes"], long_value)
        self.assertIn("exceed 10 characters", body["warnings"][0])

    @override_settings(MAX_UPLOAD_ROWS=1)
    def test_upload_rejects_files_over_row_limit(self):
        response = self.client.post(
            "/api/upload/",
            {"file": csv_upload("ID,Email\n1,a@example.com\n2,b@example.com\n")},
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("too many rows", response.json()["error"])

    def test_apply_transform_replaces_matches_and_creates_download(self):
        file_id = self.upload_sample()

        response = self.client.post(
            "/api/transform/apply/",
            {
                "file_id": file_id,
                "column_name": "Email",
                "regex_pattern": r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
                "replacement_value": "REDACTED",
                "flags": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["matched_cells_count"], 2)
        self.assertEqual(body["changed_rows_count"], 2)
        self.assertEqual(body["transformed_preview"][0]["Email"], "REDACTED")
        self.assertTrue(body["downloadable_file_url"].startswith("/api/download/"))

    def test_apply_uses_literal_replacement_not_backreferences(self):
        file_id = self.upload_sample()

        response = self.client.post(
            "/api/transform/apply/",
            {
                "file_id": file_id,
                "column_name": "Email",
                "regex_pattern": r"(john)@example\.com",
                "replacement_value": r"\1",
                "flags": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["transformed_preview"][0]["Email"], r"\1")

    def test_download_escapes_csv_formula_values(self):
        file_id = self.upload_sample()
        apply_response = self.client.post(
            "/api/transform/apply/",
            {
                "file_id": file_id,
                "column_name": "Email",
                "regex_pattern": r".+",
                "replacement_value": "=HYPERLINK(\"https://example.com\")",
                "flags": [],
            },
            format="json",
        )

        self.assertEqual(apply_response.status_code, 200)
        download_response = self.client.get(apply_response.json()["downloadable_file_url"])
        content = b"".join(download_response.streaming_content).decode("utf-8")
        rows = list(csv.DictReader(content.splitlines()))
        self.assertEqual(rows[0]["Email"], "'=HYPERLINK(\"https://example.com\")")

    @override_settings(MAX_CELL_CHARS=10)
    def test_apply_rejects_large_target_cells_without_truncating(self):
        long_value = "john@example.com" + ("x" * 20)
        upload_response = self.client.post(
            "/api/upload/",
            {"file": csv_upload(f"ID,Email\n1,{long_value}\n")},
            format="multipart",
        )
        self.assertEqual(upload_response.status_code, 200)

        response = self.client.post(
            "/api/transform/apply/",
            {
                "file_id": upload_response.json()["file_id"],
                "column_name": "Email",
                "regex_pattern": r"john",
                "replacement_value": "jane",
                "flags": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("longer than 10 characters", response.json()["error"])

    def test_apply_rejects_risky_nested_quantifier_regex(self):
        file_id = self.upload_sample()

        response = self.client.post(
            "/api/transform/apply/",
            {
                "file_id": file_id,
                "column_name": "Email",
                "regex_pattern": r"(a+)+$",
                "replacement_value": "x",
                "flags": [],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("too risky", response.json()["error"])

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("api.views.call_llm_for_regex")
    def test_generate_pattern_validates_llm_output_and_returns_local_matches(self, mock_llm):
        mock_llm.return_value = {
            "regex_pattern": r"\b[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}\b",
            "explanation": "Matches email addresses.",
            "warnings": [],
        }
        file_id = self.upload_sample()

        response = self.client.post(
            "/api/pattern/generate/",
            {
                "file_id": file_id,
                "column_name": "Email",
                "natural_language_prompt": "Find email addresses.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["explanation"], "Matches email addresses.")
        self.assertEqual(body["sample_matches"][0]["matched_text"], "john@example.com")

    @override_settings(OPENAI_API_KEY="test-key")
    @patch("api.views.call_llm_for_regex")
    def test_generate_pattern_rejects_empty_target_column(self, mock_llm):
        response = self.client.post(
            "/api/upload/",
            {"file": csv_upload("ID,Email\n1,\n2,\n")},
            format="multipart",
        )
        self.assertEqual(response.status_code, 200)

        response = self.client.post(
            "/api/pattern/generate/",
            {
                "file_id": response.json()["file_id"],
                "column_name": "Email",
                "natural_language_prompt": "Find email addresses.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("no non-empty values", response.json()["error"])
        mock_llm.assert_not_called()


class ParsingTests(TestCase):
    @override_settings(MAX_UPLOAD_ROWS=10, MAX_UPLOAD_COLUMNS=10)
    def test_duplicate_columns_are_rejected(self):
        buffer = BytesIO()
        pd.DataFrame([[1, 2]], columns=["Email", "Email"]).to_excel(buffer, index=False)
        uploaded = SimpleUploadedFile(
            "dup.xlsx",
            buffer.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        response = APIClient().post("/api/upload/", {"file": uploaded}, format="multipart")

        self.assertEqual(response.status_code, 400)
        self.assertIn("duplicate column", response.json()["error"])
