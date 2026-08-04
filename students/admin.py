from django.contrib import admin
from .models import Group, Student, Attendance, Grade, Profile, Payment, Certificate, Course, Lead, Test, StudentTestSubmission

@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role')
    list_filter = ('role',)
    search_fields = ('user__username',)

@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'created_at')
    search_fields = ('name',)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('first_name', 'last_name', 'phone', 'group', 'user', 'created_at')
    list_filter = ('group',)
    search_fields = ('first_name', 'last_name', 'phone')

@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status', 'created_at')
    list_filter = ('status', 'date')
    search_fields = ('student__first_name', 'student__last_name')

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'grade', 'grade_type', 'comment')
    list_filter = ('grade', 'grade_type', 'date')
    search_fields = ('student__first_name', 'student__last_name')

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('student', 'month', 'amount', 'is_paid', 'paid_at')
    list_filter = ('is_paid', 'month')
    search_fields = ('student__first_name', 'student__last_name')

@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ('student', 'title', 'score', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('student__first_name', 'student__last_name', 'title')

@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('name', 'description', 'icon_class', 'teacher')
    search_fields = ('name',)

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'course', 'status', 'created_at')
    list_filter = ('status', 'course')
    search_fields = ('name', 'phone')

@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = ('title', 'group', 'created_by', 'created_at')
    list_filter = ('group',)
    search_fields = ('title',)

@admin.register(StudentTestSubmission)
class StudentTestSubmissionAdmin(admin.ModelAdmin):
    list_display = ('student', 'test', 'score', 'status', 'submitted_at')
    list_filter = ('status', 'test')
    search_fields = ('student__first_name', 'student__last_name', 'test__title')

