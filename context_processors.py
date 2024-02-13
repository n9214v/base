from .services import utility_service, auth_service
from .classes.log import Log
from .classes.breadcrumb import Breadcrumb
from django.conf import settings

log = Log()


def util(request):
    # Build an absolute URL (for use in emails)
    absolute_root_url = "{0}://{1}".format(request.scheme, request.get_host())
    if 'http://' in absolute_root_url and 'localhost' not in absolute_root_url:
        absolute_root_url = absolute_root_url.replace('http://', 'https://')

    breadcrumbs = []
    for bc in utility_service.get_breadcrumbs():
        breadcrumbs.append(Breadcrumb(bc))

    model = {
        'absolute_root_url': absolute_root_url,

        # The home URL (path) depends on existence of URL Context
        'home_url': '/',
        'mjg_plugins': utility_service.get_installed_plugins(),

        # Prod vs Nonprod
        'is_production': utility_service.is_production(),
        'is_non_production': utility_service.is_non_production(),
        'is_development': utility_service.is_development(),

        # Breadcrumbs (can be set in the view with utility_service functions)
        'breadcrumbs': breadcrumbs,

        # Posted messages at top of page by default. Setting option allows moving them to the bottom
        'posted_message_position': getattr(settings, 'POSTED_MESSAGE_POSITION', 'TOP').upper()
    }

    # Get admin links for any installed MJG plugins, and the current app
    plugin_admin_links = []
    apps = utility_service.get_installed_plugins()
    apps.update({utility_service.get_app_code().lower(): utility_service.get_app_version()})
    for plugin, version in apps.items():
        if plugin.lower().startswith("django"):
            continue
        setting_name = f"{plugin.upper().replace('-', '_')}_ADMIN_LINKS"
        try:
            this_link_list = getattr(settings, setting_name)
            plugin_admin_links.extend(this_link_list)
        except AttributeError as ee:
            try:
                exec(f"from {plugin} import _DEFAULTS as {plugin}_defaults")
                these_links = eval(f"{plugin}_defaults['{setting_name}']")
                if these_links:
                    plugin_admin_links.extend(these_links)
            except Exception as ee:
                pass

    model['plugin_admin_links'] = sorted(plugin_admin_links, key=lambda i: i['label'])
    return model


def auth(request):
    auth_instance = auth_service.get_auth_instance()
    return {
        'is_authenticated': auth_instance.is_logged_in(),
        'is_logged_in': auth_instance.is_logged_in(),
        'current_user': auth_instance.get_user(),
        'authenticated_user': auth_instance.authenticated_user,
        'proxied_user': auth_instance.proxied_user,
        'can_impersonate': auth_instance.can_impersonate(),
        'is_impersonating': auth_instance.is_impersonating(),
        'can_proxy': auth_instance.get_user().has_authority('~proxy'),
        'is_proxying': auth_instance.is_proxying(),
        'avatar_url': auth_service.get_avatar_url(),
    }
