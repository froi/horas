from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import UpdateView
from django.core.urlresolvers import reverse_lazy
from django.db.models import Q

from braces.views import LoginRequiredMixin

from .models import Meeting
from .forms import MeetingUpdateForm


class MeetingUpdateView(LoginRequiredMixin, UpdateView):
    model = Meeting
    form_class = MeetingUpdateForm

    def get_object(self, *args, **kwargs):
        return get_object_or_404(
            Meeting.objects.select_related('mentor', 'protege'),
            ~Q(mentor=self.request.user), pk=self.kwargs.get('pk'),
            state='available', protege=None, mentor__username=self.kwargs['username'])

    def get_form_kwargs(self, *args, **kwargs):
        kwargs = super(MeetingUpdateView, self).get_form_kwargs(*args, **kwargs)
        kwargs['protege'] = self.request.user
        return kwargs

    def get_context_data(self, *args, **kwargs):
        ctx = super(MeetingUpdateView, self).get_context_data(*args, **kwargs)
        user = self.object.mentor
        ctx['profile_user'] = user
        return ctx

    def get_success_url(self):
        return reverse_lazy('profile_detail',
                            args=[self.kwargs['username']])


class MeetingConfirmView(LoginRequiredMixin, UpdateView):
    model = Meeting
    http_method_names = ['post']

    def post(self, *args, **kwargs):
        self.object = self.get_object()

        if self.request.user == self.object.mentor:
            self.object.get_state_info().make_transition('confirm', self.request.user)

        return HttpResponseRedirect(self.get_success_url())

    def get_object(self, *args, **kwargs):
        return get_object_or_404(
            Meeting.objects.select_related('mentor', 'protege'),
            pk=self.kwargs.get('pk'), mentor=self.request.user, state='reserved')

    def get_success_url(self):
        return reverse_lazy('profile_detail',
                            args=[self.kwargs['username']])
