from django.db import models
from mjg_base.classes.log import Log
from django.contrib.auth.models import User
from mjg_base.services import message_service, validation_service

log = Log()


class Contact(models.Model):
    """
    Contact information (may be associated with a user account)
    """
    date_created = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Associated user account
    user = models.OneToOneField(User, models.SET_NULL, related_name="contact", blank=True, null=True)

    # Identity info
    first_name = models.CharField(max_length=60, blank=False, null=False)
    last_name = models.CharField(max_length=60, blank=False, null=False, db_index=True)

    # Multiple emails may exist for associated User, but there's only one Contact email
    email = models.CharField(max_length=150, blank=False, null=False, db_index=True, unique=True)

    # Additional identity info
    gender = models.CharField(max_length=1, blank=True, null=True)
    date_of_birth = models.DateField(blank=True, null=True)

    def display_name(self):
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        elif self.user.first_name or self.user.last_name:
            return f"{self.user.first_name} {self.user.last_name}".strip()
        elif self.email:
            return self.email
        elif self.user.email:
            return self.user.email
        elif self.user:
            return str(self.user)
        else:
            "Empty Contact"

    def set_first_name(self, name):
        if name:
            self.first_name = name
            if self.user:
                self.user.first_name = name
                self.user.save()
            return True

    def set_last_name(self, name):
        if name:
            self.last_name = name
            if self.user:
                self.user.last_name = name
                self.user.save()
            return True

    def set_email(self, email):
        if email:
            email = email.lower().strip()
            if email == self.email:
                return True  # No change
            if not validation_service.is_email_address(email):
                message_service.post_error("The given email address appears to be invalid")
                return False
            other_contact = Contact.get(email)
            if other_contact:
                message_service.post_error("That email is already in use by another person")
                log.warning(f"{other_contact} has email: {email}")
                return False
            self.email = email
            # ToDo: Add email to list of user emails
            if self.user:
                self.user.email = email
                self.user.save()
            return True

    @classmethod
    def get(cls, id_or_email):
        try:
            if str(id_or_email).isnumeric():
                return Contact.objects.get(pk=id_or_email)
            else:
                # Email address should be unique
                return Contact.objects.get(email=id_or_email)
        except Contact.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get contact: {ee}")
            return None
