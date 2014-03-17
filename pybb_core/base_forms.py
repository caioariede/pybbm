# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import re
import inspect


from django import forms
from django.core.exceptions import FieldError
from django.forms.models import BaseInlineFormSet
from django.utils.translation import ugettext, ugettext_lazy
from django.utils.timezone import now as tznow

from pybb_core import util
from pybb_core.loading import get_models

User = util.get_user_model()
username_field = util.get_username_field()

from pybb_core import defaults

Topic, Post, Attachment, PollAnswer = get_models([
    'Topic', 'Post', 'Attachment', 'PollAnswer'
])


class BaseAttachmentForm(forms.ModelForm):
    class Meta(object):
        model = Attachment
        fields = ('file', )

    def clean_file(self):
        if self.cleaned_data['file'].size > defaults.PYBB_ATTACHMENT_SIZE_LIMIT:
            raise forms.ValidationError(ugettext('Attachment is too big'))
        return self.cleaned_data['file']


class BasePollAnswerForm(forms.ModelForm):
    class Meta:
        model = PollAnswer
        fields = ('text', )


class BasePollAnswerFormset(BaseInlineFormSet):
    def clean(self):
        if any(self.errors):
            raise forms.ValidationError(self.errors)
        forms_cnt = len(self.initial_forms) + len([form for form in self.extra_forms if form.has_changed()]) -\
                    len(self.deleted_forms)
        if forms_cnt > defaults.PYBB_POLL_MAX_ANSWERS:
            raise forms.ValidationError(
                ugettext('You can''t add more than %s answers for poll' % defaults.PYBB_POLL_MAX_ANSWERS))
        if forms_cnt < 2:
            raise forms.ValidationError(ugettext('Add two or more answers for this poll'))


class BasePostForm(forms.ModelForm):
    name = forms.CharField(label=ugettext_lazy('Subject'))
    poll_type = forms.TypedChoiceField(label=ugettext_lazy('Poll type'), choices=Topic.POLL_TYPE_CHOICES, coerce=int)
    poll_question = forms.CharField(
        label=ugettext_lazy('Poll question'),
        required=False,
        widget=forms.Textarea(attrs={'class': 'no-markitup'}))

    class Meta(object):
        model = Post
        fields = ('body',)

    def __init__(self, *args, **kwargs):
    #Move args to kwargs
        if args:
            kwargs.update(dict(zip(inspect.getargspec(super(BasePostForm, self).__init__)[0][1:], args)))
        self.user = kwargs.pop('user', None)
        self.ip = kwargs.pop('ip', None)
        self.topic = kwargs.pop('topic', None)
        self.forum = kwargs.pop('forum', None)
        self.may_create_poll = kwargs.pop('may_create_poll', True)
        if not (self.topic or self.forum or ('instance' in kwargs)):
            raise ValueError('You should provide topic, forum or instance')
            #Handle topic subject, poll type and question if editing topic head
        if kwargs.get('instance', None) and (kwargs['instance'].topic.head == kwargs['instance']):
            kwargs.setdefault('initial', {})['name'] = kwargs['instance'].topic.name
            kwargs.setdefault('initial', {})['poll_type'] = kwargs['instance'].topic.poll_type
            kwargs.setdefault('initial', {})['poll_question'] = kwargs['instance'].topic.poll_question

        super(BasePostForm, self).__init__(**kwargs)

        # remove topic specific fields
        if not (self.forum or (self.instance.pk and (self.instance.topic.head == self.instance))):
            del self.fields['name']
            del self.fields['poll_type']
            del self.fields['poll_question']
        elif not self.may_create_poll:
            del self.fields['poll_type']
            del self.fields['poll_question']

        self.available_smiles = defaults.PYBB_SMILES
        self.smiles_prefix = defaults.PYBB_SMILES_PREFIX

    def clean_body(self):
        body = self.cleaned_data['body']
        user = self.user or self.instance.user
        if defaults.PYBB_BODY_VALIDATOR:
            defaults.PYBB_BODY_VALIDATOR(user, body)

        for cleaner in defaults.PYBB_BODY_CLEANERS:
            body = cleaner(user, body)
        return body

    def clean(self):
        poll_type = self.cleaned_data.get('poll_type', None)
        poll_question = self.cleaned_data.get('poll_question', None)
        if poll_type is not None and poll_type != Topic.POLL_TYPE_NONE and not poll_question:
            raise forms.ValidationError(ugettext('Poll''s question is required when adding a poll'))

        return self.cleaned_data

    def save(self, commit=True):
        if self.instance.pk:
            post = super(BasePostForm, self).save(commit=False)
            if self.user:
                post.user = self.user
            if post.topic.head == post:
                post.topic.name = self.cleaned_data['name']
                if self.may_create_poll:
                    post.topic.poll_type = self.cleaned_data['poll_type']
                    post.topic.poll_question = self.cleaned_data['poll_question']
                post.topic.updated = tznow()
                if commit:
                    post.topic.save()
            if commit:
                post.save()
            return post

        allow_post = True
        if defaults.PYBB_PREMODERATION:
            allow_post = defaults.PYBB_PREMODERATION(self.user, self.cleaned_data['body'])
        if self.forum:
            topic = Topic(
                forum=self.forum,
                user=self.user,
                name=self.cleaned_data['name'],
                poll_type=self.cleaned_data.get('poll_type', Topic.POLL_TYPE_NONE),
                poll_question=self.cleaned_data.get('poll_question', None),
            )
            if not allow_post:
                topic.on_moderation = True
            if commit:
                topic.save()
        else:
            topic = self.topic
        post = Post(topic=topic, user=self.user, user_ip=self.ip, body=self.cleaned_data['body'])
        if not allow_post:
            post.on_moderation = True
        if commit:
            post.save()
        return post


class BaseAdminPostForm(BasePostForm):
    """
    Superusers can post messages from any user and from any time
    If no user with specified name - new user will be created
    """
    login = forms.CharField(label=ugettext_lazy('User'))

    def __init__(self, *args, **kwargs):
        if args:
            kwargs.update(dict(zip(inspect.getargspec(forms.ModelForm.__init__)[0][1:], args)))
        if 'instance' in kwargs and kwargs['instance']:
            kwargs.setdefault('initial', {}).update({'login': getattr(kwargs['instance'].user, username_field)})
        super(BaseAdminPostForm, self).__init__(**kwargs)

    def save(self, *args, **kwargs):
        try:
            self.user = User.objects.filter(**{username_field: self.cleaned_data['login']}).get()
        except User.DoesNotExist:
            if username_field != 'email':
                create_data = {username_field: self.cleaned_data['login'],
                               'email': '%s@example.com' % self.cleaned_data['login'],
                               'is_staff': False}
            else:
                create_data = {'email': '%s@example.com' % self.cleaned_data['login'],
                               'is_staff': False}
            self.user = User.objects.create(**create_data)
        return super(BaseAdminPostForm, self).save(*args, **kwargs)


try:
    class BaseEditProfileForm(forms.ModelForm):
        class Meta(object):
            model = util.get_pybb_profile_model()
            fields = ['signature', 'time_zone', 'language', 'show_signatures', 'avatar']

        def __init__(self, *args, **kwargs):
            super(BaseEditProfileForm, self).__init__(*args, **kwargs)
            self.fields['signature'].widget = forms.Textarea(attrs={'rows': 2, 'cols:': 60})

        def clean_avatar(self):
            if self.cleaned_data['avatar'] and (self.cleaned_data['avatar'].size > defaults.PYBB_MAX_AVATAR_SIZE):
                forms.ValidationError(ugettext('Avatar is too large, max size: %s bytes' %
                                               defaults.PYBB_MAX_AVATAR_SIZE))
            return self.cleaned_data['avatar']

        def clean_signature(self):
            value = self.cleaned_data['signature'].strip()
            if len(re.findall(r'\n', value)) > defaults.PYBB_SIGNATURE_MAX_LINES:
                raise forms.ValidationError('Number of lines is limited to %d' % defaults.PYBB_SIGNATURE_MAX_LINES)
            if len(value) > defaults.PYBB_SIGNATURE_MAX_LENGTH:
                raise forms.ValidationError('Length of signature is limited to %d' % defaults.PYBB_SIGNATURE_MAX_LENGTH)
            return value
except FieldError:
    pass


class BaseUserSearchForm(forms.Form):
    query = forms.CharField(required=False, label='')

    def filter(self, qs):
        if self.is_valid():
            query = self.cleaned_data['query']
            return qs.filter(**{'%s__contains' % username_field: query})
        else:
            return qs


class BasePollForm(forms.Form):
    def __init__(self, topic, *args, **kwargs):
        self.topic = topic

        super(BasePollForm, self).__init__(*args, **kwargs)

        qs = PollAnswer.objects.filter(topic=topic)
        if topic.poll_type == Topic.POLL_TYPE_SINGLE:
            self.fields['answers'] = forms.ModelChoiceField(
                label='', queryset=qs, empty_label=None,
                widget=forms.RadioSelect())
        elif topic.poll_type == Topic.POLL_TYPE_MULTIPLE:
            self.fields['answers'] = forms.ModelMultipleChoiceField(
                label='', queryset=qs,
                widget=forms.CheckboxSelectMultiple())

    def clean_answers(self):
        answers = self.cleaned_data['answers']
        if self.topic.poll_type == Topic.POLL_TYPE_SINGLE:
            return [answers]
        else:
            return answers
