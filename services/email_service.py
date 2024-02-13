from . import auth_service
from . import utility_service
from . import message_service, error_service
from ..classes.log import Log
from django.template.loader import render_to_string
from django.core.mail import EmailMultiAlternatives
# from ..models.email import Email
from ..context_processors import util as util_context, auth as auth_context
from django.urls import reverse

log = Log()


def get_context(util=True, auth=True):
    """Get mjg_base context to include in all email context"""
    model = {}
    request = utility_service.get_request()
    if auth:
        model.update(auth_context(request))
    if util:
        model.update(util_context(request))
    return model


def get_absolute_url(*args):
    context = get_context(util=True, auth=False)
    if args:
        return f"{context['absolute_root_url']}{reverse(args[0], args=args[1:])}"
    else:
        return context['absolute_root_url']


def get_default_recipient():
    # When authenticated, default to authenticated user
    if auth_service.is_logged_in():
        sso_email = auth_service.get_authenticated_user().email
        return sso_email.lower() if sso_email else None

    # When non-authenticated in non-production, allow a default address to be specified and stored in the session
    elif utility_service.is_non_production():
        return utility_service.get_session_var("base_default_recipient")

    # Otherwise, there is no default recipient
    return None


def set_default_email(default_recipient):
    """
    When non-authenticated in non-production, a default recipient can be specified and stored in the session
    (this helps test emails for non-authenticated situations, like Dual Credit Applications)
    """
    utility_service.set_session_var("base_default_recipient", default_recipient)


def get_testing_emails():
    """
    Get email addresses that are allowed to receive non-production emails.
    """
    return utility_service.get_setting("NONPROD_EMAILS", [])


def send(
        subject=None,
        content=None,
        sender=None,  # Can format: "Display Name <someone@pdx.edu>"
        to=None,
        cc=None,
        bcc=None,
        email_template=None,
        context=None,
        max_recipients=10,  # We rarely email more than 10 people. Exceptions should have to specify how many
        suppress_success_message=False,  # Do not notify user on successful send (but notify if send failed)
        suppress_status_messages=False,  # Do not notify user upon successful or failed send
        include_context=True,  # Include context included on all pages (current user, environment, etc)
        sender_display_name=None,  # Shortcut for: "Display Name <someone@pdx.edu>",
):
    log.trace([subject])
    invalid = False
    error_message = None

    # If sender not specified, use the default sender address
    if not sender:
        sender = utility_service.get_setting('DEFAULT_FROM_EMAIL')

    if sender_display_name and "<" not in sender:
        sender = f"{sender_display_name} <{sender}>"

    # Subject should never be empty.  If it is, log an error and exit.
    if not subject:
        error_service.record("Email subject is empty!")
        return False

    # Non-prod emails should always point out that they're from non-prod
    if utility_service.is_non_production():
        env = utility_service.get_environment()
        prepend = f"[{env}] "
        if not (subject.startswith(env) or subject.startswith(prepend)):
            subject = f"{prepend}{subject}"

    to, cc, bcc, num_recipients = _prepare_recipients(to, cc, bcc)

    # Enforce max (and min) recipients
    if num_recipients == 0:
        error_message = f"Email failed validation: No Recipients"
        log.error(error_message)
        invalid = True
    elif num_recipients > max_recipients:
        error_message = f"Email failed validation: Too Many ({num_recipients} of {max_recipients}) Recipients"
        log.error(error_message)
        invalid = True

    # If a template has not been specified, use the base template
    # (Use template=False to not use a template)
    if email_template is None:
        email_template = 'base/emails/standard'
    # Will look for html and txt versions of the template
    template_no_ext = email_template.replace('.html', '').replace('.txt', '')
    template_html = f"{template_no_ext}.html"
    template_txt = f"{template_no_ext}.txt"

    # Standard template uses subject as page title (may not even matter?)
    if not context:
        context = {'subject': subject}
    elif 'subject' not in context:
        context['subject'] = subject

    # Standard template will print plain content inside the HTML template
    if content and 'content' not in context:
        context['content'] = content

    # Include standard context that mjg_base injects into all pages
    if include_context:
        context.update(get_context())

    # Render the template to a string (HTML and plain text)
    html = plain = None
    html_error = txt_error = False
    try:
        if template_html:
            html = render_to_string(template_html, context)
    except Exception as ee:
        log.error(f"Unable to render template: {template_html}")
        log.debug(str(ee))
        html_error = True
    try:
        if template_txt:
            plain = render_to_string(template_txt, context)
    except Exception as ee:
        if content:
            # Render the content as plain text
            plain = content
        else:
            log.warning(f"Unable to render plain-text template: {template_txt}")
            log.debug(str(ee))
            txt_error = True

    # If both templates failed, then email cannot be sent
    if txt_error and html_error:
        invalid = False

    if invalid:
        log.warning(f"Email was not sent: {subject}")

    else:
        try:
            # Build the email
            email = EmailMultiAlternatives(
                subject=subject,
                body=plain,
                from_email=sender,
                to=to,
                cc=cc,
                bcc=bcc
            )

            # If there is an html version, attach it
            if html:
                email.attach_alternative(html, "text/html")

            # Send the email
            email.send()

        except Exception as ee:
            invalid = True
            log.error(ee)
            log.warning(f"Error sending email: {subject}")

    # Log the email
    status = 'F' if invalid else 'S'
    _record(
        subject=subject,
        content=content,
        sender=sender,
        to=to,
        cc=cc,
        bcc=bcc,
        email_template=email_template,
        context=context,
        max_recipients=max_recipients,
        status=status,
        error_message=error_message
    )

    # Generate a message, either for posting or logging
    if status == 'S':
        msg = ["<b>Email Sent</b><br />"]
    else:
        msg = ["<b>Unable to Send Email</b><br />"]

    msg.append('<div style="padding-left: 20px;">')

    # Include the subject
    msg.append('fal-envelope-o &nbsp;')
    msg.append(f"{subject}<br />")

    # And the recipients (if not too many). Do not display Bcc
    def list_to_str(ll):
        if len(ll) > 3:
            return "(multiple recipients)"
        else:
            return str(ll).replace("'", "").replace("[", '').replace("]", '').strip()
    #
    if to:
        msg.append(f"To: {list_to_str(to)}<br />")
    if cc:
        msg.append(f"Cc: {list_to_str(cc)}<br />")

    msg.append('</div>')

    # Combine to one string
    status_message = ''.join(msg)

    if not suppress_status_messages:
        # If success, and not suppressing success messages
        if status == 'S' and not suppress_success_message:
            message_service.post_success(status_message)
        elif status != 'S':
            message_service.post_warning(status_message)

    else:
        if status == 'S':
            log.info(status_message, strip_html=True)
        else:
            log.warning(status_message, strip_html=True)

    return status == 'S'


def _prepare_recipients(to, cc, bcc):
    """
    Used by send() to prepare the recipients in a unit-testable way
    """
    # Recipients should be in list format
    if type(to) is not list:
        to = [to]
    if type(cc) is not list:
        cc = [cc]
    if type(bcc) is not list:
        bcc = [bcc]

    def clean(address):
        return address.lower().replace(' ', '+')

    # Recipient lists should be unique. To assist with this, make all emails lowercase
    to = list(set([clean(address) for address in to if address]))
    cc = list(set([clean(address) for address in cc if address and clean(address) not in to]))
    bcc = list(set([clean(aa) for aa in bcc if aa and clean(aa) not in to and clean(aa) not in cc]))

    # Get the total number of recipients
    num_recipients = len(to) if to else 0
    num_recipients += len(cc) if cc else 0
    num_recipients += len(bcc) if bcc else 0

    # If this is non-production, remove any non-allowed addresses
    if utility_service.is_non_production() and num_recipients > 0:

        # In DEV, never send to anyone other than the default recipient
        if utility_service.is_development():
            testing_emails = []
        # In STAGE, use gtvsdax-defined testers from Finti
        else:
            testing_emails = get_testing_emails()

        default_recipient = get_default_recipient()
        allowed_to = [aa for aa in to if aa in testing_emails or aa == default_recipient]
        allowed_cc = [aa for aa in cc if aa in testing_emails or aa == default_recipient]
        allowed_bcc = [aa for aa in bcc if aa in testing_emails or aa == default_recipient]

        # Get the total number of allowed recipients
        num_allowed_recipients = len(allowed_to) if allowed_to else 0
        num_allowed_recipients += len(allowed_cc) if allowed_cc else 0
        num_allowed_recipients += len(allowed_bcc) if allowed_bcc else 0

        if num_allowed_recipients < num_recipients:
            not_allowed = {
                'to': [aa for aa in to if aa not in allowed_to],
                'cc': [aa for aa in cc if aa not in allowed_cc],
                'bcc': [aa for aa in bcc if aa not in allowed_bcc]
            }
            log.info(f"The following recipients were removed from the recipient list:\n{not_allowed}")

        if num_allowed_recipients == 0 and default_recipient:
            message_service.post_info(f"No allowed non-prod recipients. Redirecting to {default_recipient}.")
            allowed_to = [default_recipient]
            num_allowed_recipients = 1

        return allowed_to, allowed_cc, allowed_bcc, num_allowed_recipients

    else:
        return to, cc, bcc, num_recipients


def _record(subject, content, sender, to, cc, bcc, email_template, context, max_recipients, status=None, error_message=None):
    """
    Used by send() to record emails with enough data to be able to re-send them later if needed
    """
    log.trace()
    # ToDo: Record email attempts

    # email_instance = Email(
    #     app_code=utility_service.get_app_code(),
    #     url=utility_service.get_request().path,
    #     initiator=auth_service.get_auth_object().sso_user.username if auth_service.is_logged_in() else None,
    #     status=status,
    #     error_message=error_message[:128] if error_message else error_message,
    #     subject=subject[:128] if subject else subject,
    #     content=content[:4000] if content else content,
    #     sender=sender[:128] if sender else sender,
    #     to=str(to)[:4000] if to else None,
    #     cc=str(cc)[:4000] if cc else None,
    #     bcc=str(bcc)[:4000] if bcc else None,
    #     email_template=email_template[:128] if email_template else email_template,
    #     context=str(context)[:4000] if context else None,
    #     max_recipients=max_recipients
    # )
    # email_instance.save()
