import io
import re

from django.conf import settings
from django.http import FileResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from . import parsing
from .regex_llm import (
    LlmInvocationError,
    call_llm_for_regex,
    collect_prompt_samples,
    collect_sample_matches,
    normalize_llm_regex_payload,
)
from .serializers import ApplyTransformSerializer, GeneratePatternSerializer
from .storage import get_dataframe, get_export_csv, save_dataframe, save_export_csv
from .transform_apply import (
    apply_regex_to_column,
    compile_regex,
    sanitize_for_csv_export,
    validate_regex_pattern,
)


@api_view(["GET"])
def health(request):
    return Response({"status": "ok"})


@api_view(["POST"])
def upload_file(request):
    uploaded = request.FILES.get("file")
    if not uploaded:
        return Response(
            {
                "error": 'No file was uploaded. Expected a file in the "file" field.',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        ext = parsing.validate_extension(uploaded.name)
        df = parsing.read_uploaded_tabular(uploaded, ext)
        parsing.assert_non_empty(df)
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    file_id = save_dataframe(df)
    preview_rows = parsing.preview_records(df, 10)
    columns = [str(c) for c in df.columns.tolist()]
    detected_text_columns = parsing.text_column_names(df)
    warnings = parsing.long_text_warnings(df)

    return Response(
        {
            "file_id": file_id,
            "columns": columns,
            "preview_rows": preview_rows,
            "detected_text_columns": detected_text_columns,
            "warnings": warnings,
        }
    )


@api_view(["POST"])
def generate_pattern(request):
    serializer = GeneratePatternSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "error": "Invalid request body.",
                "details": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    file_id = serializer.validated_data["file_id"]
    column_name = serializer.validated_data["column_name"]
    natural_language_prompt = serializer.validated_data["natural_language_prompt"]

    df = get_dataframe(file_id)
    if df is None:
        return Response(
            {"error": "Unknown or expired file_id. Upload the file again."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if column_name not in df.columns:
        return Response(
            {"error": "Column not found in the uploaded file."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not settings.OPENAI_API_KEY:
        return Response(
            {
                "error": "LLM is not configured. Set OPENAI_API_KEY in the environment.",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    series = df[column_name]
    if not parsing.has_non_empty_values(series):
        return Response(
            {
                "error": "Selected column has no non-empty values to infer a pattern from.",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )
    samples = collect_prompt_samples(series)

    try:
        raw = call_llm_for_regex(
            column_name, natural_language_prompt, samples
        )
        pattern_str, explanation, warnings = normalize_llm_regex_payload(raw)
    except LlmInvocationError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_502_BAD_GATEWAY,
        )

    try:
        validate_regex_pattern(pattern_str)
        compiled = re.compile(pattern_str)
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except re.error as exc:
        return Response(
            {
                "error": "The model returned an invalid regular expression. It cannot be compiled with Python's re module.",
                "detail": str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if not explanation:
        explanation = "Pattern generated from your description."

    sample_matches = collect_sample_matches(series, compiled)

    return Response(
        {
            "regex_pattern": pattern_str,
            "explanation": explanation,
            "warnings": warnings,
            "sample_matches": sample_matches,
        }
    )


@api_view(["POST"])
def apply_transform(request):
    serializer = ApplyTransformSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(
            {
                "error": "Invalid request body.",
                "details": serializer.errors,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    file_id = serializer.validated_data["file_id"]
    column_name = serializer.validated_data["column_name"]
    regex_pattern = serializer.validated_data["regex_pattern"].strip()
    replacement_value = serializer.validated_data.get("replacement_value", "")
    if replacement_value is None:
        replacement_value = ""
    flag_list = list(dict.fromkeys(serializer.validated_data.get("flags") or []))

    df_orig = get_dataframe(file_id)
    if df_orig is None:
        return Response(
            {"error": "Unknown or expired file_id. Upload the file again."},
            status=status.HTTP_404_NOT_FOUND,
        )
    if column_name not in df_orig.columns:
        return Response(
            {"error": "Column not found in the uploaded file."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        compiled = compile_regex(regex_pattern, flag_list)
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except re.error as exc:
        return Response(
            {
                "error": "Invalid regular expression. It cannot be compiled with Python's re module.",
                "detail": str(exc),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        df_transformed, matched_cells_count, changed_rows_count = apply_regex_to_column(
            df_orig,
            column_name,
            compiled,
            replacement_value,
        )
    except ValueError as exc:
        return Response(
            {"error": str(exc)},
            status=status.HTTP_400_BAD_REQUEST,
        )

    transformed_preview = parsing.preview_records(df_transformed, 10)

    buffer = io.StringIO()
    sanitize_for_csv_export(df_transformed).to_csv(buffer, index=False)
    csv_bytes = buffer.getvalue().encode("utf-8")
    export_id = save_export_csv(csv_bytes)

    downloadable_file_url = f"/api/download/{export_id}/"

    return Response(
        {
            "transformed_preview": transformed_preview,
            "matched_cells_count": matched_cells_count,
            "changed_rows_count": changed_rows_count,
            "downloadable_file_url": downloadable_file_url,
        }
    )


@api_view(["GET"])
def download_export(request, export_id: str):
    blob = get_export_csv(export_id)
    if blob is None:
        return Response(
            {"error": "Download not found or expired. Run apply again."},
            status=status.HTTP_404_NOT_FOUND,
        )
    return FileResponse(
        io.BytesIO(blob),
        as_attachment=True,
        filename="transformed.csv",
        content_type="text/csv; charset=utf-8",
    )
