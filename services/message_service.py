from ..classes.log import Log
from . import utility_service
from django.contrib import messages
import re

log = Log()


def post_info(msg, add_icon=True):
    return post_message(msg, "info", add_icon=add_icon)


def post_success(msg, add_icon=True):
    return post_message(msg, "success", add_icon=add_icon)


def post_warning(msg, add_icon=True):
    return post_message(msg, "warning", add_icon=add_icon)


def post_error(msg, add_icon=True):
    return post_message(msg, "error", add_icon=add_icon)


def post_delayed_message(msg, level):
    """
    Post a message the next time a page is loaded (after the current page)
    Use case: An AJAX request encounters an error that will require a full page reload.  In this case,
    the posted messages would post, then a Javascript refresh would immediately clear the message from the screen.
    This function holds the message in the flash scope and posts it after the JS-initiated refresh.
    LIMIT 1 MESSAGE PER TYPE (info, warning, etc)
    """
    log.trace([msg, level])
    utility_service.set_flash_scope(f"delayed_message:{level.lower()}", msg)


def post_message(msg, msg_type, add_icon=True):
    request = utility_service.get_request()
    message = str(msg)
    msg_level = getattr(messages, msg_type.upper())

    if request is None:
        log.error(f"Request does not exist. Could not post message: {message}")
    else:
        # Look through messages without clearing them
        msg_list = messages.get_messages(request)
        duplicate_flag = message in [m.message for m in msg_list if m.level == msg_level]
        msg_list.used = False

        # If message is a duplicate, do not post it
        if duplicate_flag:
            log_msg = f"[DUPLICATE] {msg}"
        else:
            log_msg = f"[POSTED] {msg}"

            # Convert fa-class to a FontAwesome icon
            contains_icon = False
            prefix = ""
            for ww in re.split(r'[^\w-]', message):
                if ww in ["fas", "far",  "fal", "fad"]:
                    prefix = ww
                    message = message.replace(f"{prefix} fa-", "fa-")
                    continue
                if ww.startswith("fa-"):
                    message = message.replace(ww, f"""<i class="fa {prefix} {ww}" aria-hidden="true"></i>""")
                    contains_icon = True

            if add_icon and not contains_icon:
                std_icons = {
                    "success": "fal fa-comment-smile",
                    "info": "fal fa-comment-lines",
                    "warning": "fal fa-comment-exclamation",
                    "error": "fal fa-comment-times",
                }
                log.debug(f"Level: {msg_type} Gets icon: {std_icons.get(msg_type)}")
                message = f"""<i class="fa {std_icons.get(msg_type)}" aria-hidden="true"></i> {message}"""

            messages.add_message(request, msg_level, message)

        # Always log it (including duplicates)
        if msg_type == "error":
            log.error(log_msg, trace_error=False, strip_html=True)
        elif msg_type == "warning":
            log.warning(log_msg, strip_html=True)
        else:
            log.info(log_msg, strip_html=True)

    return None
