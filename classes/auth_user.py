from .log import Log
from ..services import utility_service, error_service
from ..classes.dynamic_role import DynamicRole
from django.contrib.auth.models import User
from ..models.contact.contact import Contact
from django.db.models import Q
from datetime import datetime
log = Log()


class AuthUser:
    # Simple properties
    is_authenticated = None
    first_name = None
    last_name = None
    username = None
    email = None
    is_proxied = None

    # Authority Codes
    authorities = None

    # Holders for other classes
    user_instance = None
    contact_instance = None

    # Functions...

    def django_user(self):
        self._get_user_instance()
        return self.user_instance

    @property
    def id(self):
        try:
            return self.django_user().id
        except Exception as ee:
            log.trace([self])
            log.error(ee)

    def contact(self):
        self._get_contact_instance()
        return self.contact_instance

    def display_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def has_authority(self, authority_list):
        """
        Does this user have the specified authority?
        If a list of authorities is given, only one of the authorities is required
        """
        try:
            # If user has no authorities, no need to process anything
            if not self.authorities:
                return False

            # If not already a list, make it so
            if type(authority_list) is not list:
                if ',' in authority_list:
                    authority_list = utility_service.csv_to_list(authority_list)
                else:
                    authority_list = [authority_list]

            # Expand out any dynamic roles
            master_list = []
            for authority_code in authority_list:
                if authority_code.startswith('~'):
                    master_list.extend(DynamicRole().get(authority_code))
                else:
                    master_list.append(authority_code)
            del authority_list

            # Look for any one matching authority
            for authority_code in master_list:
                if authority_code.lower() in self.authorities:
                    return True
        except Exception as ee:
            error_service.record(ee, "Error checking user authorities")

        # False if not found
        return False

    def is_logged_in(self):
        # Do not count a proxied user as logged in
        if self.is_proxied:
            return False

        if self.is_authenticated is not None:
            return self.is_authenticated

        self._get_user_instance()
        self.is_authenticated = self.user_instance and self.user_instance.is_authenticated
        return self.is_authenticated

    def is_valid(self):
        return self.email is not None

    def to_dict(self):
        return {
            'is_authenticated': self.is_authenticated,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'username': self.username,
            'email': self.email,
            'is_proxied': self.is_proxied,
            'authorities': self.authorities,
        }

    def __init__(self, user_data):
        # If anonymous
        if user_data is None:
            self.is_authenticated = False
            self.first_name = 'Anonymous'
            self.authorities = []
            return

        # If resuming
        elif type(user_data) is dict:
            self.is_authenticated = user_data.get('is_authenticated')
            self.first_name = user_data.get('first_name')
            self.last_name = user_data.get('last_name')
            self.email = user_data.get('email')
            self.username = user_data.get('username')
            self.is_proxied = user_data.get('is_proxied')
            self.authorities = user_data.get('authorities')
            return

        # New from Django User
        elif type(user_data) is User or 'django' in str(type(user_data)):
            log.trace([user_data])
            self.user_instance = user_data
            self._populate_from_user()

        # New from Django User ID
        elif str(user_data).isnumeric():
            log.trace([user_data])
            try:
                self.user_instance = User.objects.get(pk=user_data)
                self._populate_from_user()
            except User.DoesNotExist:
                self.user_instance = None

        # New from email
        elif '@' in user_data:
            log.trace([user_data])
            self.email = user_data
            self._get_user_instance()
            # If not found, email is not associated with a user
            if not self.user_instance:
                self.email = None
            else:
                self._populate_from_user()
        
    def _populate_from_user(self, get_related=True):
        if self.user_instance:
            self.is_authenticated = self.user_instance.is_authenticated
            self.first_name = self.user_instance.first_name
            self.last_name = self.user_instance.last_name
            self.email = self.user_instance.email
            self.username = self.user_instance.username
            if get_related:
                self._populate_authorities()
                self._get_contact_instance()

    def _populate_authorities(self, force=False):
        if force or self.authorities is None:
            self.authorities = {}
            self._get_user_instance()
            if self.user_instance and self.is_authenticated:
                log.trace()
                try:
                    now = datetime.now()
                    permissions = self.user_instance.permissions.filter(Q(effective_date__isnull=True) | Q(effective_date__lte=now))
                    permissions = permissions.filter(Q(end_date__isnull=True) | Q(end_date__gt=now))
                    if permissions:
                        for pp in permissions:
                            self.authorities[pp.authority.code] = pp.authority.title
                except Exception as ee:
                    error_service.record(ee, f"Error retrieving permissions for {self.email}")

    def _get_user_instance(self):
        if not self.user_instance:
            try:
                self.user_instance = User.objects.get(email=self.email)
            except User.DoesNotExist:
                self.user_instance = None
            except Exception as ee:
                error_service.record(ee, self)

    def _get_contact_instance(self):
        if self.contact_instance:
            return

        # Contact is linked to User
        self._get_user_instance()
        if not self.user_instance:
            return

        # Get contact from User
        log.trace()
        try:
            self.contact_instance = self.user_instance.contact
        except:
            self.contact_instance = None

        # If no linked contact, search for existing one
        if not self.contact_instance:
            self.contact_instance = Contact.get(self.email)
            # If found, update user to match Contact
            if self.contact_instance:
                self.user_instance.first_name = self.contact_instance.first_name
                self.user_instance.last_name = self.contact_instance.last_name
                self.user_instance.save()
                self.contact_instance.user = self.user_instance
                self.contact_instance.save()
                # Refresh self with updated info
                self._populate_from_user(get_related=False)
                return
    
        # Create a new contact if needed
        if not self.contact_instance:
            # First and last are required, but may not exist in user object
            placeholder = self.user_instance.username
            if not placeholder:
                placeholder = self.user_instance.email.split('@')[0] if self.user_instance.email else None
            self.contact_instance = Contact()
            self.contact_instance.user = self.user_instance
            self.contact_instance.first_name = self.first_name if self.first_name else placeholder
            self.contact_instance.last_name = self.last_name if self.last_name else placeholder
            self.contact_instance.email = self.email
            self.contact_instance.save()
            return

    def __str__(self):
        return f"{self.first_name} {self.last_name} <{self.email}>".strip()

    def __repr__(self):
        return str(self)
