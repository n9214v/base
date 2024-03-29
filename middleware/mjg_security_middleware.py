from django.shortcuts import redirect
from ..services import utility_service, message_service, validation_service, auth_service
from ..classes.log import Log
from ..models.utility.xss_attempt import XssAttempt
from django.urls import reverse
from django.http import HttpResponseForbidden, HttpResponse

log = Log()


def xss_prevention(get_response):
    def script_response(param, value, is_ajax, path):

        # Log the suspicious parameter
        log.error(f"Potential XSS attempt in '{param}' parameter")
        log.info(f"\n{value}\n")

        auth_user = auth_service.get_authenticated_user().django_user()

        # Store attempt in database.
        xss_instance = XssAttempt(
            path=path,
            user=auth_user if auth_user and auth_user.id else None,
            parameter_name=param,
            parameter_value=value
        )
        xss_instance.save()

        # ToDo: Also log it in the audit table.
        # xxx.audit_event('xss_attempt', comments=f"Created XSS attempt record #{xss_instance.id}")

        if is_ajax:
            # Generate a "posted message" to display on the view
            message_service.post_error("Suspicious input detected. Unable to process request.")

            # Return as failure for AJAX calls
            return HttpResponseForbidden()
        else:
            return redirect('base:xss_block')

    def xss_middleware(request):

        # Gather conditions and values used later
        is_ajax = utility_service.is_ajax()
        is_terminating_impersonation = request.path == reverse('base:stop_impersonating')
        is_logging_out = request.path == reverse('account_logout')
        is_health_check = utility_service.is_health_check()
        is_posted_messages = request.path == reverse('base:messages')
        is_xss_lock = request.path == reverse('base:xss_lock')

        user = auth_service.get_django_user()
        user_id = user.id if user else None

        # Script_response will return a redirect.  If there are multiple XSS attempts, all attempts
        # should be logged, but only one return is needed. Store it in a variable while iterating.
        script_response_value = None

        # Iterate through GET parameters
        for param, value in request.GET.items():
            if validation_service.contains_script(value):
                # If XSS attempt found, log it and get a Redirect
                script_response_value = script_response(param, value, is_ajax, request.path)

        # Iterate through POST parameters
        for param, value in request.POST.items():
            if validation_service.contains_script(value):
                # If XSS attempt found, log it and get a Redirect
                script_response_value = script_response(param, value, is_ajax, request.path)

        # If xss was found, return the Redirect to the blocking page
        if script_response_value is not None:
            return script_response_value

        # If not already loading the lock page (and not an AWS health check)
        if user_id is not None and not (is_xss_lock or is_health_check or is_posted_messages):
            # Locked out users may logout or stop impersonating
            if not(is_terminating_impersonation or is_logging_out):
                # Count the number of un-reviewed XSS attempts for this user
                attempts = len(XssAttempt.objects.filter(user=user, reviewer__isnull=True))
                # After 3 attempts, user is locked out of site
                if attempts >= 3:
                    return redirect('base:xss_lock')

        # Otherwise, continue normally (and add XSS-Protection header)
        response = get_response(request)
        if type(response) is HttpResponse:
            response['X-XSS-Protection'] = "1"

            # Also add Cache-control: no-store and Pragma: no-cache headers (recommended by security team)
            response['Cache-Control'] = "no-store"
            response['Pragma'] = "no-cache"
        else:
            log.info(f"Security headers not added to {type(response)}")

        return response

    return xss_middleware
