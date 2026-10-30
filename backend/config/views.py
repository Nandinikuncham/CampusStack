from django.http import JsonResponse


def csrf_failure(request, reason=""):
    """Return API-shaped CSRF errors without disclosing middleware diagnostics."""
    return JsonResponse({"detail": "CSRF verification failed."}, status=403)
