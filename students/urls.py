from django.urls import path
from . import views

urlpatterns = [
    # Bosh sahifa
    path('', views.landing_page, name='landing_page'),
    path('submit-application/', views.submit_application, name='submit_application'),
    
    # Auth
    path('dashboard/', views.dashboard, name='dashboard'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    
    # Guruhlar va talabalar
    path('groups/', views.groups_and_students, name='groups_and_students'),
    path('groups/add/', views.add_group, name='add_group'),
    path('groups/edit/<int:group_id>/', views.edit_group, name='edit_group'),
    path('groups/delete/<int:group_id>/', views.delete_group, name='delete_group'),
    path('courses/delete/<int:course_id>/', views.delete_course, name='delete_course'),
    path('students/add/', views.add_student, name='add_student'),
    path('students/edit/<int:student_id>/', views.edit_student, name='edit_student'),
    path('students/delete/<int:student_id>/', views.delete_student, name='delete_student'),
    
    # Davomat
    path('attendance/', views.attendance, name='attendance'),
    path('attendance/save/', views.save_attendance, name='save_attendance'),
    path('attendance/details/<int:student_id>/', views.get_student_monthly_attendance_details, name='student_attendance_details'),
    path('attendance/export/', views.export_student_attendance_excel, name='export_student_attendance_excel'),
    
    # Baholar
    path('grades/', views.grades, name='grades'),
    path('grades/save/', views.save_grade, name='save_grade'),
    path('grades/history/<int:student_id>/', views.get_student_grades_history, name='student_grades_history'),
    
    # Oylik to'lovlar
    path('payments/', views.payments, name='payments'),
    path('payments/save/', views.save_payment, name='save_payment'),
    
    # Natijalar (Sertifikatlar)
    path('certificates/', views.certificates_list, name='certificates_list'),
    path('certificates/upload/', views.upload_certificate, name='upload_certificate'),
    path('certificates/delete/<int:certificate_id>/', views.delete_certificate, name='delete_certificate'),
    
    # Kelgan arizalar (Leads)
    path('leads/', views.leads_list, name='leads_list'),
    path('leads/update/<int:lead_id>/', views.update_lead_status, name='update_lead_status'),
    path('leads/delete/<int:lead_id>/', views.delete_lead, name='delete_lead'),
    
    # Ustozlar va Adminlarni boshqarish
    path('staff/', views.staff_manage, name='staff_manage'),
    path('staff/create/', views.create_staff, name='create_staff'),
    path('staff/edit/<int:user_id>/', views.edit_staff, name='edit_staff'),
    path('staff/delete/<int:user_id>/', views.delete_staff, name='delete_staff'),
    
    # Imtihon testlari (Tests & Proctoring)
    path('tests/', views.test_list, name='test_list'),
    path('tests/create/', views.create_test, name='create_test'),
    path('tests/delete/<int:test_id>/', views.delete_test, name='delete_test'),
    path('tests/reset/<int:submission_id>/', views.reset_test_submission, name='reset_test_submission'),
    path('tests/export/', views.export_student_test_excel, name='export_student_test_excel'),
    path('tests/take/<int:test_id>/', views.take_test, name='take_test'),
    path('tests/submit/<int:test_id>/', views.submit_test, name='submit_test'),
    path('tests/grade/<int:submission_id>/', views.grade_submission, name='grade_submission'),
    path('tests/cheat-alert/<int:submission_id>/', views.cheat_alert, name='cheat_alert'),
]
