from django.shortcuts import redirect
from ..services import utility_service, auth_service
from ..classes.log import Log
from django.urls import reverse

log = Log()


class MjgBaseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.
        log.debug("Using MJG Base")

    def process_view(self, request, view_func, view_args, view_kwargs):

        if request.user.is_authenticated:
            pass

        return None

    def __call__(self, request):
        # Is this an AWS health check or posted messages?
        posted_messages = request.path == reverse('base:messages')
        silence_logs = utility_service.is_health_check() or posted_messages

        if posted_messages:
            log.debug("Processing 'Posted Messages'...")

        # In non-prod, make the start of a new request more visible in the log (console)
        if not silence_logs:
            if utility_service.is_non_production():
                w = 80
                log.debug(f"\n{'='.ljust(w, '=')}\n{'New Request'.center(w)}\n{'='.ljust(w, '=')}")
            log.trace([request.path, auth_service.get_user()], request.method)
            if auth_service.has_authority('~power_user'):
                utility_service.set_session_var('allow_limited_features', True)

            # ToDo: Remove debug logging
            if request.path.startswith('/accounts'):
                if request.method == 'POST' and 'email' in request.POST:
                    log.info(f"Login Email: {request.POST.get('email')}")
                elif request.method == 'GET' and 'email' in request.GET:
                    log.info(f"Login Email: {request.GET.get('email')}")
                elif request.method == 'GET' and 'authuser' in request.GET:
                    log.info(f"Auth User: {request.GET.get('authuser')}")
                else:
                    log.debug(request.POST)
                    log.debug(request.GET)
            elif utility_service.is_non_production():
                if request.method == "POST":
                    log.debug(f"Parameters: { {k:v for k,v in request.POST.items() if k != 'csrfmiddlewaretoken'} }")

        # Remove flash variables from two requests ago. Shift flash variables from last request.
        # This happens for every request EXCEPT posting messages to the screen
        if not posted_messages:
            utility_service.cycle_flash_scope()

        # Render the response
        response = self.get_response(request)

        # After the view has completed
        utility_service.clear_page_scope()

        if not silence_logs:
            log.end(None, request.path)

        return response
