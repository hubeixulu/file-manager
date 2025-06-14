$(document).ready(function () {
    // --- 全局变量和模态框实例 ---
    const selectAllCheckbox = $('#selectAll');
    const deleteSelectedBtn = $('#deleteSelectedBtn');
    const moveSelectedBtn = $('#moveSelectedBtn');
    const fileListBody = $('#file-list-body');
    const emptyFolderRow = $('#empty-folder-row');

    const renameModal = new bootstrap.Modal(document.getElementById('renameModal'));
    const deleteConfirmModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    const moveModal = new bootstrap.Modal(document.getElementById('moveModal'));
    const newFolderModal = new bootstrap.Modal(document.getElementById('newFolderModal'));
    const uploadModal = new bootstrap.Modal(document.getElementById('uploadModal'));
    const previewModalElement = document.getElementById('previewModal');

    // --- 通用函数 ---
    function toggleActionButtons() {
        const checkedCount = fileListBody.find('.item-checkbox:checked').length;
        deleteSelectedBtn.prop('disabled', checkedCount === 0);
        moveSelectedBtn.prop('disabled', checkedCount === 0);
    }

    function showAlert(message, category = 'success', duration = 5000) {
        const alertContainer = $('#alert-container');
        const alertHtml = `
            <div class="alert alert-${category} alert-dismissible fade show" role="alert">
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            </div>`;
        alertContainer.html(alertHtml);
        if (duration > 0 && category === 'success') {
            setTimeout(() => {
                alertContainer.find('.alert').alert('close');
            }, duration);
        }
    }

    function createTableRow(item) {
        const previewBtnHtml = item.previewable ? `
            <button type="button" class="btn btn-sm btn-outline-info preview-btn"
                    data-bs-toggle="modal" data-bs-target="#previewModal"
                    data-path="${item.path}" data-name="${item.name}">
                <i class="bi bi-eye"></i> 预览
            </button>` : '';

        const renameBtnHtml = user_permissions.can_rename ? `
            <button type="button" class="btn btn-sm btn-outline-secondary rename-btn" 
                    data-bs-toggle="modal" data-bs-target="#renameModal" 
                    data-old-name="${item.name}">
                <i class="bi bi-pencil-square"></i> 重命名
            </button>` : '';

        const downloadBtnHtml = item.is_dir ? '' : `
            <a href="/download/${item.path}" class="btn btn-sm btn-outline-primary"><i class="bi bi-download"></i> 下载</a>`;
        
        const sizeHtml = item.is_dir ? 
            `<span class="dir-size-display" data-path="${item.path}">-</span>
             <button type="button" class="btn btn-sm btn-outline-secondary p-0 px-1 ms-1 calc-dir-size-btn" data-path="${item.path}" title="计算目录大小">
                 <i class="bi bi-calculator"></i>
             </button>` : 
            item.size;

        const nameHtml = item.is_dir ? 
            `<i class="bi bi-folder-fill text-primary"></i> <a href="/${item.path}" class="text-decoration-none text-dark fw-bold">${item.name}</a>` :
            `<i class="bi bi-file-earmark-text text-secondary"></i> <span>${item.name}</span>`;

        return `
            <tr data-name="${item.name}">
                <td><input class="form-check-input item-checkbox" type="checkbox" name="items[]" value="${item.name}"></td>
                <td>${nameHtml}</td>
                <td><small class="text-muted">${sizeHtml}</small></td>
                <td class="text-end">${previewBtnHtml} ${renameBtnHtml} ${downloadBtnHtml}</td>
            </tr>`;
    }

    function getSelectedItems() {
        return fileListBody.find('.item-checkbox:checked').map(function() {
            return $(this).val();
        }).get();
    }
    
    // --- 事件处理 ---

    // 复选框逻辑
    selectAllCheckbox.on('change', function () {
        fileListBody.find('.item-checkbox').prop('checked', $(this).prop('checked'));
        toggleActionButtons();
    });

    fileListBody.on('change', '.item-checkbox', function () {
        toggleActionButtons();
        selectAllCheckbox.prop('checked', fileListBody.find('.item-checkbox:not(:checked)').length === 0);
    });

    // 新建文件夹
    $('#newFolderForm').on('submit', function(e) {
        e.preventDefault();
        const folderName = $('#folderName').val();
        $.ajax({
            url: '/create_folder', type: 'POST',
            data: { current_path: current_path, folder_name: folderName, csrf_token: csrf_token },
            success: function(response) {
                newFolderModal.hide();
                showAlert(response.message, 'success');
                const newRow = createTableRow(response.item);
                fileListBody.append(newRow);
                emptyFolderRow.hide();
                $('#newFolderForm')[0].reset();
            },
            error: (xhr) => showAlert(xhr.responseJSON.error, 'danger')
        });
    });

    // 重命名模态框设置和提交
    $(previewModalElement).siblings('.modal').on('show.bs.modal', function (event) {
        const modalId = $(this).attr('id');
        if (modalId === 'renameModal') {
            const button = event.relatedTarget;
            const oldName = button.getAttribute('data-old-name');
            $('#renameOldName').val(oldName);
            // *** Bug 修复：这里使用了正确的变量名 oldName ***
            $('#renameNewName').val(oldName).focus();
        }
    });

    $('#renameForm').on('submit', function(e) {
        e.preventDefault();
        const oldName = $('#renameOldName').val();
        const newName = $('#renameNewName').val();
        
        if (!newName || oldName === newName) {
            renameModal.hide();
            return;
        }

        $.ajax({
            url: '/rename', type: 'POST',
            data: { current_path: current_path, old_name: oldName, new_name: newName, csrf_token: csrf_token },
            success: function(response) {
                renameModal.hide();
                showAlert(response.message, 'success');
                const oldRow = fileListBody.find(`tr[data-name="${oldName}"]`);
                const isDir = oldRow.find('i').hasClass('bi-folder-fill');
                const newPath = current_path ? `${current_path}/${newName}` : newName;
                const newItem = {
                    name: newName, is_dir: isDir, path: newPath,
                    size: oldRow.find('small').text(), 
                    previewable: !isDir && isPreviewable(newName)
                };
                oldRow.replaceWith(createTableRow(newItem));
            },
            error: (xhr) => showAlert(xhr.responseJSON.error, 'danger')
        });
    });

    // 预览模态框设置
    previewModalElement.addEventListener('show.bs.modal', function (event) {
        const button = event.relatedTarget;
        const filePath = button.getAttribute('data-path');
        const fileName = button.getAttribute('data-name');
        const modalTitle = previewModalElement.querySelector('.modal-title');
        const previewFrame = document.getElementById('previewFrame');

        modalTitle.textContent = `预览: ${fileName}`;
        previewFrame.src = `/view/${filePath}`;
    });

    previewModalElement.addEventListener('hidden.bs.modal', function () {
        document.getElementById('previewFrame').src = 'about:blank';
    });

    // 删除
    deleteSelectedBtn.on('click', () => deleteConfirmModal.show());
    $('#confirmDeleteBtn').on('click', function() {
        const itemsToDelete = getSelectedItems();
        $.ajax({
            url: '/delete', type: 'POST',
            data: { current_path: current_path, 'items[]': itemsToDelete, csrf_token: csrf_token },
            traditional: true, 
            success: function(response) {
                deleteConfirmModal.hide();
                showAlert(response.message, 'success');
                response.deleted.forEach(name => {
                    fileListBody.find(`tr[data-name="${name}"]`).remove();
                });
                toggleActionButtons();
                if (fileListBody.children().length === 0) {
                    emptyFolderRow.show();
                }
            },
            error: (xhr) => showAlert(xhr.responseJSON.error, 'danger')
        });
    });

    // 移动
    moveSelectedBtn.on('click', () => moveModal.show());
    $('#confirmMoveBtn').on('click', function() {
        const itemsToMove = getSelectedItems();
        const destination = $('#destinationFolderMove').val();
        $.ajax({
            url: '/move', type: 'POST',
            data: { current_path: current_path, 'items[]': itemsToMove, destination_folder: destination, csrf_token: csrf_token },
            traditional: true,
            success: function(response) {
                moveModal.hide();
                showAlert(response.message, 'success');
                response.moved.forEach(name => {
                    fileListBody.find(`tr[data-name="${name}"]`).remove();
                });
                toggleActionButtons();
                 if (fileListBody.children().length === 0) {
                    emptyFolderRow.show();
                }
            },
            error: (xhr) => showAlert(xhr.responseJSON.error, 'danger')
        });
    });

    // 填充目录选择下拉框
    $('#uploadModal, #moveModal').on('show.bs.modal', function () {
        $.getJSON('/api/get_dirs', function (dirs) {
            const $uploadSelect = $('#destinationPathUpload');
            const $moveSelect = $('#destinationFolderMove');
            function buildDirOptions(dirs, selectElement, level = 0) {
                dirs.forEach(dir => {
                    const prefix = ' '.repeat(level * 4) + (level > 0 ? '└─ ' : '');
                    selectElement.append($('<option>', { value: dir.path, html: prefix + dir.name }));
                    if (dir.children && dir.children.length > 0) {
                        buildDirOptions(dir.children, selectElement, level + 1);
                    }
                });
            }
            $uploadSelect.empty().append($('<option>', { value: '', html: '根目录' }));
            $moveSelect.empty().append($('<option>', { value: '', html: '根目录' }));
            buildDirOptions(dirs, $uploadSelect);
            buildDirOptions(dirs, $moveSelect);
            $uploadSelect.val(current_path);
        });
    });

    // 文件上传逻辑
    $('#startUploadBtn').on('click', function () {
        const files = $('#fileInput')[0].files;
        if (files.length === 0) {
            showAlert('请先选择要上传的文件！', 'warning');
            return;
        }
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files[]', files[i]);
        }
        formData.append('destination_path', $('#destinationPathUpload').val());
        formData.append('csrf_token', csrf_token);

        $.ajax({
            url: '/upload/', type: 'POST',
            data: formData, processData: false, contentType: false,
            xhr: function() {
                const xhr = new window.XMLHttpRequest();
                const progressBar = $('#uploadProgressBar');
                $('#uploadProgressContainer').show();
                $('#uploadSuccessMessage').hide();
                progressBar.width('0%').text('0%').removeClass('bg-success');
                xhr.upload.addEventListener('progress', function(evt) {
                    if (evt.lengthComputable) {
                        const percentComplete = Math.round((evt.loaded / evt.total) * 100);
                        progressBar.width(percentComplete + '%').text(percentComplete + '%');
                    }
                }, false);
                return xhr;
            },
            success: function(res) {
                $('#uploadProgressBar').addClass('bg-success');
                $('#uploadSuccessMessage').show();
                setTimeout(() => window.location.reload(), 1000); 
            },
            error: (err) => {
                showAlert(err.responseJSON ? err.responseJSON.error : '上传失败', 'danger');
                $('#uploadProgressContainer').hide();
            }
        });
    });

    // 计算目录大小
    fileListBody.on('click', '.calc-dir-size-btn', function(e) {
        e.preventDefault();
        const $btn = $(this);
        const dirPath = $btn.data('path');
        const $sizeDisplay = $(`.dir-size-display[data-path="${dirPath}"]`);
        $btn.prop('disabled', true).html('<i class="bi bi-hourglass-split"></i>');
        $.getJSON(`/api/get_dir_size/${dirPath}`)
            .done(function(data) {
                $sizeDisplay.text(data.size);
                $btn.remove();
            })
            .fail(function() {
                $sizeDisplay.text('计算失败');
                $btn.prop('disabled', false).html('<i class="bi bi-calculator"></i>');
            });
    });

    // JS端的权限检查辅助函数
    function isPreviewable(filename) {
        const previewableExtensions = ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml'];
        const imageExtensions = ['.png', '.jpg', '.jpeg', '.gif', '.bmp', '.svg', '.webp'];
        const ext = ('.' + filename.split('.').pop()).toLowerCase();
        return previewableExtensions.includes(ext) || imageExtensions.includes(ext);
    }
});