from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

class Profile(models.Model):
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('teacher', 'O\'qituvchi'),
        ('student', 'O\'quvchi'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student', verbose_name="Roli")
    subject = models.CharField(max_length=100, blank=True, null=True, verbose_name="Dars beradigan fani")
    can_manage_staff = models.BooleanField(default=False, verbose_name="Ustoz va Admin Qo'shish huquqi")
    raw_password = models.CharField(max_length=128, blank=True, null=True, verbose_name="Ko'rinadigan parol")

    def __str__(self):
        return f"{self.user.username} ({self.get_role_display()})"

    class Meta:
        verbose_name = "Profil"
        verbose_name_plural = "Profillar"

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    if not hasattr(instance, 'profile'):
        Profile.objects.create(user=instance)
    instance.profile.save()

class Group(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Guruh nomi")
    description = models.TextField(blank=True, null=True, verbose_name="Tavsifi")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Guruh"
        verbose_name_plural = "Guruhlar"

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='student_profile', verbose_name="Akkaunti")
    first_name = models.CharField(max_length=100, verbose_name="Ismi")
    last_name = models.CharField(max_length=100, verbose_name="Familiyasi")
    phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Telefon raqami")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='students', verbose_name="Asosiy Guruhi")
    extra_groups = models.ManyToManyField(Group, blank=True, related_name='extra_students', verbose_name="Qo'shimcha Guruhlari")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "O'quvchi"
        verbose_name_plural = "O'quvchilar"

class Attendance(models.Model):
    STATUS_CHOICES = [
        ('P', 'Keldi'),
        ('A', 'Kelmadi'),
        ('L', 'Kechikdi'),
        ('E', 'Sababli'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances', verbose_name="O'quvchi")
    date = models.DateField(verbose_name="Sana")
    status = models.CharField(max_length=1, choices=STATUS_CHOICES, verbose_name="Holati")
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh/Sababi")
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'date')
        verbose_name = "Davomat"
        verbose_name_plural = "Davomatlar"

class Grade(models.Model):
    GRADE_TYPES = [
        ('HW', 'Uy vazifasi'),
        ('ACT', 'Darsdagi faollik'),
        ('EXAM', 'Imtihon'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grades', verbose_name="O'quvchi")
    date = models.DateField(verbose_name="Sana")
    grade = models.IntegerField(verbose_name="Baho")
    grade_type = models.CharField(max_length=4, choices=GRADE_TYPES, verbose_name="Baho turi")
    comment = models.TextField(blank=True, null=True, verbose_name="Izoh")
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Baho"
        verbose_name_plural = "Baholar"

class Payment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='payments', verbose_name="O'quvchi")
    month = models.DateField(verbose_name="Qaysi oy uchun") # Har oyning 1-sanasini kiritamiz (masalan: 2026-07-01)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="To'lov summasi")
    is_paid = models.BooleanField(default=False, verbose_name="To'langan")
    paid_at = models.DateTimeField(blank=True, null=True, verbose_name="To'langan vaqti")

    class Meta:
        unique_together = ('student', 'month')
        verbose_name = "To'lov"
        verbose_name_plural = "To'lovlar"

    def __str__(self):
        return f"{self.student} - {self.month.strftime('%Y-%m')} - {'To\'landi' if self.is_paid else 'To\'lanmadi'}"

class Certificate(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='certificates', null=True, blank=True, verbose_name="O'quvchi")
    title = models.CharField(max_length=200, verbose_name="Sertifikat / Natija nomi")
    subject = models.CharField(max_length=100, default="Matematika", verbose_name="Fan yoki Yo'nalish")
    file = models.FileField(upload_to='certificates/', verbose_name="PDF yoki Rasm fayli")
    score = models.CharField(max_length=50, blank=True, null=True, verbose_name="Imtihon bali / Natijasi")
    is_teacher_cert = models.BooleanField(default=False, verbose_name="Ustoz sertifikati")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqti")

    def __str__(self):
        return f"{self.student} - {self.title}"

    class Meta:
        verbose_name = "Sertifikat va Natija"
        verbose_name_plural = "Sertifikatlar va Natijalar"

class Course(models.Model):
    name = models.CharField(max_length=100, unique=True, verbose_name="Kurs nomi")
    description = models.TextField(verbose_name="Kurs tavsifi")
    price = models.CharField(max_length=100, default="300 000 so'm/oy", verbose_name="Kurs oylik narxi")
    icon_class = models.CharField(max_length=50, default='fa-laptop-code', verbose_name="Ikonka klassi")
    teacher = models.ForeignKey(User, on_delete=models.SET_NULL, blank=True, null=True, related_name='courses', verbose_name="O'qituvchi")

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Kurs"
        verbose_name_plural = "Kurslar"

class Lead(models.Model):
    STATUS_CHOICES = [
        ('new', 'Yangi'),
        ('called', 'Bog\'lanildi'),
        ('enrolled', 'O\'qishni boshladi'),
        ('canceled', 'Rad etildi'),
    ]
    name = models.CharField(max_length=100, verbose_name="F.I.O")
    phone = models.CharField(max_length=20, verbose_name="Telefon raqami")
    admin_phone = models.CharField(max_length=20, blank=True, null=True, verbose_name="Admin Telefon Raqami")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='leads', verbose_name="Qiziqqan kursi")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='new', verbose_name="Holati")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yuborilgan vaqti")

    def __str__(self):
        return f"{self.name} - {self.phone} ({self.course.name})"

    class Meta:
        verbose_name = "Ariza"
        verbose_name_plural = "Arizalar"

class Test(models.Model):
    TEST_TYPES = [
        ('MCQ', 'Test (A,B,C,D)'),
        ('WRITTEN', 'Yozma ish'),
        ('MIXED', 'Aralash (Test + Yozma)'),
    ]
    title = models.CharField(max_length=200, verbose_name="Test nomi")
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='tests', verbose_name="Guruh")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_tests', verbose_name="Yaratuvchi")
    file = models.FileField(upload_to='tests/', verbose_name="Savollar PDF yoki Rasm fayli")
    mcq_count = models.IntegerField(default=30, verbose_name="Variantli (A,B,C,D) savollar soni")
    written_count = models.IntegerField(default=0, verbose_name="Ochiq / Yozma savollar soni")
    duration_minutes = models.IntegerField(default=60, verbose_name="Imtihon vaqti (daqiqa)")
    answers_key = models.TextField(blank=True, null=True, verbose_name="Javoblar kaliti (masalan: A,B,C,D yoki 36:158, 37:8)")
    answers_file = models.FileField(upload_to='test_answers/', blank=True, null=True, verbose_name="Javoblar fayli (TXT/PDF/Rasm)")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqti")

    def __str__(self):
        return f"{self.title} - {self.group.name}"

    class Meta:
        verbose_name = "Test"
        verbose_name_plural = "Testlar"

class StudentTestSubmission(models.Model):
    STATUS_CHOICES = [
        ('started', 'Boshladi'),
        ('completed', 'Topshirdi'),
        ('disqualified', 'Chetlashtirildi'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='test_submissions', verbose_name="O'quvchi")
    test = models.ForeignKey(Test, on_delete=models.CASCADE, related_name='submissions', verbose_name="Test")
    student_answers = models.TextField(blank=True, null=True, verbose_name="O'quvchi javoblari")
    uploaded_solution = models.FileField(upload_to='solutions/', blank=True, null=True, verbose_name="Yozma ish rasmi/PDF")
    score = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True, verbose_name="Baho (Ball %)")
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='started', verbose_name="Holati")
    cheated_at = models.DateTimeField(blank=True, null=True, verbose_name="Qoidabuzarlik vaqti")
    submitted_at = models.DateTimeField(auto_now=True, verbose_name="Topshirilgan vaqti")

    class Meta:
        unique_together = ('student', 'test')
        verbose_name = "Topshirilgan Test"
        verbose_name_plural = "Topshirilgan Testlar"

    def __str__(self):
        return f"{self.student} - {self.test.title} ({self.get_status_display()})"
