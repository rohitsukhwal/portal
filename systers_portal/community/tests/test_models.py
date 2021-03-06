from django.test import TestCase
from django.contrib.auth.models import User
from django.db.models.signals import post_save, post_delete

from community.models import Community, JoinRequest, CommunityPage
from community.signals import manage_community_groups, remove_community_groups
from users.models import SystersUser


class CommunityModelTestCase(TestCase):
    def setUp(self):
        post_save.disconnect(manage_community_groups, sender=Community,
                             dispatch_uid="manage_groups")
        post_delete.disconnect(remove_community_groups, sender=Community,
                               dispatch_uid="remove_groups")
        User.objects.create(username='foo', password='foobar')
        self.systers_user = SystersUser.objects.get()
        self.community = Community.objects.create(name="Foo", slug="foo",
                                                  order=1,
                                                  community_admin=self.
                                                  systers_user)

    def test_unicode(self):
        """Test Community object str/unicode representation"""
        self.assertEqual(unicode(self.community), "Foo")

    def test_original_values(self):
        """Test original community name and admin functioning"""
        self.assertEqual(self.community.original_name, "Foo")
        self.assertEqual(self.community.community_admin, self.systers_user)
        self.community.name = "Bar"
        user = User.objects.create(username="bar", password="barfoo")
        systers_user2 = SystersUser.objects.get(user=user)
        self.community.community_admin = systers_user2
        self.community.save()
        self.assertEqual(self.community.original_name, "Foo")
        self.assertEqual(self.community.original_community_admin,
                         self.systers_user)

    def test_has_changed_name(self):
        """Test has_changed_name method of Community"""
        self.assertFalse(self.community.has_changed_name())
        self.community.name = "Bar"
        self.community.save()
        self.assertTrue(self.community.has_changed_name())

    def test_has_changed_community_admin(self):
        """Test has_changed_community_admin method of Community"""
        self.assertFalse(self.community.has_changed_community_admin())
        user = User.objects.create(username="bar", password="barfoo")
        systers_user2 = SystersUser.objects.get(user=user)
        self.community.community_admin = systers_user2
        self.community.save()
        self.assertTrue(self.community.has_changed_community_admin())

    def test_add_remove_member(self):
        """Test adding and removing Community members"""
        self.assertQuerysetEqual(self.community.members.all(), [])
        self.community.add_member(self.systers_user)
        self.community.save()
        self.assertSequenceEqual(self.community.members.all(),
                                 [self.systers_user])
        self.community.remove_member(self.systers_user)
        self.community.save()
        self.assertQuerysetEqual(self.community.members.all(), [])

    def test_get_fields(self):
        """Test getting Community fields"""
        fields = self.community.get_fields()
        self.assertTrue(len(fields), 12)
        self.assertTrue(fields[1], ('name', 'Foo'))


class CommunityPageModelTestCase(TestCase):
    def setUp(self):
        User.objects.create(username='foo', password='foobar')
        self.systers_user = SystersUser.objects.get()
        self.community = Community.objects.create(name="Foo", slug="foo",
                                                  order=1,
                                                  community_admin=self.
                                                  systers_user)

    def test_unicode(self):
        """Test CommunityPage object str/unicode representation"""
        page = CommunityPage(order=1, community=self.community, slug="bar",
                             title="Bar", author=self.systers_user)
        self.assertEqual(unicode(page), "Page Bar of Foo")


class JoinRequestModelTestCase(TestCase):
    def setUp(self):
        User.objects.create(username='foo', password='foobar')
        self.systers_user = SystersUser.objects.get()
        self.community = Community.objects.create(name="Foo", slug="foo",
                                                  order=1,
                                                  community_admin=self.
                                                  systers_user)

    def test_unicode(self):
        """Test JoinRequest object str/unicode representation"""
        join_request = JoinRequest(user=self.systers_user,
                                   community=self.community)
        self.assertEqual(unicode(join_request),
                         "Join Request by foo - not approved")
        join_request.is_approved = True
        join_request.save()
        self.assertEqual(unicode(join_request),
                         "Join Request by foo - approved")

    def test_approve(self):
        """Test approving a join request"""
        join_request = JoinRequest(user=self.systers_user,
                                   community=self.community)
        self.assertFalse(join_request.is_approved)
        join_request.approve()
        self.assertTrue(join_request.is_approved)
        join_request.approve()
        self.assertTrue(join_request.is_approved)

    def test_create_join_request(self):
        """Test model manager method to create a join request"""
        user = User.objects.create(username="bar", password="foobar")
        systers_user = SystersUser.objects.get(user=user)
        join_request, status = JoinRequest.objects.create_join_request(
            systers_user, self.community)
        self.assertEqual(join_request, JoinRequest.objects.get())
        self.assertEqual(status, "ok")

        join_request, status = JoinRequest.objects.create_join_request(
            systers_user, self.community)
        self.assertIsNone(join_request)
        self.assertEqual(status, "join_request_exists")

        join_request = JoinRequest.objects.get()
        join_request.approve()
        self.community.add_member(systers_user)
        join_request, status = JoinRequest.objects.create_join_request(
            systers_user, self.community)
        self.assertIsNone(join_request)
        self.assertEqual(status, "already_member")

        self.community.remove_member(systers_user)
        join_request, status = JoinRequest.objects.create_join_request(
            systers_user, self.community)
        self.assertIsInstance(join_request, JoinRequest)
        self.assertEqual(status, "ok")

    def test_cancel_join_request(self):
        """Test model manager method to cancel join requests"""
        user = User.objects.create(username="bar", password="foobar")
        systers_user = SystersUser.objects.get(user=user)

        status = JoinRequest.objects.cancel_join_request(systers_user,
                                                         self.community)
        self.assertEqual(status, "no_pending_join_request")

        JoinRequest.objects.create(user=systers_user, community=self.community)
        status = JoinRequest.objects.cancel_join_request(systers_user,
                                                         self.community)
        self.assertEqual(status, "ok")
        self.assertSequenceEqual(JoinRequest.objects.all(), [])

        self.community.add_member(systers_user)
        self.community.save()

        status = JoinRequest.objects.cancel_join_request(systers_user,
                                                         self.community)
        self.assertEqual(status, "already_member")

        JoinRequest.objects.create(user=systers_user, community=self.community)
        status = JoinRequest.objects.cancel_join_request(systers_user,
                                                         self.community)
        self.assertEqual(status, "already_member")
