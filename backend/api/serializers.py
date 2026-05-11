from rest_framework import serializers
from django.conf import settings


class GeneratePatternSerializer(serializers.Serializer):
    file_id = serializers.CharField(max_length=64, min_length=8)
    column_name = serializers.CharField(max_length=512)
    natural_language_prompt = serializers.CharField(
        min_length=1,
        max_length=8000,
        trim_whitespace=True,
    )


class ApplyTransformSerializer(serializers.Serializer):
    file_id = serializers.CharField(max_length=64, min_length=8)
    column_name = serializers.CharField(max_length=512)
    regex_pattern = serializers.CharField(
        min_length=1,
        max_length=settings.MAX_REGEX_PATTERN_LENGTH,
    )
    replacement_value = serializers.CharField(
        max_length=settings.MAX_REPLACEMENT_CHARS,
        allow_blank=True,
        required=False,
        default="",
    )
    flags = serializers.ListField(
        child=serializers.ChoiceField(
            choices=["IGNORECASE", "MULTILINE", "DOTALL", "VERBOSE"]
        ),
        required=False,
        allow_empty=True,
        default=list,
    )
