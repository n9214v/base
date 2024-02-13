from .log import Log
from ..services import utility_service, message_service
from .auth_user import AuthUser
log = Log()

session_var = "auth_tracking_dict"


class Auth:
    authenticated_user = None
    impersonated_user = None
    proxied_user = None

    def is_logged_in(self):
        return self.authenticated_user and self.authenticated_user.is_logged_in()

    def is_impersonating(self):
        return self.impersonated_user

    def is_proxying(self):
        return self.proxied_user

    def get_user(self):
        if self.is_impersonating():
            return self.impersonated_user
        else:
            return self.authenticated_user

    def get_django_user(self):
        if self.is_impersonating():
            return self.impersonated_user.django_user()
        else:
            return self.authenticated_user.django_user()

    def save(self):
        self._clean_users()
        utility_service.set_session_var(session_var, self._to_dict())

    def can_impersonate(self):
        return self.authenticated_user.has_authority('~impersonate')

    def set_impersonated_user(self, user_data):
        if self.can_impersonate():
            if self.is_impersonating():
                message_service.post_info(f"""
                <span class="fa fal fa-user-secret"></span> 
                No longer impersonating {self.impersonated_user.display_name()}
                """)
            self.reset_session()
            if user_data is None:
                return True
            iu = AuthUser(user_data)
            if iu and iu.is_valid():
                self.impersonated_user = iu
                self.save()

                message_service.post_info(f"""
                <span class="fa fal fa-user-secret"></span> 
                Impersonating {self.impersonated_user.display_name()}
                """)
                return True
            else:
                message_service.post_error("Could not find the specified user to impersonate")
        return False

    def set_proxied_user(self, user_data):
        if self.get_user().has_authority("~proxy"):

            if self.is_proxying():
                message_service.post_info(f"""
                <span class="fa fal fa-user-minus"></span> 
                No longer proxying {self.proxied_user.display_name()}
                """)

            if user_data is None:
                self.proxied_user = None
                self.save()
                return True

            pu = AuthUser(user_data)
            if pu and pu.is_valid():
                pu.is_proxied = True
                self.proxied_user = pu
                self.save()

                message_service.post_info(f"""
                <span class="fa fal fa-user-plus"></span> 
                Proxying {self.proxied_user.display_name()}
                """)
                return True
            else:
                message_service.post_error("Could not find the specified user to proxy")
        return False

    def reset_session(self):
        utility_service.clear_custom_session_vars()
        self.impersonated_user = None
        self.proxied_user = None
        self.save()

    def __init__(self, resume=True):
        # Get Django.auth.User
        request = utility_service.get_request()
        user_instance = request.user

        # If user is not authenticated, there is nothing to process
        if not user_instance.is_authenticated:
            self.authenticated_user = AuthUser(None)
            self._clean_users()
            return

        # Resume from session
        # ===============================================================
        if resume:
            self._resume()

            # If authentication has not changed, no further processing required
            if self.authenticated_user and user_instance.email == self.authenticated_user.email:
                self._clean_users()
                return

        # Generate new auth data
        # ===============================================================
        self.authenticated_user = AuthUser(user_instance)
        self.impersonated_user = None
        self.proxied_user = None
        self.save()

    def _resume(self):
        data = utility_service.get_session_var(session_var)
        if data:
            for au in ['authenticated_user', 'impersonated_user', 'proxied_user']:
                if data.get(au):
                    setattr(self, au, AuthUser(data.get(au)))

    def _to_dict(self):
        return {
            'authenticated_user': self.authenticated_user.to_dict() if self.authenticated_user else None,
            'impersonated_user': self.impersonated_user.to_dict() if self.impersonated_user else None,
            'proxied_user': self.proxied_user.to_dict() if self.proxied_user else None,
        }

    def _clean_users(self):
        if (not self.authenticated_user) or (not self.authenticated_user.is_valid()):
            self.authenticated_user = AuthUser(None)
        if self.impersonated_user and not self.impersonated_user.is_valid():
            self.impersonated_user = None
        if self.proxied_user and not self.proxied_user.is_valid():
            self.proxied_user = None
