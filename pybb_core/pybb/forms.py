from django.forms.models import inlineformset_factory

from pybb_core.loading import get_models
from pybb_core import defaults

from pybb_core.base_forms import BaseAttachmentForm, BasePollAnswerForm, \
    BasePollAnswerFormset, BasePostForm, BaseAdminPostForm, \
    BaseUserSearchForm, BasePollForm


Topic, Post, Attachment, PollAnswer = get_models([
    'Topic', 'Post', 'Attachment', 'PollAnswer'
])


try:
    from pybb_core.base_forms import BaseEditProfileForm
except ImportError:
    pass
else:
    class EditProfileForm(BaseEditProfileForm):
        pass


class AttachmentForm(BaseAttachmentForm):
    pass


class PollAnswerForm(BasePollAnswerForm):
    pass


class PollAnswerFormset(BasePollAnswerFormset):
    pass


class PostForm(BasePostForm):
    pass


class AdminPostForm(BaseAdminPostForm):
    pass


class UserSearchForm(BaseUserSearchForm):
    pass


class PollForm(BasePollForm):
    pass


AttachmentFormSet = inlineformset_factory(Post, Attachment, extra=1,
                                          form=AttachmentForm)

PollAnswerFormSet = inlineformset_factory(
    Topic, PollAnswer, extra=2,
    max_num=defaults.PYBB_POLL_MAX_ANSWERS,
    form=BasePollAnswerForm, formset=PollAnswerFormset)
