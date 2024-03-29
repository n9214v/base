#
# The unexpected error function required a new service because its use of
# auth_service resulted in circular imports when it was added to message_service
#

from django.conf import settings
from ..classes.log import Log
from inspect import getframeinfo, stack
from ..services import auth_service
# from ..models.error import Error
from crequest.middleware import CrequestMiddleware
from . import message_service
import os
import traceback

log = Log()


def record(ee, debug_info=None):
    """Shortcut for when you want a detailed log of the error without posting an error message"""

    # During local development, post the error so it doesn't get overlooked
    local_development = getattr(settings, 'ENVIRONMENT').upper() == 'DEV'
    if local_development:
        icon = 'fa-bug'
        unexpected_error(f"{icon} Bug recorded: {ee}", ee, debug_info)

    else:
        unexpected_error(None, ee, debug_info)


def unexpected_error(error_display=None, error_system=None, debug_info=None):
    """
    Logs the error in the db, the log file, and posts an error on-screen
    This service cannot use auth_service (circular import), so user must be provided if you want it logged
    """

    # Gather data
    src = get_caller_data()
    request = CrequestMiddleware.get_request()
    path = request.path if request else '?'
    method = request.method if request else None

    try:
        browser = request.META['HTTP_USER_AGENT']
    except:
        browser = 'Unknown'

    # Don't record health-check errors
    # Finti downtimes clutter the error page
    if browser and 'ELB-HealthChecker' in browser:
        if error_display:
            log.error(f"ELB-HealthCheck: {error_display}", trace_error=False)
        if error_system:
            log.error(f"ELB-HealthCheck: {error_system}", trace_error=False)
        return

    # Include parameters in error log
    parameters = _get_parameters()
    if not parameters:
        parameters = None  # To avoid "{}"
    # CSRF token is long and unhelpful. Remove it when present.
    elif 'csrfmiddlewaretoken' in parameters:
        del parameters['csrfmiddlewaretoken']

    # Gather user authentication data
    auth = auth_service.get_auth_instance()
    user_label = 'Anonymous'
    if auth.is_logged_in():
        user_label = auth.authenticated_user.display_name()
    if auth.is_impersonating():
        user_label += f" as {auth.impersonated_user.display_name()}"
    if auth.is_proxying():
        user_label += f" on behalf of {auth.proxied_user.display_name()}"

    # Get stacktrace
    stacktrace = traceback.format_exc(limit=10)

    # Log error in log file
    log.error(
        f"""\n
\t*** UNEXPECTED ERROR ***
\tSystem Error:   {error_system}
\tFriendly Error: {error_display}
\tDebug Info: {debug_info}
\tBrowser: {browser}
\tUser: {user_label}
\tRequest Path:   {f"[{method}] " if method else ''}{path}
\tParameters:     {parameters}
\tRaised From:    {src}

{stacktrace}
        """,
        trace_error=False
    )

    # ToDo: Log error in database
    # try:
    #     ee = Error()
    #     ee.app_code = getattr(settings, 'APP_CODE')
    #     ee.path = str(path)[:128] if path else path
    #     ee.parameters = str(parameters)[:500] if parameters else parameters
    #     ee.code_detail = str(src)[:128] if src else src
    #     ee.sso_user = auth.sso_user.username if auth.sso_user else None
    #     ee.browser = browser[:200] if browser else browser
    #     ee.impersonated_user = auth.impersonated_user.username if auth.impersonated_user else None
    #     ee.proxied_user = auth.proxied_user.username if auth.proxied_user else None
    #     ee.error_friendly = str(error_display)[:128] if error_display else error_display
    #     ee.error_system = str(error_system)[:128] if error_system else error_system
    #     ee.debug_info = str(debug_info)[:128] if debug_info else debug_info
    #     ee.stacktrace = stacktrace
    #     ee.save()
    # except Exception as ee:
    #     log.warning(f"Unexpected error was not saved in database: {str(ee)}")

    # Post friendly error to the screen
    if error_display:
        message_service.post_error(error_display)


def get_caller_data():
    """Return the calling code as (file-name, line-number, function-name)"""
    try:
        # Ignore this function, and the error_service.<function> that called it
        depth = 2

        # Get the info about the function that generated the message
        caller = getframeinfo(stack()[depth][0])

        # In case of nested functions within this class, may need to look deeper
        try:
            cf = caller.filename
            while cf.endswith("message_service.py") or cf.endswith("error_service.py"):
                depth += 1
                caller = getframeinfo(stack()[depth][0])
                cf = caller.filename
        except Exception as ee:
            log.warning(
                f"Unable to navigate nested functions in error_service.get_caller_data(): {ee}"
            )

        return f"{os.path.basename(caller.filename)}.{caller.function}() at line {caller.lineno}"

    except Exception as ee:
        log.warning("Unable to get file/function/line at which the error occurred.")
        return "Unknown"


def _get_parameters():
    """Get parameters as dict. This is mostly for logging parameters."""
    request = CrequestMiddleware.get_request()
    if request:
        pp = request.GET.items() if request.method == 'GET' else request.POST.items()
        return {kk: vv for kk, vv in pp}
    return None
