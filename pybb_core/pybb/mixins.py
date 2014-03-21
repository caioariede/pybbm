from django.core.exceptions import PermissionDenied
from django.http import HttpResponseForbidden


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


from pybb_core.permissions import perms


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
