# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from pybb_core.util import get_user_model, get_username_field
from pybb_core.abstract_models import AbstractCategory, AbstractForum, \
    AbstractTopic, AbstractPost, AbstractProfile, AbstractAttachment, \
    AbstractTopicReadTracker, AbstractForumReadTracker, AbstractPollAnswer, \
    AbstractPollAnswerUser

User = get_user_model()
username_field = get_username_field()


class Category(AbstractCategory):
    pass


class Forum(AbstractForum):
    pass


class Topic(AbstractTopic):
    pass


class Post(AbstractPost):
    pass


class Profile(AbstractProfile):
    pass


class Attachment(AbstractAttachment):
    pass


class TopicReadTracker(AbstractTopicReadTracker):
    pass


class ForumReadTracker(AbstractForumReadTracker):
    pass


class PollAnswer(AbstractPollAnswer):
    pass


class PollAnswerUser(AbstractPollAnswerUser):
    pass


from pybb_core.receivers import *
