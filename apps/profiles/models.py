# -*- coding: utf-8 -*-

from datetime import datetime
import pytz

from django.db import models
from django.db.models import Q
from django.contrib.auth.models import AbstractUser
from django.db.models.loading import get_model
from django.utils.timezone import now, get_default_timezone, make_aware
from django.core.urlresolvers import reverse_lazy
from django.contrib.sites.models import Site
from django.utils.translation import ugettext_lazy as _

from django.conf import settings

from notification import models as notification
from taggit.managers import TaggableManager

from .utils import get_gravatar_url, next_weekday, week_range
from .fields import DaysOfWeekField


class User(AbstractUser):
    '''
    Defines our custom user model.
    '''

    PRETTY_TIMEZONE_CHOICES = [('', _('--- Selecciona ---'))]

    for tz in pytz.common_timezones:
        now = datetime.now(pytz.timezone(tz))
        PRETTY_TIMEZONE_CHOICES.append(
            (tz, '%s (GMT %s)' % (tz, now.strftime('%z'))))

    # Public profile information
    featured = models.BooleanField(default=False)
    bio = models.TextField(blank=True)
    twitter_username = models.CharField(blank=True, max_length=50)
    facebook_username = models.CharField(blank=True, max_length=50)
    github_username = models.CharField(blank=True, max_length=50)
    linkedin_url = models.URLField(blank=True)
    website_url = models.URLField(blank=True)
    gravatar_url = models.URLField(blank=True)
    is_gravatar_verified = models.BooleanField(default=False)
    city = models.CharField(blank=True, max_length=50)
    state = models.CharField(blank=True, max_length=50)

    # Meeting availability
    day_of_week = DaysOfWeekField(blank=True, null=True, db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    timezone = models.CharField(max_length=255,
                                default=settings.HORAS_DEFAULT_TZ,
                                choices=PRETTY_TIMEZONE_CHOICES)

    # Kept private until meeting
    phone = models.CharField(blank=True, max_length=50)
    skype = models.CharField(blank=True, max_length=50)
    google = models.CharField(blank=True, max_length=50)
    jitsi = models.CharField(blank=True, max_length=50)
    address = models.TextField(blank=True)

    tags = TaggableManager(blank=True)

    date_updated = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.gravatar_url:
            self.gravatar_url = get_gravatar_url(self.email)

        # Check if meeting availability changed
        if self.has_complete_profile():
            original = User.objects.get(pk=self.pk)

            checks = [
                original.day_of_week != self.day_of_week,
                original.start_time != self.start_time,
                original.timezone != self.timezone
            ]

            # if any field changed then we must
            # delete meetings and create a new one
            if any(checks):
                print('---> meeting preferences changed')
                Meeting = get_model('meetings', 'Meeting')
                available_meetings = Meeting.objects.filter(state='available',
                                                            mentor=self)

                for meeting in available_meetings:
                    meeting.get_state_info().make_transition('delete')

                self.get_or_create_meeting()

        super(User, self).save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse_lazy('profile_detail', args=[self.username])

    def get_url_with_domain(self):
        domain = Site.objects.get_current().domain
        return '{0}://{1}{2}'.format(settings.PROTOCOL, domain, self.get_absolute_url())

    def get_tiny_name(self):
        return '{0}. {1}'.format(self.first_name[0], self.last_name)

    def has_complete_profile(self):
        dates = all([str(self.day_of_week), str(self.start_time), self.timezone,
                    self.city, self.state, self.bio, self.first_name, self.last_name])

        contact = any([self.phone, self.skype,
                      self.google, self.jitsi, self.address])

        return all([dates, contact])

    def has_social_links(self):
        return any([self.twitter_username, self.github_username,
                   self.linkedin_url, self.website_url])

    def get_location(self):
        if self.city and self.state:
            return u'{0}, {1}'.format(self.city, self.state)
        elif self.city:
            return self.city
        elif self.state:
            return self.state

    def get_all_meeting_fromats(self):
        available_formats = (
            (self.phone, 'phone', _(u'Teléfono')),
            (self.skype, 'skype', _('Skype')),
            (self.google, 'google', _('Google')),
            (self.jitsi, 'jitsi', _('Jitsi')),
            (self.address,
             'inperson',
             _('En persona') + u' ({0}, {1})'.format(self.city,
                                                     self.state)),
        )
        return available_formats

    def get_meeting_format_information(self, key):
        all_formats = self.get_all_meeting_fromats()
        for format in all_formats:
            if key == format[1]:
                return format[0]
        return False

    def get_meeting_format_name(self, key):
        all_formats = self.get_all_meeting_fromats()
        for format in all_formats:
            if key == format[1]:
                return format[2]
        return False

    def get_meeting_formats(self):
        all_formats = self.get_all_meeting_fromats()

        output = []
        for format in all_formats:
            if format[0]:
                output.append(
                    (format[1], format[2].encode('utf-8'))
                )

        return output

    def get_meeting_formats_string(self):
        formats = self.get_meeting_formats()

        output = []
        for format in formats:
            output.append(format[1])

        return ', '.join(sorted(output))

    def get_or_create_meeting(self):
        if self.has_complete_profile() and self.is_active:
            Meeting = get_model('meetings', 'Meeting')

            user_tz = pytz.timezone(self.timezone)
            date = next_weekday(now(), self.day_of_week)
            next_slot_local = make_aware(
                datetime.combine(date, self.start_time), user_tz)

            default_tz = get_default_timezone()
            next_slot = next_slot_local.astimezone(default_tz)
            week = week_range(next_slot)

            # Getto get_or_create
            try:
                meeting_slot = Meeting.objects.get(Q(state='available') |
                                                   Q(state='reserved') |
                                                   Q(state='confirmed'),
                                                   mentor=self,
                                                   datetime__range=week)
                created = False
            except Meeting.DoesNotExist:
                meeting_slot = Meeting.objects.create(mentor=self,
                                                      datetime=next_slot)
                created = True

            # Notify user
            if created:
                print('-> Created meeting_slot:{0}'.format(meeting_slot))

                if not settings.ANNOUNCE_TEST_MODE:
                    meeting_slot.publish_on_twitter()

            return meeting_slot, created

        return None, False
