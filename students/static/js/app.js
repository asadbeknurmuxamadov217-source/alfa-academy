// ================= TOAST NOTIFICATION HELPER =================
function showToast(message, type = 'success') {
    // Check if toast container already exists, if not create it
    let toast = document.querySelector('.toast-msg');
    if (!toast) {
        toast = document.createElement('div');
        toast.className = 'toast-msg';
        document.body.appendChild(toast);
    }
    
    // Set message and type
    toast.innerHTML = `<i class="fa-solid ${type === 'success' ? 'fa-circle-check' : 'fa-triangle-exclamation'}"></i> ${message}`;
    toast.className = `toast-msg show ${type}`;
    
    // Hide toast after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// ================= SIDEBAR MENU TOGGLE FOR MOBILE =================
document.addEventListener('DOMContentLoaded', () => {
    const menuToggle = document.getElementById('menuToggle');
    const sidebar = document.querySelector('.sidebar');
    
    if (menuToggle && sidebar) {
        menuToggle.addEventListener('click', (e) => {
            e.stopPropagation();
            sidebar.classList.toggle('active');
        });
        
        // Close sidebar when clicking outside on mobile
        document.addEventListener('click', (e) => {
            if (sidebar.classList.contains('active') && !sidebar.contains(e.target) && e.target !== menuToggle) {
                sidebar.classList.remove('active');
            }
        });
    }
});

// ================= MODAL DIALOGS CONTROL =================
function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Open Edit Student Modal with prefilled data
function openEditStudentModal(id, firstName, lastName, phone, groupId) {
    const form = document.getElementById('editStudentForm');
    if (form) {
        form.action = `/students/edit/${id}/`;
        document.getElementById('edit_student_fname').value = firstName;
        document.getElementById('edit_student_lname').value = lastName;
        document.getElementById('edit_student_phone').value = phone;
        document.getElementById('edit_student_group').value = groupId;
        openModal('editStudentModal');
    }
}

// ================= ACCORDION FOR GROUPS =================
function toggleAccordion(groupId) {
    const card = document.getElementById(`group-card-${groupId}`);
    if (card) {
        card.classList.toggle('active');
    }
}

// ================= ATTENDANCE AJAX OPERATIONS =================
function setAttendanceStatus(studentId, status) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    const date = document.getElementById('dateInput').value;
    const row = document.querySelector(`.attendance-row-item[data-student-id="${studentId}"]`);
    
    if (!row) return;
    
    const buttons = row.querySelectorAll('.status-btn');
    
    // Optimistic UI: update buttons
    buttons.forEach(btn => {
        btn.classList.remove('active');
    });
    
    // Find clicked button
    let clickedBtn;
    if (status === 'P') clickedBtn = row.querySelector('.btn-present');
    if (status === 'A') clickedBtn = row.querySelector('.btn-absent');
    if (status === 'L') clickedBtn = row.querySelector('.btn-late');
    if (status === 'E') clickedBtn = row.querySelector('.btn-excused');
    
    if (clickedBtn) {
        clickedBtn.classList.add('active');
    }
    
    // Send AJAX request
    fetch('/attendance/save/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            student_id: studentId,
            date: date,
            status: status
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Tarmoq xatosi');
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            showToast("Davomat saqlandi", "success");
            updateAttendanceSummary();
        } else {
            showToast("Saqlashda xatolik yuz berdi", "error");
        }
    })
    .catch(error => {
        console.error(error);
        showToast("Tarmoq ulanishida xatolik", "error");
    });
}

function updateAttendanceSummary() {
    const rows = document.querySelectorAll('.attendance-row-item');
    if (rows.length === 0) return;
    
    let countP = 0, countA = 0, countL = 0, countE = 0;
    
    rows.forEach(row => {
        if (row.querySelector('.btn-present.active')) countP++;
        else if (row.querySelector('.btn-absent.active')) countA++;
        else if (row.querySelector('.btn-late.active')) countL++;
        else if (row.querySelector('.btn-excused.active')) countE++;
    });
    
    const elP = document.getElementById('summary-P');
    const elA = document.getElementById('summary-A');
    const elL = document.getElementById('summary-L');
    const elE = document.getElementById('summary-E');
    
    if (elP) elP.innerText = countP;
    if (elA) elA.innerText = countA;
    if (elL) elL.innerText = countL;
    if (elE) elE.innerText = countE;
}

// ================= GRADEBOOK AJAX OPERATIONS =================
function saveStudentGrade(studentId, gradeType, score, date) {
    const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
    const parentBox = document.querySelector(`.grade-input-box[data-student-id="${studentId}"][data-type="${gradeType}"]`);
    
    if (!parentBox) return;
    
    const activeBtn = parentBox.querySelector(`.grade-circle-btn.btn-score-${score}`);
    const isCurrentlyActive = activeBtn.classList.contains('active');
    
    // Agar doira allaqachon faol bo'lsa, bosilganda bahoni o'chirish (null yuborish)
    const gradeToSend = isCurrentlyActive ? null : score;
    
    // Optimistic UI updates
    const buttons = parentBox.querySelectorAll('.grade-circle-btn');
    buttons.forEach(btn => btn.classList.remove('active'));
    
    if (!isCurrentlyActive && activeBtn) {
        activeBtn.classList.add('active');
    }
    
    // AJAX
    fetch('/grades/save/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrfToken
        },
        body: JSON.stringify({
            student_id: studentId,
            date: date,
            grade: gradeToSend,
            grade_type: gradeType
        })
    })
    .then(response => {
        if (!response.ok) throw new Error('Tarmoq xatosi');
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            showToast("Baho saqlandi", "success");
        } else if (data.status === 'deleted') {
            showToast("Baho o'chirildi", "success");
        } else {
            showToast("Baholashda xatolik yuz berdi", "error");
        }
    })
    .catch(error => {
        console.error(error);
        showToast("Tarmoq ulanishida xatolik", "error");
    });
}

// ================= GRADE COMMENTS DIALOG =================
let activeCommentStudentId = null;
let activeCommentGradeType = null;
let activeCommentDate = null;

function editGradeComment(studentId, gradeType, date) {
    activeCommentStudentId = studentId;
    activeCommentGradeType = gradeType;
    activeCommentDate = date;
    
    // Get student name from row
    const row = document.getElementById(`comment-btn-${studentId}-${gradeType}`).closest('.grade-row-item');
    const studentName = row.querySelector('.student-fullname').innerText;
    
    // Get grade type text
    let typeName = '';
    if (gradeType === 'HW') typeName = 'Uy vazifasi';
    if (gradeType === 'ACT') typeName = 'Darsdagi faollik';
    if (gradeType === 'EXAM') typeName = 'Imtihon';
    
    // Fill info in modal
    document.getElementById('commentModalStudent').innerText = `O'quvchi: ${studentName}`;
    document.getElementById('commentModalType').innerText = `Baho turi: ${typeName}`;
    
    // Prefill comment textarea
    const currentComment = document.getElementById(`comment-text-${studentId}-${gradeType}`).innerText.trim();
    document.getElementById('commentTextarea').value = currentComment === 'Izoh yo\'q' ? '' : currentComment;
    
    openModal('commentModal');
}

function closeCommentModal() {
    closeModal('commentModal');
    activeCommentStudentId = null;
    activeCommentGradeType = null;
    activeCommentDate = null;
}

// Save comment trigger
document.addEventListener('DOMContentLoaded', () => {
    const saveCommentBtn = document.getElementById('saveCommentModalBtn');
    if (saveCommentBtn) {
        saveCommentBtn.addEventListener('click', () => {
            if (!activeCommentStudentId || !activeCommentGradeType || !activeCommentDate) return;
            
            const commentVal = document.getElementById('commentTextarea').value;
            const csrfToken = document.querySelector('meta[name="csrf-token"]').getAttribute('content');
            
            const parentBox = document.querySelector(`.grade-input-box[data-student-id="${activeCommentStudentId}"][data-type="${activeCommentGradeType}"]`);
            const activeCircle = parentBox ? parentBox.querySelector('.grade-circle-btn.active') : null;
            
            // Comment yozish uchun baho bo'lishi shart, agar baho bo'lmasa 5 bahoni default qo'yamiz yoki ogohlantiramiz
            // Lekin keling, baho bo'lmasa saqlashga yo'l qo'ymaymiz yoki bahoni 5 qilamiz
            let gradeVal = activeCircle ? activeCircle.innerText : null;
            
            if (!gradeVal) {
                showToast("Avval o'quvchiga baho qo'ying", "error");
                closeCommentModal();
                return;
            }
            
            fetch('/grades/save/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    student_id: activeCommentStudentId,
                    date: activeCommentDate,
                    grade: parseInt(gradeVal),
                    grade_type: activeCommentGradeType,
                    comment: commentVal
                })
            })
            .then(response => {
                if (!response.ok) throw new Error('Tarmoq xatosi');
                return response.json();
            })
            .then(data => {
                if (data.status === 'success') {
                    showToast("Izoh saqlandi", "success");
                    
                    // Update UI comment tooltip and button indicator
                    const commentBtn = document.getElementById(`comment-btn-${activeCommentStudentId}-${activeCommentGradeType}`);
                    const tooltipText = document.getElementById(`comment-text-${activeCommentStudentId}-${activeCommentGradeType}`);
                    
                    if (commentVal.trim() !== "") {
                        commentBtn.classList.add('has-comment');
                        tooltipText.innerText = commentVal;
                    } else {
                        commentBtn.classList.remove('has-comment');
                        tooltipText.innerText = "Izoh yo'q";
                    }
                } else {
                    showToast("Izohni saqlashda xatolik", "error");
                }
                closeCommentModal();
            })
            .catch(error => {
                console.error(error);
                showToast("Tarmoq ulanishida xatolik", "error");
                closeCommentModal();
            });
        });
    }
});
