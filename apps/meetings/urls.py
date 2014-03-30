from django.conf.urls import patterns, url
from .views import MeetingUpdateView, MeetingConfirmView

urlpatterns = patterns(
    '',  # Empty string as prefix

    url('^(?P<pk>\d+)/$', MeetingUpdateView.as_view(), name='meeting_detail'),
    url('^(?P<pk>\d+)/confirm/$', MeetingConfirmView.as_view(), name='meeting_confirm'),
)
