from django.apps import AppConfig
from django.conf import settings

# Default settings
_DEFAULTS = {
    'AUTHORIZE_GLOBAL': False,      # Allow authorizing for other apps?

    # Admin Menu Items
    'MJG_BASE_ADMIN_LINKS': [
        {'url': "base:status", 'label': "Status Page", 'icon': "fa-medkit"},
        {'url': "base:manage_authorities", 'label': "Authorities", 'icon': "fa-lock-alt", 'authorities': "~security_admin"},
        {'url': "base:manage_users", 'label': "User Accounts", 'icon': "fa-users-cog", 'authorities': "~security_admin"},
        {'url': "base:contact_list", 'label': "Contacts", 'icon': "fa-address-book", 'authorities': "~contact_admin"},
        # {'url': "base:errors", 'label': "Error Log", 'icon': "fa-exclamation-triangle", 'authorities': "DynamicSuperUser"},
        # {'url': "base:emails", 'label': "Email Log", 'icon': "fa-envelope-o"},
        {'url': "base:features", 'label': "Feature Toggles", 'icon': "fa-toggle-on", 'authorities': "~superuser"},
        # {'url': "base:audit", 'label': "Audit Events", 'icon': "fa-id-card-o", 'authorities': "DynamicSecurityOfficer"},
        # {'url': "base:audit_xss", 'label': "XSS Attempts", 'icon': "fa-user-secret", 'authorities': "DynamicSecurityOfficer"},
        # {'url': "base:finti", 'label': "Finti Interface", 'icon': "fa-laptop", 'authorities': "developer", 'feature': "finti_console", 'nonprod_only': True},
        # {'url': "base:session", 'label': "Session Contents", 'icon': "fa-microchip", 'authorities': "developer"},
        # {'url': "base:email", 'label': "Send Test Email", 'icon': "fa-paper-plane-o", 'authorities': "developer"},
        # {'url': "base:scripts", 'label': "Admin Script", 'icon': "fa-code", 'authorities': "DynamicSuperUser+scriptor", 'feature': 'admin_script'},
        {'url': "base:export_db", 'label': "Database Export", 'icon': "fa-database", 'authorities': "developer"},
    ]
}


class MjgBaseConfig(AppConfig):
    name = 'mjg_base'
    verbose_name = "MJG Base Plugin"

    def ready(self):
        # Use mjg_base middleware
        request_middleware = 'crequest.middleware.CrequestMiddleware'
        base_middleware = 'mjg_base.middleware.mjg_base_middleware.MjgBaseMiddleware'
        xss_middleware = 'mjg_base.middleware.mjg_security_middleware.xss_prevention'
        for mm in [request_middleware, base_middleware, xss_middleware]:
            if mm not in settings.MIDDLEWARE:
                settings.MIDDLEWARE.append(mm)

    # Assign default setting values
    for key, value in _DEFAULTS.items():
        try:
            getattr(settings, key)
        except AttributeError:
            setattr(settings, key, value)
        # Suppress errors from DJANGO_SETTINGS_MODULE not being set
        except:
            pass