from django.shortcuts import render
from ..classes.log import Log
from ..services import date_service, utility_service
import time
from datetime import datetime

log = Log()


def messages(request):
    return render(
        request,
        'base/template/messages/messages.html',
        {'message_birth_date': int(time.time())}
    )


def status_page(request):
    session_data = {
        'expiry_seconds': request.session.get_expiry_age(),
        'expiry_description': date_service.seconds_to_duration_description(request.session.get_expiry_age())
    }
    return render(
        request, 'base/status_page.html',
        {
            'dev_test_content': int(time.time()),
            'server_time': datetime.now(),
            'session_data': session_data,
            'installed_plugins': utility_service.get_installed_plugins(),
        }
    )

