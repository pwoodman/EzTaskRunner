document.addEventListener('DOMContentLoaded', function() {
    const fileBrowserModal = document.getElementById('fileBrowserModal');
    const fileList = document.getElementById('fileList');
    const scriptPathInput = document.getElementById('script_path');
    let currentPath = '';

    function loadFileList(path = '') {
        fetch(`/browse_scripts?path=${encodeURIComponent(path)}`)
            .then(response => response.json())
            .then(data => {
                fileList.innerHTML = '';
                
                // Add back button if we're in a subfolder
                if (path) {
                    const backItem = document.createElement('div');
                    backItem.className = 'list-group-item list-group-item-action d-flex align-items-center';
                    backItem.innerHTML = `
                        <i class="bi bi-arrow-up-circle me-2"></i>
                        <span>..</span>
                    `;
                    backItem.addEventListener('click', () => {
                        const parentPath = path.split('/').slice(0, -1).join('/');
                        currentPath = parentPath;
                        loadFileList(parentPath);
                    });
                    fileList.appendChild(backItem);
                }

                // Sort items: folders first, then files
                const sortedItems = data.sort((a, b) => {
                    const aIsDir = a.endsWith('/');
                    const bIsDir = b.endsWith('/');
                    if (aIsDir === bIsDir) return a.localeCompare(b);
                    return aIsDir ? -1 : 1;
                });

                sortedItems.forEach(item => {
                    const isDirectory = item.endsWith('/');
                    const itemName = isDirectory ? item.slice(0, -1) : item;
                    const itemPath = path ? `${path}/${itemName}` : itemName;

                    const listItem = document.createElement('div');
                    listItem.className = 'list-group-item list-group-item-action d-flex align-items-center';
                    listItem.innerHTML = `
                        <i class="bi ${isDirectory ? 'bi-folder' : 'bi-file-earmark'} me-2"></i>
                        <span>${itemName}</span>
                    `;

                    if (isDirectory) {
                        listItem.addEventListener('click', () => {
                            currentPath = itemPath;
                            loadFileList(itemPath);
                        });
                    } else {
                        listItem.addEventListener('click', () => {
                            scriptPathInput.value = itemPath;
                            bootstrap.Modal.getInstance(fileBrowserModal).hide();
                        });
                    }

                    fileList.appendChild(listItem);
                });
            })
            .catch(error => {
                console.error('Error loading file list:', error);
                fileList.innerHTML = '<div class="list-group-item text-danger">Error loading files</div>';
            });
    }

    // Initialize file browser when modal is shown
    fileBrowserModal.addEventListener('show.bs.modal', () => {
        loadFileList(currentPath);
    });

    // Reset current path when modal is hidden
    fileBrowserModal.addEventListener('hidden.bs.modal', () => {
        currentPath = '';
    });
});