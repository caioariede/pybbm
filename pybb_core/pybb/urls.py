# -*- coding: utf-8 -*-

from __future__ import unicode_literals
try:
    from django.conf.urls import patterns, include, url
except ImportError:
    from django.conf.urls.defaults import patterns, include, url

from pybb_core.loading import pybb_import

feeds = pybb_import('feeds')
views = pybb_import('views')


urlpatterns = patterns('',
                       # Syndication feeds
                       url('^feeds/posts/$', feeds.LastPosts(), name='feed_posts'),
                       url('^feeds/topics/$', feeds.LastTopics(), name='feed_topics'),
                       )

urlpatterns += patterns('pybb_core.pybb.views',
                        # Index, Category, Forum
                        url('^$', views.IndexView.as_view(), name='index'),
                        url('^category/(?P<pk>\d+)/$', views.CategoryView.as_view(), name='category'),
                        url('^forum/(?P<pk>\d+)/$', views.ForumView.as_view(), name='forum'),

                        # User
                        url('^users/(?P<username>[^/]+)/$', views.UserView.as_view(), name='user'),
                        url('^block_user/([^/]+)/$', 'block_user', name='block_user'),
                        url('^unblock_user/([^/]+)/$', 'unblock_user', name='unblock_user'),
                        url(r'^users/(?P<username>[^/]+)/topics/$', views.UserTopics.as_view(), name='user_topics'),
                        url(r'^users/(?P<username>[^/]+)/posts/$', views.UserPosts.as_view(), name='user_posts'),

                        # Profile
                        url('^profile/edit/$', views.ProfileEditView.as_view(), name='edit_profile'),

                        # Topic
                        url('^topic/(?P<pk>\d+)/$', views.TopicView.as_view(), name='topic'),
                        url('^topic/(?P<pk>\d+)/stick/$', views.StickTopicView.as_view(), name='stick_topic'),
                        url('^topic/(?P<pk>\d+)/unstick/$', views.UnstickTopicView.as_view(), name='unstick_topic'),
                        url('^topic/(?P<pk>\d+)/close/$', views.CloseTopicView.as_view(), name='close_topic'),
                        url('^topic/(?P<pk>\d+)/open/$', views.OpenTopicView.as_view(), name='open_topic'),
                        url('^topic/(?P<pk>\d+)/poll_vote/$', views.TopicPollVoteView.as_view(), name='topic_poll_vote'),
                        url('^topic/(?P<pk>\d+)/cancel_poll_vote/$', 'topic_cancel_poll_vote', name='topic_cancel_poll_vote'),
                        url('^topic/latest/$', views.LatestTopicsView.as_view(), name='topic_latest'),

                        # Add topic/post
                        url('^forum/(?P<forum_id>\d+)/topic/add/$', views.AddPostView.as_view(), name='add_topic'),
                        url('^topic/(?P<topic_id>\d+)/post/add/$', views.AddPostView.as_view(), name='add_post'),

                        # Post
                        url('^post/(?P<pk>\d+)/$', views.PostView.as_view(), name='post'),
                        url('^post/(?P<pk>\d+)/edit/$', views.EditPostView.as_view(), name='edit_post'),
                        url('^post/(?P<pk>\d+)/delete/$', views.DeletePostView.as_view(), name='delete_post'),
                        url('^post/(?P<pk>\d+)/moderate/$', views.ModeratePost.as_view(), name='moderate_post'),

                        # Attachment
                        #url('^attachment/(\w+)/$', 'show_attachment', name='pybb_attachment'),

                        # Subscription
                        url('^subscription/topic/(\d+)/delete/$',
                            'delete_subscription', name='delete_subscription'),
                        url('^subscription/topic/(\d+)/add/$',
                            'add_subscription', name='add_subscription'),

                        # API
                        url('^api/post_ajax_preview/$', 'post_ajax_preview', name='post_ajax_preview'),

                        # Commands
                        url('^mark_all_as_read/$', 'mark_all_as_read', name='mark_all_as_read')
                        )
