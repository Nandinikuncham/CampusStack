from django.conf import settings
from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from apps.profiles.models import FacultyProfile, StudentProfile

from .models import User


class RegistrationSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=301, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    department = serializers.CharField(max_length=120, trim_whitespace=True)

    def validate_name(self, value):
        parts = value.split(maxsplit=1)
        if not parts[0] or len(parts[0]) > 150 or (len(parts) > 1 and len(parts[1]) > 150):
            raise serializers.ValidationError("Name must fit the first and last name fields.")
        return value

    def validate_email(self, value):
        email = value.strip().casefold()
        domain = email.rpartition("@")[2]
        allowed_domain = settings.COLLEGE_EMAIL_DOMAIN.casefold()
        if domain != allowed_domain:
            raise serializers.ValidationError(
                f"Use your college email address ending in @{allowed_domain}."
            )
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return email

    def validate_password(self, value):
        try:
            django_validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.messages) from exc
        return value

    @staticmethod
    def split_name(name):
        parts = name.strip().split(maxsplit=1)
        return parts[0], parts[1] if len(parts) > 1 else ""

    def create_user(self, *, email, password, name, account_type):
        first_name, last_name = self.split_name(name)
        return User.objects.create_user(
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
            account_type=account_type,
        )


class StudentRegistrationSerializer(RegistrationSerializer):
    batch_start_year = serializers.IntegerField(min_value=1900, max_value=2200)
    batch_end_year = serializers.IntegerField(min_value=1900, max_value=2200)
    admission_date = serializers.DateField()
    expected_graduation_date = serializers.DateField()

    def validate(self, attrs):
        if attrs["batch_end_year"] < attrs["batch_start_year"]:
            raise serializers.ValidationError(
                {"batch_end_year": "Batch end year cannot precede batch start year."}
            )
        if attrs["expected_graduation_date"] < attrs["admission_date"]:
            raise serializers.ValidationError(
                {"expected_graduation_date": "Graduation cannot precede admission."}
            )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        user = self.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data["name"],
            account_type=User.AccountType.STUDENT,
        )
        profile = StudentProfile(
            user=user,
            department=validated_data["department"],
            batch_start_year=validated_data["batch_start_year"],
            batch_end_year=validated_data["batch_end_year"],
            admission_date=validated_data["admission_date"],
            expected_graduation_date=validated_data["expected_graduation_date"],
        )
        try:
            profile.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        profile.save()
        return user


class FacultyRegistrationSerializer(RegistrationSerializer):
    designation = serializers.CharField(max_length=120, trim_whitespace=True)

    @transaction.atomic
    def create(self, validated_data):
        user = self.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            name=validated_data["name"],
            account_type=User.AccountType.FACULTY,
        )
        profile = FacultyProfile(
            user=user,
            department=validated_data["department"],
            designation=validated_data["designation"],
            approval_status=FacultyProfile.ApprovalStatus.PENDING,
        )
        try:
            profile.full_clean()
        except DjangoValidationError as exc:
            raise serializers.ValidationError(exc.message_dict) from exc
        profile.save()
        return user


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class UserDetailsSerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()
    profile = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ("id", "email", "name", "first_name", "last_name", "account_type", "profile")

    def get_name(self, obj):
        return " ".join(part for part in (obj.first_name, obj.last_name) if part)

    def get_profile(self, obj):
        if obj.account_type == User.AccountType.STUDENT:
            try:
                profile = obj.student_profile
            except StudentProfile.DoesNotExist:
                return None
            return {
                "department": profile.department,
                "batch_start_year": profile.batch_start_year,
                "batch_end_year": profile.batch_end_year,
                "admission_date": profile.admission_date,
                "expected_graduation_date": profile.expected_graduation_date,
            }
        if obj.account_type == User.AccountType.FACULTY:
            try:
                profile = obj.faculty_profile
            except FacultyProfile.DoesNotExist:
                return None
            return {
                "department": profile.department,
                "designation": profile.designation,
                "approval_status": profile.approval_status,
            }
        return None
