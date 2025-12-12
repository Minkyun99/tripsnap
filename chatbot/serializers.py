from rest_framework import serializers

class ChatInitSerializer(serializers.Serializer):
    preference = serializers.CharField(max_length=100)
    region = serializers.CharField(max_length=100, required=False, allow_blank=True)
    dates = serializers.CharField(max_length=100, required=False, allow_blank=True)
    transport = serializers.CharField(max_length=100, required=False, allow_blank=True)
