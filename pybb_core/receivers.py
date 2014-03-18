from django.db.models.signals import post_delete, post_save

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType

from pybb_core import defaults
from pybb_core.util import get_user_model, get_pybb_profile, get_pybb_profile_model
from pybb_core.subscription import notify_topic_subscribers
from pybb_core.loading import get_classes


Profile, Post = get_classes('models', ['Profile', 'Post'])


def post_saved(instance, **kwargs):
    notify_topic_subscribers(instance)

    if get_pybb_profile(instance.user).autosubscribe:
        instance.topic.subscribers.add(instance.user)

    if kwargs['created']:
        profile = get_pybb_profile(instance.user)
        profile.post_count = instance.user.posts.count()
        profile.save()


def post_deleted(instance, **kwargs):
    profile = get_pybb_profile(instance.user)
    profile.post_count = instance.user.posts.count()
    profile.save()


def user_saved(instance, created, **kwargs):
    if not created:
        return
    try:
        add_post_permission = Permission.objects.get_by_natural_key('add_post', 'pybb', 'post')
        add_topic_permission = Permission.objects.get_by_natural_key('add_topic', 'pybb', 'topic')
    except (Permission.DoesNotExist, ContentType.DoesNotExist):
        return
    instance.user_permissions.add(add_post_permission, add_topic_permission)
    instance.save()
    if get_pybb_profile_model() == Profile:
        Profile(user=instance).save()


post_save.connect(post_saved, sender=Post)
post_delete.connect(post_deleted, sender=Post)
if defaults.PYBB_AUTO_USER_PERMISSIONS:
    post_save.connect(user_saved, sender=get_user_model())
