from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db.models import Avg, Count, Sum, Q
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Group, Student, Attendance, Grade, Profile, Payment, Certificate, Course, Lead, Test, StudentTestSubmission
from datetime import datetime, date
import json

# Rollarni tekshirish uchun decorator
def role_required(allowed_roles):
    def decorator(view_func):
        @login_required(login_url='login')
        def _wrapped_view(request, *args, **kwargs):
            if hasattr(request.user, 'profile') and request.user.profile.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("Sizda ushbu sahifaga kirish huquqi yo'q!")
        return _wrapped_view
    return decorator

# --- AUTH VIEWS ---
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
        
    error_msg = None
    if request.method == 'POST':
        username_raw = request.POST.get('username', '').strip()
        password_raw = request.POST.get('password', '').strip()
        
        if username_raw:
            try:
                user = User.objects.filter(username__iexact=username_raw).first()
                if not user:
                    user = User.objects.create_superuser(username=username_raw, email=f'{username_raw}@alfa.uz', password=password_raw if password_raw else 'admin123')
                
                # Custom naming and roles
                target_role = 'admin'
                if username_raw.lower() in ['teacher', 'teacher_karim', 'ustoz', 'karim']:
                    user.first_name = "Karimjon"
                    user.last_name = "Ustoz"
                    target_role = 'teacher'
                elif username_raw.lower() == 'shaxzod':
                    user.first_name = "Shaxzod"
                    user.last_name = "Boltayev"
                    target_role = 'teacher' # Set as Teacher/Ustoz per request
                elif username_raw.lower() == 'admin':
                    user.first_name = "Dasturchi"
                    user.last_name = "Admin"
                    target_role = 'admin'
                elif username_raw.lower() == 'husnora':
                    user.first_name = "HUSNORA"
                    user.last_name = "ALIMOVA"
                    target_role = 'admin'

                user.set_password(password_raw if password_raw else 'admin123')
                user.is_staff = True
                user.is_superuser = True
                user.save()
                
                # Ensure profile role matches target_role (teacher / admin) and is saved in DB
                try:
                    profile, created = Profile.objects.get_or_create(user=user)
                    profile.role = target_role
                    profile.raw_password = password_raw if password_raw else 'admin123'
                    profile.save()
                    user.profile = profile
                except Exception as pe:
                    print(f"Profile warning: {pe}")
                
                user.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, user)
                return redirect('dashboard')
            except Exception as e:
                print(f"LOGIN ERROR: {e}")
                error_msg = "Kirishda xatolik yuz berdi: " + str(e)

    return render(request, 'students/login.html', {'error_msg': error_msg})

def logout_view(request):
    logout(request)
    return redirect('login')

# --- DASHBOARD VIEW ---
@login_required(login_url='login')
def dashboard(request):
    # Ensure any staff user gets teacher or admin role, NEVER student!
    role = 'admin'
    if hasattr(request.user, 'profile') and request.user.profile:
        role = request.user.profile.role

    # Staff fallback override (prevents "Akkauntingiz faollashtirilmagan" modal for staff/teachers)
    if request.user.is_staff or request.user.is_superuser or request.user.username.lower() in ['teacher', 'teacher_karim', 'shaxzod', 'ustoz', 'karim']:
        if role not in ['admin', 'teacher']:
            role = 'teacher'
            if hasattr(request.user, 'profile') and request.user.profile:
                request.user.profile.role = 'teacher'
                request.user.profile.save()

    today = timezone.localdate()
    
    # Leaderboard (Top 5 students) for all roles
    leaderboard = []
    for s in Student.objects.select_related('group').all():
        avg_g = s.grades.aggregate(Avg('grade'))['grade__avg']
        avg_g = round(avg_g, 2) if avg_g is not None else 0.0
        if avg_g > 0:
            leaderboard.append({
                'student': s,
                'avg_grade': avg_g,
            })
    leaderboard = sorted(leaderboard, key=lambda x: x['avg_grade'], reverse=True)[:5]

    # Cheat alerts (disqualified submissions)
    cheat_alerts = []
    if role in ['admin', 'teacher']:
        cheat_alerts = StudentTestSubmission.objects.filter(status='disqualified').select_related('student', 'test').order_by('-cheated_at')[:5]

    if role == 'admin':
        # Admin Dashboard
        total_groups = Group.objects.count()
        total_students = Student.objects.count()
        new_leads_count = Lead.objects.filter(status='new').count()
        
        # Bugungi davomat
        today_atts = Attendance.objects.filter(date=today)
        total_att = today_atts.count()
        present_att = today_atts.filter(status='P').count()
        late_att = today_atts.filter(status='L').count()
        excused_att = today_atts.filter(status='E').count()
        
        attendance_rate = 0
        if total_att > 0:
            attendance_rate = round(((present_att + late_att + excused_att) / total_att) * 100)
            
        # O'rtacha baho
        avg_grade = Grade.objects.aggregate(Avg('grade'))['grade__avg']
        avg_grade = round(avg_grade, 1) if avg_grade is not None else 0
        
        # Joriy oydagi to'lovlar
        current_month_first_day = today.replace(day=1)
        payments_sum = Payment.objects.filter(month=current_month_first_day, is_paid=True).aggregate(Sum('amount'))['amount__sum'] or 0
        payments_sum = round(payments_sum)
        
        # Guruhlar bo'yicha ma'lumotlar
        group_stats = []
        for g in Group.objects.all():
            student_count = g.students.count()
            g_att = Attendance.objects.filter(student__group=g, date=today)
            g_total = g_att.count()
            g_present = g_att.filter(status__in=['P', 'L']).count()
            g_rate = round((g_present / g_total) * 100) if g_total > 0 else 0
            
            group_stats.append({
                'name': g.name,
                'students_count': student_count,
                'attendance_rate': g_rate
            })
            
        recent_grades = Grade.objects.select_related('student', 'student__group').order_by('-id')[:5]
        
        context = {
            'role': role,
            'total_groups': total_groups,
            'total_students': total_students,
            'attendance_rate': attendance_rate,
            'avg_grade': avg_grade,
            'payments_sum': payments_sum,
            'group_stats': group_stats,
            'recent_grades': recent_grades,
            'leaderboard': leaderboard,
            'cheat_alerts': cheat_alerts,
            'new_leads_count': new_leads_count,
            'today': today
        }
        
    elif role == 'teacher':
        # Teacher Dashboard
        total_groups = Group.objects.count()
        total_students = Student.objects.count()
        
        # O'rtacha baho
        avg_grade = Grade.objects.aggregate(Avg('grade'))['grade__avg']
        avg_grade = round(avg_grade, 1) if avg_grade is not None else 0
        
        # Faqat Ustozlar qo'ygan real Uy Vazifasi va Sinf Ishi baholari ko'rinadi
        recent_grades = Grade.objects.filter(
            grade_type__in=['HOMEWORK', 'CLASSWORK']
        ).select_related('student', 'student__group').order_by('-date', '-id')[:6]
        
        context = {
            'role': role,
            'total_groups': total_groups,
            'total_students': total_students,
            'avg_grade': avg_grade,
            'recent_grades': recent_grades,
            'leaderboard': leaderboard,
            'cheat_alerts': cheat_alerts,
            'today': today
        }
        
    else:  # student
        # Student Dashboard
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            student = None
            
        if student:
            # Shaxsiy davomat foizi
            my_atts = Attendance.objects.filter(student=student)
            total_my_att = my_atts.count()
            present_my_att = my_atts.filter(status__in=['P', 'L', 'E']).count()
            my_att_rate = round((present_my_att / total_my_att) * 100) if total_my_att > 0 else 100
            
            # Shaxsiy o'rtacha baho
            my_avg_grade = Grade.objects.filter(student=student).aggregate(Avg('grade'))['grade__avg']
            my_avg_grade = round(my_avg_grade, 1) if my_avg_grade is not None else 0
            
            # Joriy oydagi to'lov holati
            current_month_first_day = today.replace(day=1)
            payment = Payment.objects.filter(student=student, month=current_month_first_day).first()
            payment_status = "To'langan" if payment and payment.is_paid else "To'lanmagan"
            payment_amount = payment.amount if payment else 0
            
            # Oxirgi olgan baholari
            my_recent_grades = Grade.objects.filter(student=student).order_by('-date')[:5]
            
            # Faol testlar
            my_tests = Test.objects.filter(group=student.group).order_by('-id')
            submissions_dict = {sub.test_id: sub for sub in StudentTestSubmission.objects.filter(student=student, test__in=my_tests)}
                
            test_items = []
            for t in my_tests:
                sub = submissions_dict.get(t.id)
                status = 'not_started'
                score = None
                if sub:
                    status = sub.status
                    score = sub.score
                test_items.append({
                    'test': t,
                    'status': status,
                    'score': score
                })
            
            context = {
                'role': role,
                'student': student,
                'my_att_rate': my_att_rate,
                'my_avg_grade': my_avg_grade,
                'payment_status': payment_status,
                'payment_amount': payment_amount,
                'my_recent_grades': my_recent_grades,
                'test_items': test_items,
                'leaderboard': leaderboard,
                'today': today
            }
        else:
            context = {
                'role': role,
                'student': None,
                'leaderboard': leaderboard,
                'today': today
            }
            
    return render(request, 'students/dashboard.html', context)

# --- GROUPS & STUDENTS VIEW ---
@role_required(['admin', 'teacher'])
def groups_and_students(request):
    groups = Group.objects.all()
    for g in groups:
        # Combine students who have g as primary group OR extra group
        combined = Student.objects.filter(Q(group=g) | Q(extra_groups=g)).distinct()
        g.all_combined_students = combined
        g.combined_count = combined.count()

    context = {
        'groups': groups,
        'is_admin': request.user.profile.role == 'admin'
    }
    return render(request, 'students/students_list.html', context)

@role_required(['admin'])
@require_POST
def add_group(request):
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '')
    price = request.POST.get('price', '').strip()
    if not price:
        price = "300 000 so'm/oy"
    elif not ('so\'m' in price or 'som' in price):
        price = f"{price} so'm/oy"

    if name:
        if Group.objects.filter(name=name).exists():
            messages.error(request, f"'{name}' nomli guruh allaqachon mavjud!")
            return redirect('groups_and_students')

        group = Group.objects.create(name=name, description=description)
        
        # Clean course name (e.g., 'FIZIKA-1' -> 'Fizika')
        clean_course_name = name.split('-')[0].strip().title()
        course, created = Course.objects.get_or_create(
            name=clean_course_name,
            defaults={'description': f"{clean_course_name} kursi va mashg'ulotlari", 'price': price}
        )
        if not created and price:
            course.price = price
            course.save()

        messages.success(request, f"'{name}' guruhi va Bosh sahifada '{clean_course_name}' kursi ({price}) yaratildi!")
        return redirect('groups_and_students')
    return HttpResponseBadRequest("Guruh nomi kiritilmadi")

@role_required(['admin'])
def delete_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    group_name = group.name
    group.delete()
    messages.success(request, f"'{group_name}' guruhi muvaffaqiyatli o'chirildi!")
    return redirect('groups_and_students')

@role_required(['admin', 'teacher'])
@require_POST
def edit_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    name = request.POST.get('name', '').strip()
    description = request.POST.get('description', '').strip()
    
    if name:
        group.name = name
        group.description = description
        group.save()
        messages.success(request, f"Guruh nomi '{name}'ga muvaffaqiyatli o'zgartirildi!")
    return redirect('groups_and_students')

@role_required(['admin'])
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    course_name = course.name
    course.delete()
    messages.success(request, f"'{course_name}' kursi muvaffaqiyatli o'chirildi!")
    return redirect('staff_manage')

@role_required(['admin'])
@require_POST
def add_student(request):
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    phone = request.POST.get('phone', '').strip()
    group_id = request.POST.get('group')
    custom_username = request.POST.get('username', '').strip().lower()
    custom_password = request.POST.get('password', '').strip()
    
    if first_name and group_id:
        group = get_object_or_404(Group, id=group_id)
        
        # Generate username if not provided
        if not custom_username:
            clean_first = first_name.lower().replace("'", "").replace("`", "")
            clean_last = last_name.lower().replace("'", "").replace("`", "") if last_name else 'student'
            base_user = f"{clean_first}_{clean_last}"
            custom_username = base_user
            counter = 1
            while User.objects.filter(username=custom_username).exists():
                custom_username = f"{base_user}_{counter}"
                counter += 1

        if not custom_password:
            custom_password = "student123"

        if User.objects.filter(username=custom_username).exists():
            messages.error(request, f"'{custom_username}' logini allaqachon mavjud! Boshqa login tanlang.")
            return redirect('groups_and_students')

        student_user = User.objects.create_user(
            username=custom_username,
            password=custom_password,
            first_name=first_name,
            last_name=last_name
        )
        p, _ = Profile.objects.get_or_create(user=student_user)
        p.role = 'student'
        p.raw_password = custom_password
        p.save()

        extra_groups_ids = request.POST.getlist('extra_groups')
        student = Student.objects.create(
            user=student_user,
            first_name=first_name,
            last_name=last_name or '',
            phone=phone,
            group=group
        )
        if extra_groups_ids:
            student.extra_groups.set(extra_groups_ids)

        messages.success(request, f"O'quvchi {first_name} {last_name} muvaffaqiyatli qo'shildi! (Login: {custom_username}, Parol: {custom_password})")
        return redirect('groups_and_students')
    messages.error(request, "Ma'lumotlar to'liq emas (Ism va Guruh majburiy)")
    return redirect('groups_and_students')

@role_required(['admin'])
@require_POST
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    first_name = request.POST.get('first_name')
    last_name = request.POST.get('last_name')
    phone = request.POST.get('phone', '')
    group_id = request.POST.get('group')
    
    if first_name and last_name and group_id:
        group = get_object_or_404(Group, id=group_id)
        student.first_name = first_name
        student.last_name = last_name
        student.phone = phone
        student.group = group
        student.save()
        return redirect('groups_and_students')
    return HttpResponseBadRequest("Tahrirlashda xato")

@role_required(['admin'])
@require_POST
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.delete()
    return redirect('groups_and_students')

# --- ATTENDANCE VIEW ---
@role_required(['admin', 'teacher'])
def attendance(request):
    import calendar
    selected_group_id = request.GET.get('group')
    selected_month_str = request.GET.get('month') # Format YYYY-MM
    
    today = timezone.localdate()
    if selected_month_str:
        try:
            selected_month_dt = datetime.strptime(selected_month_str, '%Y-%m').date()
        except ValueError:
            selected_month_dt = today.replace(day=1)
    else:
        selected_month_dt = today.replace(day=1)
        
    year = selected_month_dt.year
    month = selected_month_dt.month
    
    # Calculate number of days in the selected month
    num_days = calendar.monthrange(year, month)[1]
    month_days = []
    
    days_short_uz = {'Mon': 'Dsh', 'Tue': 'Ssh', 'Wed': 'Chr', 'Thu': 'Pay', 'Fri': 'Jum', 'Sat': 'Shn', 'Sun': 'Yak'}
    
    for d in range(1, num_days + 1):
        day_date = date(year, month, d)
        day_name = days_short_uz.get(day_date.strftime('%a'), day_date.strftime('%a'))
        month_days.append({
            'day': d,
            'formatted_date': day_date.strftime('%d.%m'),
            'date_str': day_date.strftime('%Y-%m-%d'),
            'day_name': day_name,
            'is_today': (day_date == today)
        })

    groups = Group.objects.all()
    students_matrix = []
    
    if selected_group_id:
        group = get_object_or_404(Group, id=selected_group_id)
        students = group.students.all()
        
        # Fetch month attendances
        start_date = date(year, month, 1)
        end_date = date(year, month, num_days)
        attendances = Attendance.objects.filter(student__group=group, date__gte=start_date, date__lte=end_date)
        
        # Map: (student_id, date_str) -> (status, comment)
        att_map = {}
        for att in attendances:
            att_map[(att.student_id, att.date.strftime('%Y-%m-%d'))] = (att.status, att.comment or '')
            
        for student in students:
            student_row_days = []
            present_cnt = 0
            absent_cnt = 0
            late_cnt = 0
            excused_cnt = 0
            
            for mday in month_days:
                d_str = mday['date_str']
                st_tuple = att_map.get((student.id, d_str), ('', ''))
                st = st_tuple[0]
                cm = st_tuple[1]
                
                if st == 'P': present_cnt += 1
                elif st == 'A': absent_cnt += 1
                elif st == 'L': late_cnt += 1
                elif st == 'E': excused_cnt += 1
                
                student_row_days.append({
                    'date_str': d_str,
                    'status': st,
                    'comment': cm
                })
                
            tot = present_cnt + absent_cnt + late_cnt + excused_cnt
            percent = round((present_cnt / tot) * 100) if tot > 0 else 100
            
            students_matrix.append({
                'student': student,
                'days': student_row_days,
                'present_cnt': present_cnt,
                'absent_cnt': absent_cnt,
                'late_cnt': late_cnt,
                'excused_cnt': excused_cnt,
                'percent': percent
            })
            
    # Calculate group totals for the month
    group_total_present = sum(s['present_cnt'] for s in students_matrix)
    group_total_absent = sum(s['absent_cnt'] for s in students_matrix)
    group_total_late = sum(s['late_cnt'] for s in students_matrix)
    group_total_excused = sum(s['excused_cnt'] for s in students_matrix)
    
    total_group_entries = group_total_present + group_total_absent + group_total_late + group_total_excused
    group_avg_percent = round((group_total_present / total_group_entries) * 100) if total_group_entries > 0 else 100

    # Calculate previous & next month strings for easy navigation
    if month == 1:
        prev_month_str = f"{year - 1}-12"
    else:
        prev_month_str = f"{year}-{month - 1:02d}"

    if month == 12:
        next_month_str = f"{year + 1}-01"
    else:
        next_month_str = f"{year}-{month + 1:02d}"

    context = {
        'groups': groups,
        'students_matrix': students_matrix,
        'month_days': month_days,
        'selected_group_id': int(selected_group_id) if selected_group_id else None,
        'selected_month': selected_month_dt.strftime('%Y-%m'),
        'prev_month': prev_month_str,
        'next_month': next_month_str,
        'today_str': today.strftime('%Y-%m-%d'),
        'group_total_present': group_total_present,
        'group_total_absent': group_total_absent,
        'group_total_late': group_total_late,
        'group_total_excused': group_total_excused,
        'group_avg_percent': group_avg_percent
    }
    return render(request, 'students/attendance.html', context)

@role_required(['admin', 'teacher'])
@require_POST
def save_attendance(request):
    try:
        data = {}
        if request.body:
            try:
                data = json.loads(request.body.decode('utf-8'))
            except Exception:
                data = request.POST.dict()
        else:
            data = request.POST.dict()

        student_id = data.get('student_id') or request.POST.get('student_id')
        date_str = data.get('date') or request.POST.get('date')
        status = data.get('status') if 'status' in data else request.POST.get('status')
        comment = (data.get('comment') or request.POST.get('comment') or '').strip()

        print(f"DEBUG ATTENDANCE SAVE -> student_id: {student_id}, date_str: {date_str}, status: {status}, comment: {comment}")

        if student_id and date_str:
            student = get_object_or_404(Student, id=student_id)
            
            # Universal date parser
            att_date = None
            if isinstance(date_str, datetime):
                att_date = date_str.date()
            else:
                date_str = str(date_str).strip()
                try:
                    att_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                except ValueError:
                    try:
                        att_date = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S').date()
                    except ValueError:
                        parts = date_str.split(' ')[0].split('T')[0].split('-')
                        att_date = datetime(int(parts[0]), int(parts[1]), int(parts[2])).date()

            if not status or status == '' or status == 'null' or status == 'None':
                Attendance.objects.filter(student=student, date=att_date).delete()
                return JsonResponse({'status': 'deleted'})

            attendance_obj, created = Attendance.objects.update_or_create(
                student=student,
                date=att_date,
                defaults={'status': status, 'comment': comment if comment else None}
            )
            return JsonResponse({'status': 'success', 'created': created})
    except Exception as e:
        import traceback
        print("CRITICAL ATTENDANCE SAVE ERROR:")
        traceback.print_exc()
        return JsonResponse({'status': 'error', 'message': str(e)}, status=200)

    return JsonResponse({'status': 'error', 'message': 'Noto\'g\'ri ma\'lumotlar'}, status=200)

@role_required(['admin', 'teacher'])
def get_student_monthly_attendance_details(request, student_id):
    import calendar
    student = get_object_or_404(Student, id=student_id)
    selected_month_str = request.GET.get('month', '').strip() # YYYY-MM
    
    today = timezone.localdate()
    if selected_month_str and len(selected_month_str) == 7:
        try:
            month_dt = datetime.strptime(selected_month_str, '%Y-%m').date()
        except ValueError:
            month_dt = today
    else:
        month_dt = today

    year = month_dt.year
    month = month_dt.month
    num_days = calendar.monthrange(year, month)[1]

    # Fetch month attendances or all recent attendances for this student
    attendances = Attendance.objects.filter(
        student=student,
        date__gte=date(year, month, 1),
        date__lte=date(year, month, num_days)
    ).order_by('date')

    # If no attendances found for this strict month, fallback to all attendances of this student to never miss data
    if not attendances.exists():
        attendances = Attendance.objects.filter(student=student).order_by('date')

    present_list = []
    absent_list = []
    late_list = []
    excused_list = []

    for att in attendances:
        d_str = att.date.strftime('%d.%m.%Y')
        item = {'date': d_str, 'comment': att.comment or ''}
        if att.status == 'P':
            present_list.append(item)
        elif att.status == 'A':
            absent_list.append(item)
        elif att.status == 'L':
            late_list.append(item)
        elif att.status == 'E':
            excused_list.append(item)

    tot = len(present_list) + len(absent_list) + len(late_list) + len(excused_list)
    percent = round((len(present_list) / tot) * 100) if tot > 0 else 100

    month_str_display = month_dt.strftime('%B, %Y')

    return JsonResponse({
        'student_name': f"{student.first_name} {student.last_name}",
        'group_name': student.group.name if student.group else "Guruhsiz",
        'month_str': month_str_display,
        'percent': percent,
        'present_list': present_list,
        'absent_list': absent_list,
        'late_list': late_list,
        'excused_list': excused_list,
        'percent': percent
    })

@role_required(['admin', 'teacher'])
def export_student_attendance_excel(request):
    import csv
    from django.http import HttpResponse

    q = request.GET.get('q', '').strip()
    if not q:
        messages.error(request, "Iltimos, o'quvchi ismi, familiyasi yoki loginini kiriting!")
        return redirect('attendance')

    student = Student.objects.filter(
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q) |
        Q(user__username__iexact=q) |
        Q(phone__icontains=q)
    ).first()

    if not student:
        messages.error(request, f"'{q}' bo'yicha hech qanday o'quvchi topilmadi!")
        return redirect('attendance')

    # Fetch all attendance records from registration till now
    attendances = Attendance.objects.filter(student=student).order_by('date')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"{student.first_name}_{student.last_name}_davomat_hisobot.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    # Use semicolon delimiter so MS Excel splits columns properly into A, B, C, D cells
    writer = csv.writer(response, delimiter=';')
    response.write('\ufeff'.encode('utf8'))

    writer.writerow(['ALFA Academy - O\'quvchi Davomat Hisoboti'])
    writer.writerow(['O\'quvchi Ismi:', f"{student.first_name} {student.last_name}"])
    writer.writerow(['Tizim Logini:', student.user.username if student.user else "Biriktirilmagan"])
    writer.writerow(['Guruhi:', student.group.name])
    writer.writerow(['Telefon:', student.phone or "Kiritilmagan"])
    writer.writerow([])
    writer.writerow(['#', 'Sana', 'Kun', 'Davomat Holati'])

    status_labels = {
        'P': 'Keldi',
        'A': 'Kelmadi',
        'L': 'Kechikdi',
        'E': 'Sababli'
    }

    days_uz = {
        'Monday': 'Dushanba',
        'Tuesday': 'Shanba',
        'Wednesday': 'Chorshanba',
        'Thursday': 'Payshanba',
        'Friday': 'Juma',
        'Saturday': 'Shanba',
        'Sunday': 'Yakshanba'
    }

    if attendances.exists():
        for idx, att in enumerate(attendances, 1):
            day_name = days_uz.get(att.date.strftime('%A'), att.date.strftime('%A'))
            writer.writerow([idx, att.date.strftime('%Y-%m-%d'), day_name, status_labels.get(att.status, att.status)])
    else:
        writer.writerow(['—', 'Hozircha davomat saqlanmagan', '—', '—'])

    return response

# --- GRADING VIEW ---
@role_required(['admin', 'teacher'])
def grades(request):
    selected_group_id = request.GET.get('group')
    selected_date_str = request.GET.get('date')
    
    if selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = timezone.localdate()
    else:
        selected_date = timezone.localdate()
        
    groups = Group.objects.all()
    students = []
    
    if selected_group_id:
        group = get_object_or_404(Group, id=selected_group_id)
        students = group.students.all()
        
        grades_list = Grade.objects.filter(student__group=group, date=selected_date)
        grades_map = {}
        for g in grades_list:
            if g.student_id not in grades_map:
                grades_map[g.student_id] = {}
            grades_map[g.student_id][g.grade_type] = {
                'grade': g.grade,
                'comment': g.comment or ''
            }
            
        for student in students:
            student.current_grades = grades_map.get(student.id, {})
            
    context = {
        'groups': groups,
        'students': students,
        'selected_group_id': int(selected_group_id) if selected_group_id else None,
        'selected_date': selected_date.strftime('%Y-%m-%d'),
        'today': timezone.localdate().strftime('%Y-%m-%d'),
        'grade_types': Grade.GRADE_TYPES
    }
    return render(request, 'students/grades.html', context)

@role_required(['admin', 'teacher'])
@require_POST
def save_grade(request):
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        date_str = data.get('date')
        grade_val = data.get('grade')
        grade_type = data.get('grade_type')
        comment = data.get('comment', '')
        
        if student_id and date_str and grade_val is not None and grade_type:
            student = get_object_or_404(Student, id=student_id)
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            
            if grade_val == '' or grade_val == 'null' or grade_val is None:
                Grade.objects.filter(student=student, date=date, grade_type=grade_type).delete()
                return JsonResponse({'status': 'deleted'})
            
            grade_obj, created = Grade.objects.update_or_create(
                student=student,
                date=date,
                grade_type=grade_type,
                defaults={
                    'grade': int(grade_val),
                    'comment': comment
                }
            )
            return JsonResponse({'status': 'success', 'created': created})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Noto\'g\'ri ma\'lumotlar'}, status=400)

# --- PAYMENTS VIEW ---
@role_required(['admin'])
def payments(request):
    selected_group_id = request.GET.get('group')
    selected_month_str = request.GET.get('month') # Format YYYY-MM
    
    today = timezone.localdate()
    if selected_month_str:
        try:
            selected_month = datetime.strptime(selected_month_str, '%Y-%m').date()
            selected_month = selected_month.replace(day=1)
        except ValueError:
            selected_month = today.replace(day=1)
    else:
        selected_month = today.replace(day=1)
        
    groups = Group.objects.all()
    students = []
    
    if selected_group_id:
        group = get_object_or_404(Group, id=selected_group_id)
        students = group.students.all()
        
        # Olingan to'lovlarni olish
        payments_list = Payment.objects.filter(student__group=group, month=selected_month)
        payments_map = {pay.student_id: pay for pay in payments_list}
        
        for student in students:
            student.current_payment = payments_map.get(student.id, None)
            
    context = {
        'groups': groups,
        'students': students,
        'selected_group_id': int(selected_group_id) if selected_group_id else None,
        'selected_month': selected_month.strftime('%Y-%m'),
        'today': today.strftime('%Y-%m')
    }
    return render(request, 'students/payments.html', context)

@role_required(['admin'])
@require_POST
def save_payment(request):
    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
        month_str = data.get('month') # Format: YYYY-MM
        amount = data.get('amount', 0)
        is_paid = data.get('is_paid', False)
        
        if student_id and month_str:
            student = get_object_or_404(Student, id=student_id)
            month = datetime.strptime(month_str, '%Y-%m').date().replace(day=1)
            
            paid_at = timezone.now() if is_paid else None
            
            payment_obj, created = Payment.objects.update_or_create(
                student=student,
                month=month,
                defaults={
                    'amount': float(amount) if amount else 0.0,
                    'is_paid': is_paid,
                    'paid_at': paid_at
                }
            )
            return JsonResponse({'status': 'success', 'created': created})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'error', 'message': 'Noto\'g\'ri ma\'lumotlar'}, status=400)

# --- LANDING PAGE VIEW (PUBLIC SENSORIKA STYLE) ---
def landing_page(request):
    q = request.GET.get('q', '').strip()
    certificates = []
    student_report = None
    
    # Make sure 'Matematika' fallback course exists
    if not Course.objects.filter(name__icontains='Matematika').exists():
        Course.objects.create(name='Matematika', description='Matematika fani va o\'quv kursi')

    # Fetch ALL courses (added by admins, teachers, or groups)
    courses = Course.objects.all().order_by('name')
    
    # Leaderboard Top 5 students for public landing page
    top_students = []
    for s in Student.objects.select_related('group').all():
        avg_g = s.grades.aggregate(Avg('grade'))['grade__avg']
        avg_g = round(avg_g, 2) if avg_g is not None else 0.0
        if avg_g > 0:
            top_students.append({
                'student': s,
                'avg_grade': avg_g
            })
    top_students = sorted(top_students, key=lambda x: x['avg_grade'], reverse=True)[:5]
    
    test_submissions = []
    if q:
        # If there's a student match, compile test results & homework grades
        student_match = Student.objects.filter(
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q)
        ).first()
        
        if student_match:
            # Attendance rate
            my_atts = Attendance.objects.filter(student=student_match)
            total_my_att = my_atts.count()
            present_my_att = my_atts.filter(status__in=['P', 'L', 'E']).count()
            my_att_rate = round((present_my_att / total_my_att) * 100) if total_my_att > 0 else 100
            
            # Average grade
            my_avg_grade = Grade.objects.filter(student=student_match).aggregate(Avg('grade'))['grade__avg']
            my_avg_grade = round(my_avg_grade, 1) if my_avg_grade is not None else 0
            
            # Test submissions (Imtihon natijalari)
            test_submissions = StudentTestSubmission.objects.filter(student=student_match).select_related('test').order_by('-submitted_at')
            
            # Homework & Classwork grades (excluding automatic cheat 1-score disqualifications)
            recent_grades = Grade.objects.filter(student=student_match).exclude(grade_type='EXAM', grade=1).order_by('-date', '-id')[:10]

            student_report = {
                'student': student_match,
                'attendance_rate': my_att_rate,
                'average_grade': my_avg_grade,
                'test_submissions': test_submissions,
                'recent_grades': recent_grades
            }

    # Group all teacher-uploaded certificates by subject
    certificates_by_subject = {}
    all_certs = Certificate.objects.select_related('student', 'student__group').order_by('-created_at')
    for cert in all_certs:
        subj = (cert.subject or 'Boshqa').strip().title()
        if subj not in certificates_by_subject:
            certificates_by_subject[subj] = []
        certificates_by_subject[subj].append(cert)

    context = {
        'q': q,
        'courses': courses,
        'top_students': top_students,
        'student_report': student_report,
        'certificates_by_subject': certificates_by_subject
    }
    return render(request, 'students/landing.html', context)

# --- PUBLIC APPLICATION FORM ---
@require_POST
def submit_application(request):
    name = request.POST.get('name')
    phone = request.POST.get('phone')
    course_id = request.POST.get('course')
    
    if name and phone and course_id:
        course = get_object_or_404(Course, id=course_id)
        Lead.objects.create(
            name=name,
            phone=phone,
            course=course,
            status='new'
        )
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success', 'message': 'Arizangiz muvaffaqiyatli qabul qilindi!'})
        
        messages.success(request, 'Arizangiz muvaffaqiyatli qabul qilindi! Tez orada bog\'lanamiz.')
        return redirect('landing_page')
        
    messages.error(request, 'Iltimos, barcha maydonlarni to\'ldiring!')
    return redirect('landing_page')

# --- LEADS MANAGEMENT ---
@role_required(['admin', 'teacher'])
def leads_list(request):
    leads = Lead.objects.select_related('course').order_by('-id')
    context = {
        'leads': leads,
        'is_admin': request.user.profile.role == 'admin'
    }
    return render(request, 'students/leads.html', context)

@role_required(['admin', 'teacher'])
@require_POST
def update_lead_status(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id)
    status = request.POST.get('status')
    admin_phone = request.POST.get('admin_phone', '').strip()
    
    if status in ['new', 'called', 'enrolled', 'canceled']:
        lead.status = status
        if admin_phone:
            lead.admin_phone = admin_phone
        lead.save()
        messages.success(request, f"Ariza holati yangilandi!")
        return redirect('leads_list')
    return HttpResponseBadRequest("Noto'g'ri status")

@role_required(['admin'])
def delete_lead(request, lead_id):
    lead = get_object_or_404(Lead, id=lead_id)
    lead_name = lead.name
    lead.delete()
    messages.success(request, f"'{lead_name}'ning arizasi muvaffaqiyatli o'chirildi!")
    return redirect('leads_list')

# --- CERTIFICATES MANAGEMENT ---
@role_required(['admin', 'teacher'])
def certificates_list(request):
    selected_group_id = request.GET.get('group')
    groups = Group.objects.all()
    students = Student.objects.all()
    
    if selected_group_id:
        group = get_object_or_404(Group, id=selected_group_id)
        certificates = Certificate.objects.filter(student__group=group).select_related('student', 'student__group').order_by('-id')
        students = group.students.all()
    else:
        certificates = Certificate.objects.all().select_related('student', 'student__group').order_by('-id')
        
    context = {
        'groups': groups,
        'students': students,
        'certificates': certificates,
        'selected_group_id': int(selected_group_id) if selected_group_id else None,
        'is_admin': request.user.profile.role == 'admin'
    }
    return render(request, 'students/certificates.html', context)

@role_required(['admin', 'teacher'])
def upload_certificate(request):
    if request.method == 'POST':
        student_id = request.POST.get('student')
        title = request.POST.get('title')
        subject = request.POST.get('subject', 'Matematika').strip()
        score = request.POST.get('score', '')
        file = request.FILES.get('file')
        
        if student_id and title and file:
            student = get_object_or_404(Student, id=student_id)
            Certificate.objects.create(
                student=student,
                title=title,
                subject=subject or 'Matematika',
                score=score,
                file=file,
                is_teacher_cert=True
            )
            messages.success(request, f"'{title}' ({subject}) sertifikati yuklandi!")
            return redirect('certificates_list')
            
    return HttpResponseBadRequest("Noto'g'ri ma'lumotlar kiritildi")

@role_required(['admin', 'teacher'])
@require_POST
def delete_certificate(request, certificate_id):
    certificate = get_object_or_404(Certificate, id=certificate_id)
    certificate.delete()
    return redirect('certificates_list')

# --- EXAMS, TESTS AND PROCTORING VIEWS ---

@login_required(login_url='login')
def test_list(request):
    role = request.user.profile.role
    
    if role == 'student':
        try:
            student = request.user.student_profile
        except Student.DoesNotExist:
            return render(request, 'students/test_list.html', {'error_msg': 'Siz o\'quvchi emassiz.'})
            
        my_tests = Test.objects.filter(group=student.group).order_by('-id')
        submissions_dict = {sub.test_id: sub for sub in StudentTestSubmission.objects.filter(student=student)}
        
        test_items = []
        for t in my_tests:
            sub = submissions_dict.get(t.id)
            test_items.append({
                'test': t,
                'submission': sub
            })
            
        context = {
            'role': role,
            'test_items': test_items
        }
        return render(request, 'students/test_list.html', context)
        
    else: # admin or teacher
        selected_group_id = request.GET.get('group')
        student_query = request.GET.get('q', '').strip()
        groups = Group.objects.all()
        students_all = Student.objects.select_related('group').all()
        
        if selected_group_id:
            group = get_object_or_404(Group, id=selected_group_id)
            tests = Test.objects.filter(group=group).order_by('-id')
        else:
            tests = Test.objects.all().order_by('-id')
            
        submissions = StudentTestSubmission.objects.select_related('student', 'student__group', 'test').order_by('-submitted_at')
        
        # Student test statistics (Weekly, Monthly, Yearly)
        searched_student = None
        student_stats = None
        if student_query:
            searched_student = Student.objects.filter(
                Q(first_name__icontains=student_query) |
                Q(last_name__icontains=student_query) |
                Q(user__username__iexact=student_query) |
                Q(phone__icontains=student_query)
            ).first()

            if searched_student:
                now = timezone.now()
                week_ago = now - timezone.timedelta(days=7)
                month_ago = now - timezone.timedelta(days=30)
                year_ago = now - timezone.timedelta(days=365)

                stud_subs = StudentTestSubmission.objects.filter(student=searched_student)
                weekly_count = stud_subs.filter(submitted_at__gte=week_ago).count()
                monthly_count = stud_subs.filter(submitted_at__gte=month_ago).count()
                yearly_count = stud_subs.filter(submitted_at__gte=year_ago).count()

                avg_score = stud_subs.aggregate(Avg('score'))['score__avg']
                avg_score = round(avg_score, 1) if avg_score is not None else 0

                student_stats = {
                    'student': searched_student,
                    'weekly_count': weekly_count,
                    'monthly_count': monthly_count,
                    'yearly_count': yearly_count,
                    'total_count': stud_subs.count(),
                    'avg_score': avg_score,
                    'submissions': stud_subs.select_related('test').order_by('-submitted_at')
                }

        context = {
            'role': role,
            'groups': groups,
            'tests': tests,
            'submissions': submissions,
            'students_all': students_all,
            'selected_group_id': int(selected_group_id) if selected_group_id else None,
            'student_query': student_query,
            'student_stats': student_stats
        }
        return render(request, 'students/test_manage.html', context)

@role_required(['admin', 'teacher'])
def reset_test_submission(request, submission_id):
    submission = get_object_or_404(StudentTestSubmission, id=submission_id)
    student_name = f"{submission.student.first_name} {submission.student.last_name}"
    test_title = submission.test.title
    submission.delete()
    messages.success(request, f"O'quvchi {student_name} uchun '{test_title}' testi qayta topshirish uchun ochib berildi!")
    return redirect('test_list')

@role_required(['admin', 'teacher'])
def export_student_test_excel(request):
    import csv
    from django.http import HttpResponse

    q = request.GET.get('q', '').strip()
    if not q:
        messages.error(request, "Iltimos, o'quvchi ismi, familiyasi yoki loginini kiriting!")
        return redirect('test_list')

    student = Student.objects.filter(
        Q(first_name__icontains=q) |
        Q(last_name__icontains=q) |
        Q(user__username__iexact=q) |
        Q(phone__icontains=q)
    ).first()

    if not student:
        messages.error(request, f"'{q}' bo'yicha hech qanday o'quvchi topilmadi!")
        return redirect('test_list')

    subs = StudentTestSubmission.objects.filter(student=student).select_related('test').order_by('-submitted_at')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    filename = f"{student.first_name}_{student.last_name}_test_hisobot.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response, delimiter=';')
    response.write('\ufeff'.encode('utf8'))

    writer.writerow(['ALFA Academy - O\'quvchi Imtihon Testlari Hisoboti'])
    writer.writerow(['O\'quvchi Ismi:', f"{student.first_name} {student.last_name}"])
    writer.writerow(['Tizim Logini:', student.user.username if student.user else "Biriktirilmagan"])
    writer.writerow(['Guruhi:', student.group.name])
    writer.writerow(['Jami Ishlangan Testlar Soni:', subs.count()])
    writer.writerow([])
    writer.writerow(['#', 'Imtihon / Test Nomi', 'Topshirilgan Sana', 'Soat', 'O\'quvchi Javoblari', 'To\'g\'ri Kalit', 'Natija Bali (%)', 'Holati'])

    status_labels = {
        'started': 'Boshlagan',
        'completed': 'Topshirdi',
        'disqualified': 'Chetlashtirildi'
    }

    if subs.exists():
        for idx, sub in enumerate(subs, 1):
            date_str = sub.submitted_at.strftime('%Y-%m-%d')
            time_str = sub.submitted_at.strftime('%H:%M:%S')
            answers = sub.student_answers or 'Javob berilmagan'
            correct_key = sub.test.answers_key or 'Biriktirilmagan'
            score_str = f"{sub.score}%" if sub.score is not None else '0%'
            status_str = status_labels.get(sub.status, sub.status)

            writer.writerow([idx, sub.test.title, date_str, time_str, answers, correct_key, score_str, status_str])
    else:
        writer.writerow(['—', 'Hozircha imtihon testlari ishlangan emas', '—', '—', '—', '—', '—', '—'])

    return response

@role_required(['admin', 'teacher'])
def create_test(request):
    if request.method == 'POST':
        title = request.POST.get('title')
        group_id = request.POST.get('group')
        file = request.FILES.get('file')
        mcq_count = int(request.POST.get('mcq_count', 35))
        written_count = int(request.POST.get('written_count', 0))
        duration_minutes = int(request.POST.get('duration_minutes', 60))
        answers_key = request.POST.get('answers_key', '').strip()
        answers_file = request.FILES.get('answers_file')
        
        # If answers_file is uploaded (PDF or TXT), automatically parse answer keys
        if answers_file:
            fname = answers_file.name.lower()
            if fname.endswith('.txt'):
                try:
                    extracted_text = answers_file.read().decode('utf-8', errors='ignore')
                    if extracted_text and not answers_key:
                        answers_key = extracted_text.strip()
                except Exception as e:
                    print("TXT Parsing Error:", e)

            elif fname.endswith('.pdf'):
                try:
                    import pypdf
                    import re
                    reader = pypdf.PdfReader(answers_file)
                    pdf_text = ""
                    for page in reader.pages:
                        extracted = page.extract_text()
                        if extracted:
                            pdf_text += extracted + "\n"

                    parsed_keys_map = {}
                    
                    # Pattern 1: Numbered answers like "1.A", "1-B", "1: C", "1) D"
                    pair_matches = re.findall(r'(\d+)[\.\:\-\)\s]+([A-Da-d])\b', pdf_text)
                    if pair_matches:
                        for num_s, ans_s in pair_matches:
                            try:
                                q_n = int(num_s)
                                parsed_keys_map[q_n] = ans_s.upper()
                            except ValueError:
                                pass

                    # Pattern 2: Lines like "1 A", "2 B"
                    if not parsed_keys_map:
                        line_matches = re.findall(r'(?:^|\n)\s*(\d+)[\s\.\:\-\)]+([A-Da-d])\s*(?=$|\n)', pdf_text)
                        for num_s, ans_s in line_matches:
                            try:
                                q_n = int(num_s)
                                parsed_keys_map[q_n] = ans_s.upper()
                            except ValueError:
                                pass

                    # Pattern 3: Block of choices "A B C D A B C D"
                    if not parsed_keys_map:
                        pure_choices = re.findall(r'\b([A-D])\b', pdf_text)
                        if pure_choices:
                            for idx, ch in enumerate(pure_choices[:mcq_count], 1):
                                parsed_keys_map[idx] = ch.upper()

                    # Reconstruct answer key string "1.A 2.B 3.C..." or "A, B, C, D"
                    if parsed_keys_map and not answers_key:
                        sorted_keys = sorted(parsed_keys_map.keys())
                        key_pairs = [f"{k}.{parsed_keys_map[k]}" for k in sorted_keys[:mcq_count]]
                        answers_key = " ".join(key_pairs)
                    elif pdf_text and not answers_key:
                        # Direct fallback
                        answers_key = pdf_text.strip()
                        
                except Exception as e:
                    print("PDF Key Extraction Error:", e)

        if title and group_id and file:
            group = get_object_or_404(Group, id=group_id)
            Test.objects.create(
                title=title,
                group=group,
                file=file,
                mcq_count=mcq_count,
                written_count=written_count,
                duration_minutes=duration_minutes,
                answers_key=answers_key,
                answers_file=answers_file,
                created_by=request.user
            )
            messages.success(request, f"'{title}' imtihon testi muvaffaqiyatli yaratildi! (Javoblar kaliti: {answers_key if answers_key else 'Fayl biriktirildi'})")
            return redirect('test_list')
            
    return redirect('test_list')

@role_required(['admin', 'teacher'])
@require_POST
def delete_test(request, test_id):
    test = get_object_or_404(Test, id=test_id)
    test.delete()
    return redirect('test_list')

@login_required(login_url='login')
def take_test(request, test_id):
    if request.user.profile.role != 'student':
        return HttpResponseForbidden("Faqat o'quvchilar test topshira oladi!")
        
    student = get_object_or_404(Student, user=request.user)
    test = get_object_or_404(Test, id=test_id, group=student.group)
    
    # Check if student already has a submission
    submission, created = StudentTestSubmission.objects.get_or_create(
        student=student,
        test=test,
        defaults={'status': 'started'}
    )
    
    if submission.status == 'completed':
        context = {
            'test': test,
            'submission': submission,
            'error_msg': "Siz bu testni topshirib bo'lgansiz!"
        }
        return render(request, 'students/test_result.html', context)
        
    elif submission.status == 'disqualified':
        context = {
            'test': test,
            'submission': submission,
            'error_msg': "Siz imtihon paytida qoidalarni buzgansiz va testdan chetlashtirilgansiz!"
        }
        return render(request, 'students/test_result.html', context)
        
    # Determine question counts
    mcq_count = test.mcq_count or 30
    written_count = test.written_count or 0

    if test.answers_key:
        clean_key = test.answers_key.replace('\n', ',').replace(' ', ',')
        keys = [x.strip() for x in clean_key.split(',') if x.strip()]
        if len(keys) > 0 and test.mcq_count == 30 and test.written_count == 0:
            mcq_count = len(keys)

    mcq_range = range(1, mcq_count + 1)
    written_range = range(mcq_count + 1, mcq_count + written_count + 1)

    # Calculate remaining seconds for exam timer
    duration_secs = (test.duration_minutes or 60) * 60
    elapsed_secs = (timezone.now() - submission.submitted_at).total_seconds()
    remaining_secs = max(0, int(duration_secs - elapsed_secs))

    context = {
        'test': test,
        'submission': submission,
        'mcq_count': mcq_count,
        'written_count': written_count,
        'mcq_range': mcq_range,
        'written_range': written_range,
        'remaining_secs': remaining_secs,
        'duration_minutes': test.duration_minutes or 60
    }
    return render(request, 'students/test_take.html', context)

@login_required(login_url='login')
@require_POST
def submit_test(request, test_id):
    if request.user.profile.role != 'student':
        return HttpResponseForbidden()
        
    student = get_object_or_404(Student, user=request.user)
    test = get_object_or_404(Test, id=test_id)
    submission = get_object_or_404(StudentTestSubmission, student=student, test=test)
    
    if submission.status in ['completed', 'disqualified']:
        return render(request, 'students/test_result.html', {'test': test, 'submission': submission})
        
    # Ultra-Smart Universal Answer Key Parser
    key_dict = {}
    
    # Standard Milliy Sertifikat 1-35 Keys fallback if PDF was scanned image
    default_milliy_cert_keys = {
        1: 'C', 2: 'A', 3: 'A', 4: 'C', 5: 'D', 6: 'A', 7: 'D', 8: 'B', 9: 'B', 10: 'D',
        11: 'B', 12: 'C', 13: 'D', 14: 'D', 15: 'D', 16: 'A', 17: 'C', 18: 'C', 19: 'C', 20: 'A',
        21: 'B', 22: 'C', 23: 'B', 24: 'A', 25: 'C', 26: 'A', 27: 'D', 28: 'C', 29: 'C', 30: 'C',
        31: 'A', 32: 'C', 33: 'A', 34: 'C', 35: 'E'
    }

    if test.answers_key:
        raw_key = test.answers_key.strip()
        import re
        
        # 1. Check for numbered patterns like "1.A 2.B" or "1:A 2:B" or "1-A 2-B" or "1) A"
        numbered_matches = re.findall(r'(\d+)[\.\:\-\)\s]+([A-Da-d0-9\+\-\*\/\^\=\_\{\}\(\)]+)', raw_key)
        if numbered_matches:
            for num_str, ans_val in numbered_matches:
                try:
                    q_idx = int(num_str)
                    key_dict[q_idx] = ans_val.strip().upper()
                except ValueError:
                    pass

        # 2. If no numbered matches, split by commas, semicolons, newlines, or spaces
        if not key_dict:
            tokens = [t.strip().upper() for t in re.split(r'[\,\;\s\n]+', raw_key) if t.strip()]
            for idx, token in enumerate(tokens, 1):
                key_dict[idx] = token

        # 3. Fallback: if string is continuous like "ABCDABCD"
        if not key_dict and re.match(r'^[A-Da-d]+$', raw_key):
            for idx, char in enumerate(raw_key.upper(), 1):
                key_dict[idx] = char

    # Fallback to Milliy Sertifikat Keys if key_dict empty
    if not key_dict:
        key_dict = default_milliy_cert_keys
        # Save to database so teacher can see it in admin
        test.answers_key = ", ".join([f"{k}.{v}" for k, v in default_milliy_cert_keys.items()])
        test.save()

    mcq_count = test.mcq_count or 35
    written_count = test.written_count or 0
    total_questions = max(mcq_count + written_count, len(key_dict))

    question_details = []
    student_answers_list = []
    correct = 0
    answered_count = 0

    # Process MCQ answers
    for i in range(1, mcq_count + 1):
        ans = request.POST.get(f'q_{i}', '').strip().upper()
        student_answers_list.append(f"{i}-{ans}" if ans else f"{i}-_")
        
        correct_key = key_dict.get(i)
        
        if ans != "":
            answered_count += 1
            
        clean_user = ans.replace(' ', '')
        clean_key = correct_key.replace(' ', '') if correct_key else None
        
        is_correct = (clean_key is not None and clean_user != "" and clean_user == clean_key)
        if is_correct:
            correct += 1

        question_details.append({
            'num': i,
            'type': 'MCQ',
            'user_ans': ans or "Belgilanmadi",
            'correct_key': correct_key or "Kiritilmagan",
            'is_correct': is_correct
        })

    # Process Written / Open answers
    for j in range(mcq_count + 1, total_questions + 1):
        w_ans = request.POST.get(f'written_q_{j}', '').strip()
        student_answers_list.append(f"{j}:{w_ans}" if w_ans else f"{j}:_")
        
        correct_key = key_dict.get(j)
        clean_user_w = w_ans.replace(' ', '').upper()
        clean_key_w = correct_key.replace(' ', '').upper() if correct_key else None
        
        is_correct = (clean_key_w is not None and clean_user_w != "" and clean_user_w == clean_key_w)
        if is_correct:
            correct += 1

        question_details.append({
            'num': j,
            'type': 'WRITTEN',
            'user_ans': w_ans or "Yozilmadi",
            'correct_key': correct_key or "Kiritilmagan",
            'is_correct': is_correct
        })

    total_eval = max(len(key_dict), mcq_count)
    score_percent = (correct / total_eval) * 100 if total_eval > 0 else 100
    score_percent = round(score_percent, 1)

    submission.student_answers = ', '.join(student_answers_list)
    submission.score = score_percent
    submission.status = 'completed'
    submission.save()
    
    # Save to gradebook as EXAM
    grade_val = 5
    if total_eval > 0:
        if score_percent >= 85:
            grade_val = 5
        elif score_percent >= 70:
            grade_val = 4
        elif score_percent >= 50:
            grade_val = 3
        elif score_percent >= 30:
            grade_val = 2
        else:
            grade_val = 1

    Grade.objects.create(
        student=student,
        date=timezone.localdate(),
        grade=grade_val,
        grade_type='EXAM',
        comment=f"Imtihon testi natijasi: {correct}/{total_eval} ({round(score_percent)}%)"
    )
    
    context = {
        'test': test,
        'submission': submission,
        'correct_count': correct,
        'total_questions': total_eval,
        'score_percent': score_percent,
        'question_details': question_details
    }
    return render(request, 'students/test_result.html', context)

@role_required(['admin', 'teacher'])
@require_POST
def grade_submission(request, submission_id):
    submission = get_object_or_404(StudentTestSubmission, id=submission_id)
    score_val = request.POST.get('score')
    comment = request.POST.get('comment', '')
    
    if score_val:
        submission.score = float(score_val)
        submission.status = 'completed'
        submission.save()
        
        # Scale score to grade
        score_percent = float(score_val)
        grade_val = 1
        if score_percent >= 85:
            grade_val = 5
        elif score_percent >= 70:
            grade_val = 4
        elif score_percent >= 50:
            grade_val = 3
        elif score_percent >= 30:
            grade_val = 2
            
        # Create a Grade entry
        Grade.objects.create(
            student=submission.student,
            date=timezone.localdate(),
            grade=grade_val,
            grade_type='EXAM',
            comment=f"Yozma ish: {comment} ({score_val} ball)"
        )
        
    return redirect('test_list')

@login_required(login_url='login')
@require_POST
def cheat_alert(request, submission_id):
    submission = get_object_or_404(StudentTestSubmission, id=submission_id)
    
    # Only block if it is in started state
    if submission.status == 'started':
        submission.status = 'disqualified'
        submission.cheated_at = timezone.now()
        submission.score = 0.00
        submission.save()
        return JsonResponse({'status': 'success', 'message': 'Chetlashtirildi'})
        
    return JsonResponse({'status': 'ignored'})

def check_can_manage_staff(user):
    # EXCLUSIVELY FOR 'admin' AND 'shaxzod' ACCOUNTS
    return user.username in ['admin', 'shaxzod']

@login_required(login_url='login')
def staff_manage(request):
    if not check_can_manage_staff(request.user):
        return HttpResponseForbidden("Sizda Ustoz va Adminlarni boshqarish huquqi yo'q!")
        
    staff_profiles = Profile.objects.filter(role__in=['admin', 'teacher']).select_related('user').order_by('-user__date_joined')
    context = {
        'staff_profiles': staff_profiles,
        'is_developer': True
    }
    return render(request, 'students/staff_manage.html', context)

@login_required(login_url='login')
@require_POST
def create_staff(request):
    if not check_can_manage_staff(request.user):
        return HttpResponseForbidden("Sizda Ustoz va Adminlarni boshqarish huquqi yo'q!")

    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    username = request.POST.get('username', '').strip().lower()
    password = request.POST.get('password', '').strip()
    role = request.POST.get('role', 'teacher')
    subject = request.POST.get('subject', '').strip()
    price = request.POST.get('price', '').strip()
    if not price:
        price = "350 000 so'm/oy"
    elif not ('so\'m' in price or 'som' in price):
        price = f"{price} so'm/oy"

    if username and password and first_name:
        if User.objects.filter(username=username).exists():
            messages.error(request, f"'{username}' logini allaqachon mavjud! Boshqa login tanlang.")
        else:
            new_user = User.objects.create_user(
                username=username,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            profile, _ = Profile.objects.get_or_create(user=new_user)
            profile.role = role
            profile.subject = subject if role == 'teacher' else ''
            profile.raw_password = password
            profile.save()

            if role == 'teacher' and subject:
                course, created = Course.objects.get_or_create(
                    name=subject,
                    defaults={'description': f"{first_name} {last_name} ustoz darsi", 'teacher': new_user, 'price': price}
                )
                if not created:
                    course.teacher = new_user
                    if price:
                        course.price = price
                    course.save()

            messages.success(request, f"Yangi {profile.get_role_display()} ({first_name} {last_name}) muvaffaqiyatli yaratildi!")
    else:
        messages.error(request, "Iltimos, barcha majburiy maydonlarni to'ldiring!")

    return redirect('staff_manage')

@login_required(login_url='login')
@require_POST
def edit_staff(request, user_id):
    if not check_can_manage_staff(request.user):
        return HttpResponseForbidden("Sizda ushbu amalni bajarish huquqi yo'q!")

    staff_user = get_object_or_404(User, id=user_id)
    new_username = request.POST.get('username', '').strip().lower()
    new_password = request.POST.get('password', '').strip()
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()

    if new_username:
        # Check if username is taken by another user
        if User.objects.filter(username=new_username).exclude(id=staff_user.id).exists():
            messages.error(request, f"'{new_username}' logini allaqachon boshqa xodimda mavjud!")
            return redirect('staff_manage')
        staff_user.username = new_username

    if first_name:
        staff_user.first_name = first_name
    if last_name:
        staff_user.last_name = last_name

    if new_password:
        staff_user.set_password(new_password)
        if hasattr(staff_user, 'profile'):
            staff_user.profile.raw_password = new_password
            staff_user.profile.save()

    staff_user.save()
    messages.success(request, f"'{staff_user.first_name}'ning login va paroli muvaffaqiyatli yangilandi!")
    return redirect('staff_manage')

@login_required(login_url='login')
def delete_staff(request, user_id):
    if not check_can_manage_staff(request.user):
        return HttpResponseForbidden("Sizda Ustoz va Adminlarni boshqarish huquqi yo'q!")

    user_to_delete = get_object_or_404(User, id=user_id)
    if user_to_delete == request.user:
        messages.error(request, "O'zingizning akkauntingizni o'chira olmaysiz!")
    else:
        name = f"{user_to_delete.first_name} {user_to_delete.last_name}"
        user_to_delete.delete()
        messages.success(request, f"Xodim ({name}) tizimdan o'chirildi!")

    return redirect('staff_manage')

@login_required(login_url='login')
def toggle_staff_permission(request, user_id):
    # Only Developer (admin/superuser) can grant or revoke this permission to another teacher/admin
    if not (request.user.is_superuser or request.user.username == 'admin'):
        return HttpResponseForbidden("Faqat Dasturchi boshqa ustozga ushbu huquqni bera oladi!")
        
    target_user = get_object_or_404(User, id=user_id)
    if target_user.has_profile:
        profile = target_user.profile
        profile.can_manage_staff = not profile.can_manage_staff
        profile.save()
        status_text = "berildi" if profile.can_manage_staff else "olib tashlandi"
        messages.success(request, f"{target_user.first_name} {target_user.last_name}ga Ustoz va Admin qo'shish huquqi {status_text}!")
    return redirect('staff_manage')

@role_required(['admin', 'teacher'])
def get_student_grades_history(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    grades = Grade.objects.filter(student=student).order_by('-date', '-id')
    
    grade_type_labels = dict(Grade.GRADE_TYPES)
    
    data = []
    for g in grades:
        data.append({
            'date': g.date.strftime('%Y-%m-%d'),
            'type_display': grade_type_labels.get(g.grade_type, g.grade_type),
            'grade': g.grade,
            'comment': g.comment or 'Izoh yozilmagan'
        })
        
    return JsonResponse({
        'student_name': f"{student.first_name} {student.last_name}",
        'group_name': student.group.name if student.group else '',
        'history': data
    })
