from datetime import timedelta

from django.utils import timezone
from django.db import models, IntegrityError
from django.db.models import Q

from . import app_settings


class EmailAddressManager(models.Manager):

    def add_email(self, request, user, email, **kwargs):
        confirm = kwargs.pop("confirm", False)
        signup = kwargs.pop("signup", False)
        try:
            email_address = self.create(user=user, email=email, **kwargs)
        except IntegrityError:
            return None
        else:
            if confirm and not email_address.verified:
                email_address.send_confirmation(request,
                                                signup=signup)
            return email_address

    def get_primary(self, user):
        try:
            return self.get(user=user, primary=True)
        except self.model.DoesNotExist:
            return None

    def get_users_for(self, email):
        # this is a list rather than a generator because we probably want to
        # do a len() on it right away
        return [address.user for address in self.filter(verified=True,
                                                        email=email)]

    def fill_cache_for_user(self, user, addresses):
        """
        In a multi-db setup, inserting records and re-reading them later
        on may result in not being able to find newly inserted
        records. Therefore, we maintain a cache for the user so that
        we can avoid database access when we need to re-read..
        """
        user._emailaddress_cache = addresses

    def get_for_user(self, user, email):
        cache_key = '_emailaddress_cache'
        addresses = getattr(user, cache_key, None)
        if addresses is None:
            return self.get(user=user,
                            email__iexact=email)
        else:
            for address in addresses:
                if address.email.lower() == email.lower():
                    return address
            raise self.model.DoesNotExist()


class EmailConfirmationManager(models.Manager):

    def all_expired(self):
        return self.filter(self.expired_q())

    def all_valid(self):
        return self.exclude(self.expired_q())

    def expired_q(self):
        sent_threshold = timezone.now() \
            - timedelta(days=app_settings.EMAIL_CONFIRMATION_EXPIRE_DAYS)
        return Q(sent__lt=sent_threshold)

    def delete_expired_confirmations(self):
        self.all_expired().delete()