$(document).ready(function () {

    // --- 全局变量和通用函数 ---
    const fileActionForm = $('#fileActionForm');
    const selectAllCheckbox = $('#selectAll');
    const itemCheckboxes = $('.item-checkbox');
    const deleteSelectedBtn = $('#deleteSelectedBtn');
    const moveSelectedBtn = $('#moveSelectedBtn');

    function toggleActionButtons() {
        const checkedCount = $('.item-checkbox:checked').length;
        if (checkedCount > 0) {
            deleteSelectedBtn.prop('disabled', false);
            moveSelectedBtn.prop('disabled', false);
        } else {
            deleteSelectedBtn.prop('disabled', true);
            moveSelectedBtn.prop('disabled', true);
        }
    }

    // --- 复选框逻辑 ---
    selectAllCheckbox.on('change', function () {
        itemCheckboxes.prop('checked', $(this).prop('checked'));
        toggleActionButtons();
    });
    itemCheckboxes.on('change', function () {
        if (!$(this).prop('checked')) {
            selectAllCheckbox.prop('checked', false);
        } else if ($('.item-checkbox:checked').length === itemCheckboxes.length) {
            selectAllCheckbox.prop('checked', true);
        }
        toggleActionButtons();
    });

    // --- 目录树填充逻辑 ---
    function buildDirOptions(dirs, selectElement, level = 0) {
        dirs.forEach(dir => {
            const prefix = ' '.repeat(level * 4) + (level > 0 ? '└─ ' : '');
            selectElement.append($('<option>', { value: dir.path, html: prefix + dir.name }));
            if (dir.children && dir.children.length > 0) {
                buildDirOptions(dir.children, selectElement, level + 1);
            }
        });
    }
    function populateDirSelects() {
        $.getJSON('/api/get_dirs', function (dirs) {
            const $uploadSelect = $('#destinationPathUpload');
            const $moveSelect = $('#destinationFolderMove');
            $uploadSelect.empty();
            $moveSelect.empty();
            $uploadSelect.append($('<option>', { value: '', html: '根目录' }));
            $moveSelect.append($('<option>', { value: '', html: '根目录' }));
            buildDirOptions(dirs, $uploadSelect);
            buildDirOptions(dirs, $moveSelect);
            $uploadSelect.val(current_path);
        });
    }
    $('#uploadModal, #moveModal').on('show.bs.modal', function () {
        populateDirSelects();
    });

    // --- 删除逻辑 ---
    const deleteConfirmModal = new bootstrap.Modal(document.getElementById('deleteConfirmModal'));
    deleteSelectedBtn.on('click', function(e) {
        e.preventDefault();
        fileActionForm.attr('action', '/delete');
        deleteConfirmModal.show();
    });
    $('#confirmDeleteBtn').on('click', function() { fileActionForm.submit(); });

    // --- 移动逻辑 ---
    const moveModal = new bootstrap.Modal(document.getElementById('moveModal'));
    moveSelectedBtn.on('click', function(e) {
        e.preventDefault();
        fileActionForm.attr('action', '/move');
        moveModal.show();
    });
    $('#confirmMoveBtn').on('click', function() {
        const destination = $('#destinationFolderMove').val();
        fileActionForm.append(`<input type="hidden" name="destination_folder" value="${destination}">`);
        fileActionForm.submit();
    });

    // --- 文件上传逻辑 (已改进) ---
    // (代码与上一版相同，此处省略以保持简洁)
    const uploadBtn = $('#startUploadBtn');
    const uploadForm = $('#uploadForm');
    const fileInput = $('#fileInput');
    const progressBar = $('#uploadProgressBar');
    const progressContainer = $('#uploadProgressContainer');
    const successMessage = $('#uploadSuccessMessage');
    uploadBtn.on('click', function () {
        const files = fileInput[0].files;
        if (files.length === 0) {
            alert('请先选择要上传的文件！');
            return;
        }
        const formData = new FormData();
        for (let i = 0; i < files.length; i++) {
            formData.append('files[]', files[i]);
        }
        formData.append('destination_path', $('#destinationPathUpload').val());
        $.ajax({
            url: '/upload/',
            type: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            xhr: function() {
                const xhr = new window.XMLHttpRequest();
                progressBar.width('0%').text('0%').removeClass('bg-success');
                progressContainer.show();
                successMessage.hide();
                xhr.upload.addEventListener('progress', function(evt) {
                    if (evt.lengthComputable) {
                        const percentComplete = Math.round((evt.loaded / evt.total) * 100);
                        progressBar.width(percentComplete + '%').text(percentComplete + '%');
                    }
                }, false);
                return xhr;
            },
            success: function(res) {
                progressBar.width('100%').text('100%').addClass('bg-success');
                successMessage.show();
                setTimeout(function() { window.location.reload(); }, 1000);
            },
            error: function(err) {
                alert('上传失败: ' + (err.responseJSON ? err.responseJSON.error : '未知错误'));
                progressContainer.hide();
            }
        });
    });

    // --- 新增：计算目录大小的逻辑 ---
    $('.table').on('click', '.calc-dir-size-btn', function(e) {
        e.preventDefault();
        const $btn = $(this);
        const dirPath = $btn.data('path');
        const $sizeDisplay = $(`.dir-size-display[data-path="${dirPath}"]`);

        // 显示加载状态
        $btn.prop('disabled', true).html('<i class="bi bi-hourglass-split"></i>');

        $.getJSON(`/api/get_dir_size/${dirPath}`)
            .done(function(data) {
                // 更新大小并移除按钮
                $sizeDisplay.text(data.size);
                $btn.remove();
            })
            .fail(function() {
                // 处理错误
                $sizeDisplay.text('计算失败');
                $btn.prop('disabled', false).html('<i class="bi bi-calculator"></i>');
            });
    });

});
