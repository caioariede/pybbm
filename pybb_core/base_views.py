# -*- coding: utf-8 -*-

from __future__ import unicode_literals
import math

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.contrib import messages
from django.db.models import F, Q
from django.db.models.aggregates import Count
from django.http import HttpResponseRedirect, HttpResponse, Http404, HttpResponseBadRequest,\
    HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import ugettext as _
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_POST
from django.views.generic.edit import ModelFormMixin
from django.views.decorators.csrf import csrf_protect
from django.views import generic
from pybb_core.util import build_cache_key
from pybb_core.loading import get_models, get_form, get_forms

try:
    from pure_pagination import Paginator
    pure_pagination = True
except ImportError:
    # the simplest emulation of django-pure-pagination behavior
    from django.core.paginator import Paginator, Page
    class PageRepr(int):
        def querystring(self):
            return 'page=%s' % self
    Page.pages = lambda self: [PageRepr(i) for i in range(1, self.paginator.num_pages + 1)]
    pure_pagination = False

from pybb_core.templatetags.pybb_tags import pybb_topic_poll_not_voted
from pybb_core import defaults

from pybb_core.permissions import perms

from pybb_core import util


Category, Forum, Topic, Post, TopicReadTracker, \
    ForumReadTracker, PollAnswerUser = get_models([
        'Category', 'Forum', 'Topic', 'Post', 'TopicReadTracker',
        'ForumReadTracker', 'PollAnswerUser'
    ])

PostForm, AdminPostForm, AttachmentFormSet, \
    PollAnswerFormSet, PollForm = get_forms([
        'PostForm', 'AdminPostForm', 'AttachmentFormSet',
        'PollAnswerFormSet', 'PollForm'
    ])

User = util.get_user_model()
username_field = util.get_username_field()


__all__ = (
    'BaseIndexView', 'BaseCategoryView', 'BaseForumView',
    'BaseLatestTopicsView', 'BaseTopicView', 'BaseAddPostView',
    'BaseEditPostView', 'BaseUserView', 'BaseUserPosts', 'BaseUserTopics',
    'BasePostView', 'BaseModeratePost', 'BaseProfileEditView',
    'BaseDeletePostView', 'BaseStickTopicView', 'BaseUnstickTopicView',
    'BaseCloseTopicView', 'BaseOpenTopicView', 'BaseTopicPollVoteView',
    'topic_cancel_poll_vote',
    'delete_subscription',
    'add_subscription',
    'post_ajax_preview',
    'mark_all_as_read',
    'block_user',
    'unblock_user',
)


class PaginatorMixin(object):
    def get_paginator(self, queryset, per_page, orphans=0, allow_empty_first_page=True, **kwargs):
        kwargs = {}
        if pure_pagination:
            kwargs['request'] = self.request
        return Paginator(queryset, per_page, orphans=0, allow_empty_first_page=True, **kwargs)


class RedirectToLoginMixin(object):
    """ mixin which redirects to settings.LOGIN_URL if the view encounters an PermissionDenied exception
        and the user is not authenticated. Views inheriting from this need to implement
        get_login_redirect_url(), which returns the URL to redirect to after login (parameter "next")
    """
    def dispatch(self, request, *args, **kwargs):
        try:
            return super(RedirectToLoginMixin, self).dispatch(request, *args, **kwargs)
        except PermissionDenied:
            if not request.user.is_authenticated():
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(self.get_login_redirect_url())
            else:
                return HttpResponseForbidden()

    def get_login_redirect_url(self):
        """ get the url to which we redirect after the user logs in. subclasses should override this """
        return '/'


class BreadcrumbMixin(object):
    """ insert in the context, the object to be used in the breadcrumb
    """
    context_breadcrumb_object_name = 'object'

    def update_breadcrumb_ctx(self, ctx):
        ctx['breadcrumb_object'] = self.get_breadcrumb_object(ctx)

    def get_breadcrumb_object(self, ctx):
        obj_name = getattr(self, 'context_breadcrumb_object_name', None)

        if not obj_name:
            # Fallback
            obj_name = getattr(self, 'context_object_name', None)

        if obj_name:
            return ctx.get(obj_name)


class PermissionsMixin(object):
    """ mixin that wraps all permission calls so they can be intercepted
    and changed easily. it can be used to create custom permission
    verifications based on the request, for example.
    """

    # Filtering
    def perms_filter_forums(self, user, qs):
        return perms.filter_forums(user, qs)

    def perms_filter_categories(self, user, qs):
        return perms.filter_categories(user, qs)

    def perms_filter_topics(self, user, qs):
        return perms.filter_topics(user, qs)

    def perms_filter_posts(self, user, qs):
        return perms.filter_posts(user, qs)

    # Forums
    def perms_may_view_forum(self, user, forum):
        return perms.may_view_forum(user, forum)

    # Categories
    def perms_may_view_category(self, user, category):
        return perms.may_view_category(user, category)

    # Topics
    def perms_may_view_topic(self, user, topic):
        return perms.may_view_topic(user, topic)

    def perms_may_moderate_topic(self, user, topic):
        return perms.may_moderate_topic(user, topic)

    def perms_may_vote_in_topic(self, user, topic):
        return perms.may_vote_in_topic(user, topic)

    def perms_may_create_topic(self, user, forum):
        return perms.may_create_topic(user, forum)

    def perms_may_stick_topic(self, user, topic):
        return perms.may_stick_topic(user, topic)

    def perms_may_unstick_topic(self, user, topic):
        return perms.may_unstick_topic(user, topic)

    def perms_may_close_topic(self, user, topic):
        return perms.may_close_topic(user, topic)

    def perms_may_open_topic(self, user, topic):
        return perms.may_open_topic(user, topic)

    def perms_may_create_poll(self, user):
        return perms.may_create_poll(user)

    # Posts
    def perms_may_post_as_admin(self, user):
        return perms.may_post_as_admin(user)

    def perms_may_create_post(self, user, topic):
        return perms.may_create_post(user, topic)

    def perms_may_edit_post(self, user, topic):
        return perms.may_edit_post(user, topic)

    def perms_may_view_post(self, user, post):
        return perms.may_view_post(user, post)

    def perms_may_delete_post(self, user, post):
        return perms.may_delete_post(user, post)

    def perms_may_attach_files(self, user):
        return perms.may_attach_files(user)

    # Users
    def perms_may_block_user(self, user, block_user):
        return perms.may_block_user(user, block_user)


class BaseIndexView(PermissionsMixin, generic.ListView):

    template_name = 'pybb/index.html'
    context_object_name = 'categories'

    def get_context_data(self, **kwargs):
        ctx = super(BaseIndexView, self).get_context_data(**kwargs)
        categories = ctx['categories']
        for category in categories:
            category.forums_accessed = self.perms_filter_forums(self.request.user, category.forums.filter(parent=None))
        ctx['categories'] = categories
        return ctx

    def get_queryset(self):
        return self.perms_filter_categories(self.request.user, Category.objects.all())


class BaseCategoryView(PermissionsMixin, RedirectToLoginMixin, BreadcrumbMixin, generic.DetailView):

    template_name = 'pybb/index.html'
    context_object_name = 'category'

    def get_login_redirect_url(self):
        return reverse('pybb:category', args=(self.kwargs['pk'],))

    def get_queryset(self):
        return Category.objects.all()

    def get_object(self, queryset=None):
        obj = super(BaseCategoryView, self).get_object(queryset)
        if not self.perms_may_view_category(self.request.user, obj):
            raise PermissionDenied
        return obj

    def get_context_data(self, **kwargs):
        ctx = super(BaseCategoryView, self).get_context_data(**kwargs)
        ctx['category'].forums_accessed = self.perms_filter_forums(self.request.user, ctx['category'].forums.filter(parent=None))
        ctx['categories'] = [ctx['category']]
        self.update_breadcrumb_ctx(ctx)
        return ctx


class BaseForumView(PermissionsMixin, RedirectToLoginMixin, PaginatorMixin, BreadcrumbMixin, generic.ListView):

    paginate_by = defaults.PYBB_FORUM_PAGE_SIZE
    context_object_name = 'topic_list'
    context_breadcrumb_object_name = 'forum'
    template_name = 'pybb/forum.html'

    def get_login_redirect_url(self):
        return reverse('pybb:forum', args=(self.kwargs['pk'],))

    def get_context_data(self, **kwargs):
        ctx = super(BaseForumView, self).get_context_data(**kwargs)
        ctx['forum'] = self.forum
        ctx['forum'].forums_accessed = self.perms_filter_forums(self.request.user, self.forum.child_forums.all())
        self.update_breadcrumb_ctx(ctx)
        return ctx

    def get_queryset(self):
        self.forum = get_object_or_404(Forum.objects.all(), pk=self.kwargs['pk'])
        if not self.perms_may_view_forum(self.request.user, self.forum):
            raise PermissionDenied

        qs = self.forum.topics.order_by('-sticky', '-updated').select_related()
        qs = self.perms_filter_topics(self.request.user, qs)
        return qs


class BaseLatestTopicsView(PermissionsMixin, PaginatorMixin, generic.ListView):

    paginate_by = defaults.PYBB_FORUM_PAGE_SIZE
    context_object_name = 'topic_list'
    template_name = 'pybb/latest_topics.html'

    def get_queryset(self):
        qs = Topic.objects.all().select_related()
        qs = self.perms_filter_topics(self.request.user, qs)
        return qs.order_by('-updated')


class BaseTopicView(PermissionsMixin, RedirectToLoginMixin, PaginatorMixin, BreadcrumbMixin, generic.ListView):
    paginate_by = defaults.PYBB_TOPIC_PAGE_SIZE
    template_object_name = 'post_list'
    template_name = 'pybb/topic.html'

    post_form_class = PostForm
    admin_post_form_class = AdminPostForm
    poll_form_class = PollForm
    attachment_formset_class = AttachmentFormSet

    context_breadcrumb_object_name = 'topic'

    def get_login_redirect_url(self):
        return reverse('pybb:topic', args=(self.kwargs['pk'],))

    def get_post_form_class(self):
        return self.post_form_class

    def get_admin_post_form_class(self):
        return self.admin_post_form_class

    def get_poll_form_class(self):
        return self.poll_form_class

    def get_attachment_formset_class(self):
        return self.attachment_formset_class

    def dispatch(self, request, *args, **kwargs):
        self.topic = get_object_or_404(Topic.objects.select_related('forum'), pk=kwargs['pk'])

        if request.GET.get('first-unread'):
            if request.user.is_authenticated():
                read_dates = []
                try:
                    read_dates.append(TopicReadTracker.objects.get(user=request.user, topic=self.topic).time_stamp)
                except TopicReadTracker.DoesNotExist:
                    pass
                try:
                    read_dates.append(ForumReadTracker.objects.get(user=request.user, forum=self.topic.forum).time_stamp)
                except ForumReadTracker.DoesNotExist:
                    pass

                read_date = read_dates and max(read_dates)
                if read_date:
                    try:
                        first_unread_topic = self.topic.posts.filter(created__gt=read_date).order_by('created')[0]
                    except IndexError:
                        first_unread_topic = self.topic.last_post
                else:
                    first_unread_topic = self.topic.head
                return HttpResponseRedirect(reverse('pybb:post', kwargs={'pk': first_unread_topic.id}))

        return super(BaseTopicView, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        if not self.perms_may_view_topic(self.request.user, self.topic):
            raise PermissionDenied
        if self.request.user.is_authenticated() or not defaults.PYBB_ANONYMOUS_VIEWS_CACHE_BUFFER:
            Topic.objects.filter(id=self.topic.id).update(views=F('views') + 1)
        else:
            cache_key = build_cache_key('anonymous_topic_views', topic_id=self.topic.id)
            cache.add(cache_key, 0)
            if cache.incr(cache_key) % defaults.PYBB_ANONYMOUS_VIEWS_CACHE_BUFFER == 0:
                Topic.objects.filter(id=self.topic.id).update(views=F('views') +
                                                                    defaults.PYBB_ANONYMOUS_VIEWS_CACHE_BUFFER)
                cache.set(cache_key, 0)
        qs = self.topic.posts.all().select_related('user')
        if defaults.PYBB_PROFILE_RELATED_NAME:
            qs = qs.select_related('user__%s' % defaults.PYBB_PROFILE_RELATED_NAME)
        if not self.perms_may_moderate_topic(self.request.user, self.topic):
            qs = self.perms_filter_posts(self.request.user, qs)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super(BaseTopicView, self).get_context_data(**kwargs)

        if self.request.user.is_authenticated():
            self.request.user.is_moderator = self.perms_may_moderate_topic(self.request.user, self.topic)
            self.request.user.is_subscribed = self.request.user in self.topic.subscribers.all()
            if self.perms_may_post_as_admin(self.request.user):
                ctx['form'] = self.get_admin_post_form_class()(
                    initial={'login': getattr(self.request.user, username_field)},
                    topic=self.topic)
            else:
                ctx['form'] = self.get_post_form_class()(topic=self.topic)
            self.mark_read(self.request.user, self.topic)
        elif defaults.PYBB_ENABLE_ANONYMOUS_POST:
            ctx['form'] = self.get_post_form_class()(topic=self.topic)
        else:
            ctx['form'] = None
            ctx['next'] = self.get_login_redirect_url()
        if self.perms_may_attach_files(self.request.user):
            aformset = self.get_attachment_formset_class()()
            ctx['aformset'] = aformset
        if defaults.PYBB_FREEZE_FIRST_POST:
            ctx['first_post'] = self.topic.head
        else:
            ctx['first_post'] = None
        ctx['topic'] = self.topic

        if self.perms_may_vote_in_topic(self.request.user, self.topic) and \
                pybb_topic_poll_not_voted(self.topic, self.request.user):
            ctx['poll_form'] = self.get_poll_form_class()(self.topic)

        self.update_breadcrumb_ctx(ctx)

        return ctx

    def mark_read(self, user, topic):
        try:
            forum_mark = ForumReadTracker.objects.get(forum=topic.forum, user=user)
        except ForumReadTracker.DoesNotExist:
            forum_mark = None
        if (forum_mark is None) or (forum_mark.time_stamp < topic.updated):
            # Mark topic as readed
            topic_mark, new = TopicReadTracker.objects.get_or_create_tracker(topic=topic, user=user)
            if not new:
                topic_mark.save()

            # Check, if there are any unread topics in forum
            readed = topic.forum.topics.filter((Q(topicreadtracker__user=user,
                                                  topicreadtracker__time_stamp__gte=F('updated'))) |
                                                Q(forum__forumreadtracker__user=user,
                                                  forum__forumreadtracker__time_stamp__gte=F('updated')))\
                                       .only('id').order_by()

            not_readed = topic.forum.topics.exclude(id__in=readed)
            if not not_readed.exists():
                # Clear all topic marks for this forum, mark forum as readed
                TopicReadTracker.objects.filter(user=user, topic__forum=topic.forum).delete()
                forum_mark, new = ForumReadTracker.objects.get_or_create_tracker(forum=topic.forum, user=user)
                forum_mark.save()


class PostEditMixin(PermissionsMixin):

    poll_answer_formset_class = PollAnswerFormSet

    def get_poll_answer_formset_class(self):
        return self.poll_answer_formset_class

    def get_form_class(self):
        if self.perms_may_post_as_admin(self.request.user):
            return AdminPostForm
        else:
            return PostForm

    def get_context_data(self, **kwargs):
        ctx = super(PostEditMixin, self).get_context_data(**kwargs)
        if self.perms_may_attach_files(self.request.user) and (not 'aformset' in kwargs):
            ctx['aformset'] = AttachmentFormSet(instance=self.object if getattr(self, 'object') else None)
        if self.perms_may_create_poll(self.request.user) and ('pollformset' not in kwargs):
            ctx['pollformset'] = self.get_poll_answer_formset_class()(
                instance=self.object.topic if getattr(self, 'object') else None
            )
        return ctx

    def form_valid(self, form):
        success = True
        save_attachments = False
        save_poll_answers = False
        self.object = form.save(commit=False)

        if self.perms_may_attach_files(self.request.user):
            aformset = AttachmentFormSet(self.request.POST, self.request.FILES, instance=self.object)
            if aformset.is_valid():
                save_attachments = True
            else:
                success = False
        else:
            aformset = None

        if self.perms_may_create_poll(self.request.user):
            pollformset = self.get_poll_answer_formset_class()()
            if getattr(self, 'forum', None) or self.object.topic.head == self.object:
                if self.object.topic.poll_type != Topic.POLL_TYPE_NONE:
                    pollformset = self.get_poll_answer_formset_class()(self.request.POST,
                                                                       instance=self.object.topic)
                    if pollformset.is_valid():
                        save_poll_answers = True
                    else:
                        success = False
                else:
                    self.object.topic.poll_question = None
                    self.object.topic.poll_answers.all().delete()
        else:
            pollformset = None

        if success:
            self.object.topic.save()
            self.object.topic = self.object.topic
            self.object.save()
            if save_attachments:
                aformset.save()
            if save_poll_answers:
                pollformset.save()
            return super(ModelFormMixin, self).form_valid(form)
        else:
            return self.render_to_response(self.get_context_data(form=form, aformset=aformset, pollformset=pollformset))


class BaseAddPostView(PostEditMixin, BreadcrumbMixin, generic.CreateView):

    template_name = 'pybb/add_post.html'
    context_breadcrumb_object_name = 'topic'

    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated():
            self.user = request.user
        else:
            if defaults.PYBB_ENABLE_ANONYMOUS_POST:
                self.user, new = User.objects.get_or_create(**{username_field: defaults.PYBB_ANONYMOUS_USERNAME})
            else:
                from django.contrib.auth.views import redirect_to_login
                return redirect_to_login(request.get_full_path())

        self.forum = None
        self.topic = None
        if 'forum_id' in kwargs:
            self.forum = get_object_or_404(self.perms_filter_forums(self.request.user, Forum.objects.all()), pk=kwargs['forum_id'])
            if not self.perms_may_create_topic(self.user, self.forum):
                raise PermissionDenied
        elif 'topic_id' in kwargs:
            self.topic = get_object_or_404(self.perms_filter_topics(self.request.user, Topic.objects.all()), pk=kwargs['topic_id'])
            if not self.perms_may_create_post(self.user, self.topic):
                raise PermissionDenied

            self.quote = ''
            if 'quote_id' in request.GET:
                try:
                    quote_id = int(request.GET.get('quote_id'))
                except TypeError:
                    raise Http404
                else:
                    post = get_object_or_404(Post, pk=quote_id)
                    self.quote = defaults.PYBB_QUOTE_ENGINES[defaults.PYBB_MARKUP](post.body, getattr(post.user, username_field))

                if self.quote and request.is_ajax():
                    return HttpResponse(self.quote)
        return super(BaseAddPostView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        ip = self.request.META.get('REMOTE_ADDR', '')
        form_kwargs = super(BaseAddPostView, self).get_form_kwargs()
        form_kwargs.update(dict(topic=self.topic, forum=self.forum, user=self.user,
                           ip=ip, initial={}))
        if getattr(self, 'quote', None):
            form_kwargs['initial']['body'] = self.quote
        if self.perms_may_post_as_admin(self.user):
            form_kwargs['initial']['login'] = getattr(self.user, username_field)
        form_kwargs['may_create_poll'] = self.perms_may_create_poll(self.user)
        return form_kwargs

    def get_context_data(self, **kwargs):
        ctx = super(BaseAddPostView, self).get_context_data(**kwargs)
        ctx['forum'] = self.forum
        ctx['topic'] = self.topic
        self.update_breadcrumb_ctx(ctx)
        return ctx

    def get_success_url(self):
        if (not self.request.user.is_authenticated()) and defaults.PYBB_PREMODERATION:
            return reverse('pybb:index')
        return super(BaseAddPostView, self).get_success_url()


class BaseEditPostView(PostEditMixin, BreadcrumbMixin, generic.UpdateView):

    model = Post

    context_object_name = 'post'
    template_name = 'pybb/edit_post.html'

    @method_decorator(login_required)
    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseEditPostView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        form_kwargs = super(BaseEditPostView, self).get_form_kwargs()
        form_kwargs['may_create_poll'] = self.perms_may_create_poll(self.request.user)
        return form_kwargs

    def get_object(self, queryset=None):
        post = super(BaseEditPostView, self).get_object(queryset)
        if not self.perms_may_edit_post(self.request.user, post):
            raise PermissionDenied
        return post

    def get_context_data(self, **kwargs):
        ctx = super(BaseEditPostView, self).get_context_data(**kwargs)
        self.update_breadcrumb_ctx(ctx)
        return ctx


class BaseUserView(PermissionsMixin, generic.DetailView):
    model = User
    template_name = 'pybb/user.html'
    context_object_name = 'target_user'

    def get_object(self, queryset=None):
        if queryset is None:
            queryset = self.get_queryset()
        return get_object_or_404(queryset, **{username_field: self.kwargs['username']})

    def get_context_data(self, **kwargs):
        ctx = super(BaseUserView, self).get_context_data(**kwargs)
        ctx['topic_count'] = Topic.objects.filter(user=ctx['target_user']).count()
        return ctx


class BaseUserPosts(PermissionsMixin, PaginatorMixin, generic.ListView):
    model = Post
    paginate_by = defaults.PYBB_TOPIC_PAGE_SIZE
    template_name = 'pybb/user_posts.html'

    def dispatch(self, request, *args, **kwargs):
        username = kwargs.pop('username')
        self.user = get_object_or_404(**{'klass': User, username_field: username})
        return super(BaseUserPosts, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super(BaseUserPosts, self).get_queryset()
        qs = qs.filter(user=self.user)
        qs = self.perms_filter_posts(self.request.user, qs).select_related('topic')
        qs = qs.order_by('-created', '-updated')
        return qs

    def get_context_data(self, **kwargs):
        context = super(BaseUserPosts, self).get_context_data(**kwargs)
        context['target_user'] = self.user
        return context


class BaseUserTopics(PermissionsMixin, PaginatorMixin, generic.ListView):
    model = Topic
    paginate_by = defaults.PYBB_FORUM_PAGE_SIZE
    template_name = 'pybb/user_topics.html'

    def dispatch(self, request, *args, **kwargs):
        username = kwargs.pop('username')
        self.user = get_object_or_404(User, username=username)
        return super(BaseUserTopics, self).dispatch(request, *args, **kwargs)

    def get_queryset(self):
        qs = super(BaseUserTopics, self).get_queryset()
        qs = qs.filter(user=self.user)
        qs = self.perms_filter_topics(self.user, qs)
        qs = qs.order_by('-updated', '-created')
        return qs

    def get_context_data(self, **kwargs):
        context = super(BaseUserTopics, self).get_context_data(**kwargs)
        context['target_user'] = self.user
        return context


class BasePostView(PermissionsMixin, RedirectToLoginMixin, generic.RedirectView):

    def get_login_redirect_url(self):
        return reverse('pybb:post', args=(self.kwargs['pk'],))

    def get_redirect_url(self, **kwargs):
        post = get_object_or_404(Post.objects.all(), pk=self.kwargs['pk'])
        if not self.perms_may_view_post(self.request.user, post):
            raise PermissionDenied
        count = post.topic.posts.filter(created__lt=post.created).count() + 1
        page = math.ceil(count / float(defaults.PYBB_TOPIC_PAGE_SIZE))
        return '%s?page=%d#post-%d' % (reverse('pybb:topic', args=[post.topic.id]), page, post.id)


class BaseModeratePost(PermissionsMixin, generic.RedirectView):
    def get_redirect_url(self, **kwargs):
        post = get_object_or_404(Post, pk=self.kwargs['pk'])
        if not self.perms_may_moderate_topic(self.request.user, post.topic):
            raise PermissionDenied
        post.on_moderation = False
        post.save()
        return post.get_absolute_url()


class BaseProfileEditView(generic.UpdateView):

    template_name = 'pybb/edit_profile.html'

    def get_object(self, queryset=None):
        return util.get_pybb_profile(self.request.user)

    def get_form_class(self):
        if not self.form_class:
            return get_form('EditProfileForm')
        else:
            return super(BaseProfileEditView, self).get_form_class()

    @method_decorator(login_required)
    @method_decorator(csrf_protect)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseProfileEditView, self).dispatch(request, *args, **kwargs)

    def get_success_url(self):
        return reverse('pybb:edit_profile')


class BaseDeletePostView(PermissionsMixin, BreadcrumbMixin, generic.DeleteView):

    template_name = 'pybb/delete_post.html'
    context_object_name = 'post'

    def get_object(self, queryset=None):
        post = get_object_or_404(Post.objects.select_related('topic', 'topic__forum'), pk=self.kwargs['pk'])
        if not self.perms_may_delete_post(self.request.user, post):
            raise PermissionDenied
        self.topic = post.topic
        self.forum = post.topic.forum
        if not self.perms_may_moderate_topic(self.request.user, self.topic):
            raise PermissionDenied
        return post

    def delete(self, request, *args, **kwargs):
        self.object = self.get_object()
        self.object.delete()
        redirect_url = self.get_success_url()
        if not request.is_ajax():
            return HttpResponseRedirect(redirect_url)
        else:
            return HttpResponse(redirect_url)

    def get_success_url(self):
        try:
            Topic.objects.get(pk=self.topic.id)
        except Topic.DoesNotExist:
            return self.forum.get_absolute_url()
        else:
            if not self.request.is_ajax():
                return self.topic.get_absolute_url()
            else:
                return ""

    def get_context_data(self, **kwargs):
        ctx = super(BaseDeletePostView, self).get_context_data(**kwargs)
        self.update_breadcrumb_ctx(ctx)
        return ctx


class TopicActionBaseView(PermissionsMixin, generic.View):

    def get_topic(self):
        return get_object_or_404(Topic, pk=self.kwargs['pk'])

    @method_decorator(login_required)
    def get(self, *args, **kwargs):
        self.topic = self.get_topic()
        self.action(self.topic)
        return HttpResponseRedirect(self.topic.get_absolute_url())


class BaseStickTopicView(TopicActionBaseView):

    def action(self, topic):
        if not self.perms_may_stick_topic(self.request.user, topic):
            raise PermissionDenied
        topic.sticky = True
        topic.save()


class BaseUnstickTopicView(TopicActionBaseView):

    def action(self, topic):
        if not self.perms_may_unstick_topic(self.request.user, topic):
            raise PermissionDenied
        topic.sticky = False
        topic.save()


class BaseCloseTopicView(TopicActionBaseView):

    def action(self, topic):
        if not self.perms_may_close_topic(self.request.user, topic):
            raise PermissionDenied
        topic.closed = True
        topic.save()


class BaseOpenTopicView(TopicActionBaseView):
    def action(self, topic):
        if not self.perms_may_open_topic(self.request.user, topic):
            raise PermissionDenied
        topic.closed = False
        topic.save()


class BaseTopicPollVoteView(PermissionsMixin, BreadcrumbMixin, generic.UpdateView):
    model = Topic
    http_method_names = ['post', ]
    form_class = PollForm

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super(BaseTopicPollVoteView, self).dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super(ModelFormMixin, self).get_form_kwargs()
        kwargs['topic'] = self.object
        return kwargs

    def form_valid(self, form):
        # already voted
        if not self.perms_may_vote_in_topic(self.request.user, self.object) or \
           not pybb_topic_poll_not_voted(self.object, self.request.user):
            return HttpResponseForbidden()

        answers = form.cleaned_data['answers']
        for answer in answers:
            # poll answer from another topic
            if answer.topic != self.object:
                return HttpResponseBadRequest()

            PollAnswerUser.objects.create(poll_answer=answer, user=self.request.user)
        return super(ModelFormMixin, self).form_valid(form)

    def form_invalid(self, form):
        return redirect(self.object)

    def get_success_url(self):
        return self.object.get_absolute_url()

    def get_context_data(self, **kwargs):
        ctx = super(BaseTopicPollVoteView, self).get_context_data(**kwargs)
        self.update_breadcrumb_ctx(ctx)
        return ctx


@login_required
def topic_cancel_poll_vote(request, pk):
    topic = get_object_or_404(Topic, pk=pk)
    PollAnswerUser.objects.filter(user=request.user, poll_answer__topic_id=topic.id).delete()
    return HttpResponseRedirect(topic.get_absolute_url())


@login_required
def delete_subscription(request, topic_id):
    topic = get_object_or_404(perms.filter_topics(request.user, Topic.objects.all()), pk=topic_id)
    topic.subscribers.remove(request.user)
    return HttpResponseRedirect(topic.get_absolute_url())


@login_required
def add_subscription(request, topic_id):
    topic = get_object_or_404(perms.filter_topics(request.user, Topic.objects.all()), pk=topic_id)
    topic.subscribers.add(request.user)
    return HttpResponseRedirect(topic.get_absolute_url())


@login_required
def post_ajax_preview(request):
    content = request.POST.get('data')
    html = defaults.PYBB_MARKUP_ENGINES[defaults.PYBB_MARKUP](content)
    return render(request, 'pybb/_markitup_preview.html', {'html': html})


@login_required
def mark_all_as_read(request):
    for forum in perms.filter_forums(request.user, Forum.objects.all()):
        forum_mark, new = ForumReadTracker.objects.get_or_create_tracker(forum=forum, user=request.user)
        forum_mark.save()
    TopicReadTracker.objects.filter(user=request.user).delete()
    msg = _('All forums marked as read')
    messages.success(request, msg, fail_silently=True)
    return redirect(reverse('pybb:index'))


@login_required
@require_POST
def block_user(request, username):
    user = get_object_or_404(User, **{username_field: username})
    if not perms.may_block_user(request.user, user):
        raise PermissionDenied
    user.is_active = False
    user.save()
    if 'block_and_delete_messages' in request.POST:
        # individually delete each post and empty topic to fire method
        # with forum/topic counters recalculation
        for p in Post.objects.filter(user=user):
            p.delete()
        for t in Topic.objects.annotate(cnt=Count('posts')).filter(cnt=0):
            t.delete()
    msg = _('User successfuly blocked')
    messages.success(request, msg, fail_silently=True)
    return redirect('pybb:index')


@login_required
@require_POST
def unblock_user(request, username):
    user = get_object_or_404(User, **{username_field: username})
    if not perms.may_block_user(request.user, user):
        raise PermissionDenied
    user.is_active = True
    user.save()
    msg = _('User successfuly unblocked')
    messages.success(request, msg, fail_silently=True)
    return redirect('pybb:index')
