import requests
from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response


@api_view(["POST"])
def chat(request):
    # LLM API URL 配置
    if not settings.BK_MONITOR_AI_API_URL:
        return Response({'error': 'AI assistant is not configured'}, status=status.HTTP_501_NOT_IMPLEMENTED)

    url = f"{settings.BK_MONITOR_AI_API_URL}/api/chat/"

    try:
        response = requests.post(url, json=request.data, stream=True)
        response.raise_for_status()
    except requests.exceptions.RequestException as e:
        return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def event_stream():
        for line in response.iter_lines(chunk_size=10):
            if line:
                result = line.decode('utf-8') + '\n\n'
                yield result

    # 返回 StreamingHttpResponse
    sr = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    sr.headers["Cache-Control"] = "no-cache"
    sr.headers["X-Accel-Buffering"] = "no"
    return sr
