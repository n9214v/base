from django.db import models
from datetime import datetime
from mjg_base.classes.log import Log
from mjg_base.services import utility_service

log = Log()


class Feature(models.Model):
    """Feature Toggles"""
    last_updated = models.DateTimeField(auto_now=True)

    # Fields
    group_code = models.CharField(
        max_length=80,
        verbose_name='Group Code',
        help_text='Group features to toggle an entire set of features together',
        default=None, blank=True, null=True
    )
    feature_code = models.CharField(
        max_length=30,
        verbose_name='Feature Identifier',
        help_text='Short identifier for referencing this feature from source code'
    )
    feature_title = models.CharField(
        max_length=80,
        verbose_name='Feature Title',
        help_text='Title of the feature (displayed to users)'
    )
    feature_description = models.CharField(
        max_length=500,
        verbose_name='Feature Description',
        help_text='Optional description of the feature (displayed to users)',
        default=None, blank=True, null=True
    )
    status = models.CharField(
        max_length=1,
        help_text='Is this feature active?',
        default='L',
        choices=(('N', 'No'), ('Y', 'Yes'), ('L', 'Limited to Admins'))
    )

    # Disabled feature can become enabled at a specified date
    enable_date = models.DateTimeField(default=None, blank=True, null=True)

    # Enabled feature can become disabled at a specified date
    disable_date = models.DateTimeField(default=None, blank=True, null=True)

    # =======================
    # SETTERS
    # =======================
    def set_status(self, status):
        log.trace([self, status])
        # If changing to a valid status
        if status in ["Y", "N", "L"] and self.status != status:
            change_string = f"{self.status}{status}"
            enabling = change_string in ['NL', 'NY', 'LY']
            disabling = change_string in ['YN', 'LN']  # YL?

            # Set the new status
            self.status = status

            # If enabling, clear any existing enable date
            if enabling:
                self.enable_date = None

            # If disabling, clear any disable date
            if disabling:
                self.disable_date = None

    def set_status_by_date(self):
        if self.enable_date and self.enable_date <= datetime.now():
            self.set_status('Y')
            self.save()
        if self.disable_date and self.disable_date <= datetime.now():
            self.set_status('N')
            self.save()

    # =======================
    # STATUS
    # =======================

    def current_status(self):
        self.set_status_by_date()
        return self.status

    def status_description(self):
        if self.status == 'Y':
            return "Active"
        elif self.status == 'L':
            return 'Limited'
        else:
            return 'Inactive'

    def __str__(self):
        return f"{self.feature_code} ({self.status_description()})"

    @classmethod
    def is_enabled(cls, feature_code):
        toggles = cls.get_feature_toggles()
        if feature_code not in toggles:
            log.info(f"Creating new feature: {feature_code}")
            nf = Feature()
            nf.feature_code = feature_code
            nf.feature_title = utility_service.decamelize(feature_code)
            nf.save()
            toggles = cls.get_feature_toggles(force_query=True)

        return toggles.get(feature_code)

    @classmethod
    def get_feature_toggles(cls, force_query=False):
        """
        Get a map of features and whether or not they are enabled
        """
        toggles = utility_service.recall()
        if toggles and not force_query:
            return toggles

        log.trace()
        toggles = {}

        # Get all features
        features = Feature.objects.all()
        allow_limited = utility_service.get_session_var('allow_limited_features')
        for ff in features:
            if allow_limited:
                toggles[ff.feature_code] = ff.current_status() in ['Y', 'L']
            else:
                toggles[ff.feature_code] = ff.current_status() == 'Y'
        del features

        return utility_service.store(toggles)

    @classmethod
    def get(cls, feature_info):
        try:
            if str(feature_info).isnumeric():
                return Feature.objects.get(pk=feature_info)
            else:
                return Feature.objects.get(feature_code=feature_info)
        except Feature.DoesNotExist:
            return None
        except Exception as ee:
            log.error(f"Could not get feature: {ee}")
            return None
