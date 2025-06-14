$(document).ready(function() {
    const editUserModal = new bootstrap.Modal(document.getElementById('editUserModal'));
    const userListBody = $('#user-list-body');

    // --- 通用函数 ---
    function showAlert(message, category = 'success', duration = 5000) {
        const alertContainer = $('#alert-container');
        const alertHtml = `
            <div class="alert alert-${category} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>`;
        alertContainer.html(alertHtml);
        if (duration > 0) {
            setTimeout(() => { alertContainer.find('.alert').alert('close'); }, duration);
        }
    }

    // --- 事件处理 ---

    // 注册开关切换
    $('#registrationSwitch').on('change', function() {
        const isEnabled = $(this).is(':checked');
        $.ajax({
            url: '/admin/toggle_registration',
            type: 'POST',
            data: {
                enabled: isEnabled,
                csrf_token: csrf_token
            },
            success: function(response) {
                showAlert(response.message, 'success');
            },
            error: function(xhr) {
                showAlert(xhr.responseJSON.error, 'danger');
                // 切换失败时，恢复开关状态
                $(this).prop('checked', !isEnabled);
            }
        });
    });

    // 添加用户
    $('#addUserForm').on('submit', function(e) {
        e.preventDefault();
        const username = $('#newUsername').val();
        const password = $('#newPassword').val();
        const role = $('#newRole').val();

        $.ajax({
            url: '/admin/add_user',
            type: 'POST',
            data: { username, password, role, csrf_token },
            success: function(response) {
                showAlert(response.message, 'success');
                $('#addUserForm')[0].reset();
                const newUser = response.user;
                const newRow = `
                    <tr data-user-id="${newUser.id}">
                        <td>${newUser.id}</td>
                        <td data-field="username">${newUser.username}</td>
                        <td data-field="role">${newUser.role}</td>
                        <td class="text-center"><i class="bi bi-check-lg text-success"></i></td>
                        <td class="text-center"><i class="bi bi-check-lg text-success"></i></td>
                        <td class="text-center"><i class="bi bi-check-lg text-success"></i></td>
                        <td class="text-center"><i class="bi bi-check-lg text-success"></i></td>
                        <td class="text-center"><i class="bi bi-check-lg text-success"></i></td>
                        <td class="text-end">
                            <button class="btn btn-sm btn-outline-secondary edit-user-btn" data-bs-toggle="modal" data-bs-target="#editUserModal">
                                <i class="bi bi-pencil-square"></i> 编辑
                            </button>
                            <button class="btn btn-sm btn-outline-danger delete-user-btn">
                                <i class="bi bi-trash"></i> 删除
                            </button>
                        </td>
                    </tr>`;
                userListBody.append(newRow);
            },
            error: (xhr) => showAlert(xhr.responseJSON.error, 'danger')
        });
    });

    // 弹出编辑模态框并填充数据
    userListBody.on('click', '.edit-user-btn', function() {
        const row = $(this).closest('tr');
        const userId = row.data('user-id');
        const username = row.find('[data-field="username"]').text();
        const role = row.find('[data-field="role"]').text();
        
        // 从隐藏的 input 中获取权限数据
        const can_upload = row.find('input[name="can_upload"]').val() === 'true';
        const can_delete = row.find('input[name="can_delete"]').val() === 'true';
        const can_rename = row.find('input[name="can_rename"]').val() === 'true';
        const can_move = row.find('input[name="can_move"]').val() === 'true';
        const can_create_folder = row.find('input[name="can_create_folder"]').val() === 'true';


        $('#editUserId').val(userId);
        $('#editUsername').val(username);
        $('#editRole').val(role);
        $('#editPassword').val('');
        
        // 填充权限复选框
        $('#editCanUpload').prop('checked', can_upload);
        $('#editCanDelete').prop('checked', can_delete);
        $('#editCanRename').prop('checked', can_rename);
        $('#editCanMove').prop('checked', can_move);
        $('#editCanCreateFolder').prop('checked', can_create_folder);
    });

    // 提交编辑表单
    $('#editUserForm').on('submit', function(e) {
        e.preventDefault();
        const userId = $('#editUserId').val();
        const data = {
            username: $('#editUsername').val(),
            password: $('#editPassword').val(),
            role: $('#editRole').val(),
            can_upload: $('#editCanUpload').is(':checked'),
            can_delete: $('#editCanDelete').is(':checked'),
            can_rename: $('#editCanRename').is(':checked'),
            can_move: $('#editCanMove').is(':checked'),
            can_create_folder: $('#editCanCreateFolder').is(':checked'),
            csrf_token: csrf_token
        };

        $.ajax({
            url: `/admin/edit_user/${userId}`,
            type: 'POST',
            data: data,
            success: function(response) {
                editUserModal.hide();
                showAlert(response.message, 'success');
                // 刷新页面以显示最准确的权限状态
                location.reload();
            },
            error: (xhr) => showAlert(xhr.responseJSON.error, 'danger')
        });
    });

    // 删除用户
    userListBody.on('click', '.delete-user-btn', function() {
        if (!confirm('您确定要删除这个用户吗？其所有文件也将被删除，此操作不可撤销。')) {
            return;
        }
        const row = $(this).closest('tr');
        const userId = row.data('user-id');

        $.ajax({
            url: `/admin/delete_user/${userId}`,
            type: 'POST',
            data: { csrf_token },
            success: function(response) {
                showAlert(response.message, 'success');
                row.fadeOut(300, function() { $(this).remove(); });
            },
            error: (xhr) => showAlert(xhr.responseJSON.error, 'danger')
        });
    });
});