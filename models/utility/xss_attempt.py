from django.db import models
from mjg_base.classes.log import Log
from django.contrib.auth.models import User

log = Log()


class XssAttempt(models.Model):
    """Potential XSS attempts"""
    # Associated user account
    user = models.OneToOneField(User, models.SET_NULL, related_name="xss_suspects", blank=True, null=True)

    # Admin reviewer
    reviewer = models.OneToOneField(User, models.SET_NULL, related_name="xss_reviewers", blank=True, null=True)

    # Fields
    path = models.CharField(
        max_length=200,
        help_text='Request path',
        blank=False, null=False
    )
    parameter_name = models.CharField(
        max_length=80,
        help_text='Parameter name',
        default=None, blank=True, null=True
    )
    parameter_value = models.CharField(
        max_length=500,
        help_text='Parameter content',
        default=None, blank=True, null=True
    )
    date_created = models.DateTimeField(auto_now_add=True)

    @classmethod
    def get(cls, xss_id):
        try:
            return XssAttempt.objects.get(pk=xss_id)
        except XssAttempt.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get XssAttempt: {ee}")
            return None
