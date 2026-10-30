from datetime import date

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.academics.models import AcademicCalendar
from apps.audit.models import AuditEvent
from apps.profiles.models import FacultyProfile, StudentProfile
from apps.questions.models import Tag

from .models import Mentorship, MentorshipRequest, TagFollow, UserFollow


class SocialAPITests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "Strong-Social-Test-Passphrase-73!"
        cls.junior = User.objects.create_user("junior@gvpcew.ac.in", cls.password)
        cls.senior = User.objects.create_user("senior@gvpcew.ac.in", cls.password)
        cls.alumni = User.objects.create_user("alumni@gvpcew.ac.in", cls.password)
        cls.second_senior = User.objects.create_user("senior2@gvpcew.ac.in", cls.password)
        cls.other = User.objects.create_user("other-social@gvpcew.ac.in", cls.password)
        cls.pending_faculty = User.objects.create_user(
            "pending-faculty@gvpcew.ac.in",
            cls.password,
            account_type=User.AccountType.FACULTY,
        )
        cls.approved_faculty = User.objects.create_user(
            "approved-faculty@gvpcew.ac.in",
            cls.password,
            account_type=User.AccountType.FACULTY,
        )
        cls.administrator = User.objects.create_superuser(
            "social-admin@gvpcew.ac.in", cls.password
        )
        cls.calendar = AcademicCalendar.objects.create(
            academic_year="2026-2027-social",
            starts_on=date(2026, 8, 1),
            ends_on=date(2027, 6, 30),
            is_current=True,
        )
        cls.junior_profile = cls.make_student_profile(cls.junior, 2025, 2029)
        cls.senior_profile = cls.make_student_profile(cls.senior, 2024, 2028)
        cls.second_senior_profile = cls.make_student_profile(cls.second_senior, 2024, 2028)
        cls.alumni_profile = cls.make_student_profile(cls.alumni, 2022, 2026)
        cls.pending_faculty_profile = FacultyProfile.objects.create(
            user=cls.pending_faculty,
            department="Computer Science",
            designation="Lecturer",
        )
        cls.approved_faculty_profile = FacultyProfile.objects.create(
            user=cls.approved_faculty,
            department="Computer Science",
            designation="Professor",
            approval_status=FacultyProfile.ApprovalStatus.APPROVED,
            approved_by=cls.administrator,
            approved_at=timezone.now(),
        )
        cls.tag = Tag.objects.create(name="Data Systems")

    @staticmethod
    def make_student_profile(user, start_year, end_year):
        graduation = date(end_year, 6, 30)
        return StudentProfile.objects.create(
            user=user,
            department="Computer Science",
            batch_start_year=start_year,
            batch_end_year=end_year,
            admission_date=date(start_year, 8, 1),
            expected_graduation_date=graduation,
        )

    def client_for(self, user):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(user)
        token_response = client.get("/api/v1/auth/csrf/")
        self.assertEqual(token_response.status_code, 200)
        client.csrf_token = token_response.json()["csrf_token"]
        return client

    def post(self, client, path, data=None):
        return client.post(
            path,
            data or {},
            format="json",
            HTTP_X_CSRFTOKEN=client.csrf_token,
        )

    def test_user_follow_unfollow_self_prevention_and_counts(self):
        follower = self.client_for(self.junior)
        url = f"/api/v1/users/{self.senior.pk}/follow/"
        followed = self.post(follower, url)
        self.assertEqual(followed.status_code, 200)
        self.assertTrue(followed.json()["is_following"])
        self.assertEqual(followed.json()["follower_count"], 1)

        repeated = self.post(follower, url)
        self.assertEqual(repeated.status_code, 200)
        self.assertEqual(UserFollow.objects.filter(follower=self.junior, following=self.senior).count(), 1)
        self.assertEqual(follower.get(f"/api/v1/users/{self.senior.pk}/followers/").json()["count"], 1)
        self.assertEqual(follower.get(f"/api/v1/users/{self.junior.pk}/following/").json()["count"], 1)

        unfollowed = follower.delete(url, HTTP_X_CSRFTOKEN=follower.csrf_token)
        self.assertEqual(unfollowed.status_code, 200)
        self.assertEqual(unfollowed.json()["follower_count"], 0)
        self.assertEqual(self.post(follower, f"/api/v1/users/{self.junior.pk}/follow/").status_code, 400)

    def test_user_follow_duplicate_is_prevented_by_database(self):
        UserFollow.objects.create(follower=self.junior, following=self.senior)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                UserFollow.objects.create(follower=self.junior, following=self.senior)

    def test_tag_follow_unfollow_duplicate_prevention_and_counts(self):
        client = self.client_for(self.junior)
        url = f"/api/v1/tags/{self.tag.pk}/follow/"
        response = self.post(client, url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["follower_count"], 1)
        self.assertEqual(self.post(client, url).status_code, 200)
        self.assertEqual(TagFollow.objects.filter(user=self.junior, tag=self.tag).count(), 1)

        followed_tags = client.get("/api/v1/tags/followed/")
        self.assertEqual(followed_tags.status_code, 200)
        self.assertEqual(followed_tags.json()["count"], 1)
        self.assertEqual(followed_tags.json()["results"][0]["follower_count"], 1)

        tag_detail = client.get(f"/api/v1/tags/{self.tag.pk}/")
        self.assertEqual(tag_detail.status_code, 200)
        self.assertEqual(tag_detail.json()["follower_count"], 1)
        self.assertEqual(
            client.delete(url, HTTP_X_CSRFTOKEN=client.csrf_token).json()["follower_count"],
            0,
        )

    def test_tag_follow_duplicate_is_prevented_by_database(self):
        TagFollow.objects.create(user=self.junior, tag=self.tag)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                TagFollow.objects.create(user=self.junior, tag=self.tag)

    def test_eligible_mentors_and_junior_and_senior_mentees(self):
        junior_client = self.client_for(self.junior)
        for mentor in (self.senior, self.alumni, self.approved_faculty):
            response = self.post(
                junior_client,
                "/api/v1/mentorship/requests/",
                {"mentor_id": mentor.pk, "message": "I would appreciate guidance."},
            )
            self.assertEqual(response.status_code, 201, response.content)

        senior_client = self.client_for(self.second_senior)
        peer_request = self.post(
            senior_client,
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.approved_faculty.pk, "message": "I would appreciate advice."},
        )
        self.assertEqual(peer_request.status_code, 201, peer_request.content)

    def test_ineligible_mentors_and_mentees_are_rejected(self):
        client = self.client_for(self.junior)
        for mentor in (self.junior, self.pending_faculty, self.administrator):
            response = self.post(
                client,
                "/api/v1/mentorship/requests/",
                {"mentor_id": mentor.pk, "message": "Request purpose."},
            )
            self.assertEqual(response.status_code, 400, response.content)

        senior_client = self.client_for(self.second_senior)
        junior_mentor_request = self.post(
            senior_client,
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.junior.pk, "message": "Junior students cannot mentor."},
        )
        self.assertEqual(junior_mentor_request.status_code, 400)

        alumni_client = self.client_for(self.alumni)
        alumni_mentee_request = self.post(
            alumni_client,
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.senior.pk, "message": "Alumni cannot request student mentorship."},
        )
        self.assertEqual(alumni_mentee_request.status_code, 400)

        faculty_client = self.client_for(self.approved_faculty)
        response = self.post(
            faculty_client,
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.senior.pk, "message": "Faculty cannot request student mentorship."},
        )
        self.assertEqual(response.status_code, 400)

    def test_duplicate_pending_request_is_rejected_and_audited_without_message(self):
        client = self.client_for(self.junior)
        payload = {"mentor_id": self.senior.pk, "message": "Please help me plan."}
        first = self.post(client, "/api/v1/mentorship/requests/", payload)
        self.assertEqual(first.status_code, 201, first.content)
        duplicate = self.post(client, "/api/v1/mentorship/requests/", payload)
        self.assertEqual(duplicate.status_code, 400)
        event = AuditEvent.objects.get(action="mentorship.requested")
        self.assertEqual(event.target_user, self.senior)
        self.assertNotIn("message", event.metadata)

    def test_requester_and_status_are_server_controlled(self):
        response = self.post(
            self.client_for(self.junior),
            "/api/v1/mentorship/requests/",
            {
                "mentor_id": self.senior.pk,
                "student_id": self.other.pk,
                "status": "APPROVED",
                "message": "Cannot assign my own requester or status.",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(MentorshipRequest.objects.exists())

    def test_only_intended_mentor_can_approve_or_reject_and_approval_creates_relationship(self):
        request_response = self.post(
            self.client_for(self.junior),
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.senior.pk, "message": "Guidance requested."},
        )
        request_id = request_response.json()["id"]
        approve_url = f"/api/v1/mentorship/requests/{request_id}/approve/"

        unrelated = self.post(self.client_for(self.other), approve_url)
        self.assertEqual(unrelated.status_code, 404)
        mentee_attempt = self.post(self.client_for(self.junior), approve_url)
        self.assertEqual(mentee_attempt.status_code, 403)

        approved = self.post(self.client_for(self.senior), approve_url)
        self.assertEqual(approved.status_code, 200, approved.content)
        self.assertEqual(approved.json()["status"], MentorshipRequest.Status.APPROVED)
        relationship = Mentorship.objects.get(request_id=request_id)
        self.assertEqual(relationship.status, Mentorship.Status.ACTIVE)
        self.assertTrue(AuditEvent.objects.filter(action="mentorship.approved").exists())

        received = self.client_for(self.senior).get("/api/v1/mentorship/requests/received/")
        sent = self.client_for(self.junior).get("/api/v1/mentorship/requests/sent/")
        self.assertEqual(received.json()["count"], 1)
        self.assertEqual(sent.json()["count"], 1)
        self.assertEqual(self.client_for(self.other).get("/api/v1/mentorship/requests/sent/").json()["count"], 0)

    def test_rejection_cancellation_and_invalid_transitions(self):
        first = self.post(
            self.client_for(self.junior),
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.senior.pk, "message": "Please advise."},
        ).json()
        rejected = self.post(
            self.client_for(self.senior),
            f"/api/v1/mentorship/requests/{first['id']}/reject/",
        )
        self.assertEqual(rejected.status_code, 200)
        self.assertEqual(rejected.json()["status"], MentorshipRequest.Status.REJECTED)
        self.assertEqual(
            self.post(
                self.client_for(self.senior),
                f"/api/v1/mentorship/requests/{first['id']}/approve/",
            ).status_code,
            400,
        )

        second = self.post(
            self.client_for(self.junior),
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.second_senior.pk, "message": "Please advise."},
        ).json()
        cancelled = self.post(
            self.client_for(self.junior),
            f"/api/v1/mentorship/requests/{second['id']}/cancel/",
        )
        self.assertEqual(cancelled.status_code, 200)
        self.assertEqual(cancelled.json()["status"], MentorshipRequest.Status.CANCELLED)
        self.assertEqual(
            self.post(
                self.client_for(self.junior),
                f"/api/v1/mentorship/requests/{second['id']}/cancel/",
            ).status_code,
            400,
        )

    def test_duplicate_active_pair_is_rejected_and_relationship_can_complete(self):
        client = self.client_for(self.junior)
        original = self.post(
            client,
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.senior.pk, "message": "First request."},
        ).json()
        self.post(
            self.client_for(self.senior),
            f"/api/v1/mentorship/requests/{original['id']}/approve/",
        )
        second = self.post(
            client,
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.senior.pk, "message": "Second request."},
        )
        self.assertEqual(second.status_code, 201)
        second_approval = self.post(
            self.client_for(self.senior),
            f"/api/v1/mentorship/requests/{second.json()['id']}/approve/",
        )
        self.assertEqual(second_approval.status_code, 400)
        self.assertEqual(Mentorship.objects.filter(student=self.junior, mentor=self.senior, status="ACTIVE").count(), 1)

        relationship = Mentorship.objects.get(request_id=original["id"])
        active = self.client_for(self.junior).get("/api/v1/mentorship/relationships/")
        self.assertEqual(active.json()["count"], 1)
        completed = self.post(
            self.client_for(self.junior),
            f"/api/v1/mentorship/relationships/{relationship.pk}/complete/",
        )
        self.assertEqual(completed.status_code, 200, completed.content)
        self.assertEqual(completed.json()["status"], Mentorship.Status.COMPLETED)
        self.assertEqual(relationship.request.__class__.objects.get(pk=original["id"]).status, MentorshipRequest.Status.COMPLETED)
        self.assertEqual(
            self.client_for(self.junior).get("/api/v1/mentorship/relationships/").json()["count"],
            0,
        )
        self.assertTrue(AuditEvent.objects.filter(action="mentorship.completed").exists())

    def test_active_mentorship_pair_constraint_is_enforced_in_database(self):
        first_request = MentorshipRequest.objects.create(
            student=self.junior,
            mentor=self.senior,
            message="Approved request one.",
            status=MentorshipRequest.Status.APPROVED,
            resolved_at=timezone.now(),
        )
        second_request = MentorshipRequest.objects.create(
            student=self.junior,
            mentor=self.senior,
            message="Approved request two.",
            status=MentorshipRequest.Status.APPROVED,
            resolved_at=timezone.now(),
        )
        Mentorship.objects.create(request=first_request, student=self.junior, mentor=self.senior)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                Mentorship.objects.create(request=second_request, student=self.junior, mentor=self.senior)

    def test_private_requests_require_authentication_and_other_users_cannot_list_them(self):
        request_response = self.post(
            self.client_for(self.junior),
            "/api/v1/mentorship/requests/",
            {"mentor_id": self.senior.pk, "message": "Private request."},
        )
        request_id = request_response.json()["id"]
        anonymous = APIClient(enforce_csrf_checks=True)
        self.assertEqual(anonymous.get("/api/v1/mentorship/requests/sent/").status_code, 403)
        unrelated_url = f"/api/v1/mentorship/requests/{request_id}/reject/"
        self.assertEqual(self.post(self.client_for(self.other), unrelated_url).status_code, 404)
