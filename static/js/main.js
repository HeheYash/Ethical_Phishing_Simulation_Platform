// Main JavaScript functionality for Ethical Phishing Simulation Platform

document.addEventListener('DOMContentLoaded', function() {
    // Initialize tooltips
    initializeTooltips();

    // Initialize confirmation dialogs
    initializeConfirmations();

    // Initialize file uploads
    initializeFileUploads();

    // Initialize charts if Chart.js is available
    if (typeof Chart !== 'undefined') {
        initializeCharts();
    }

    // Auto-hide flash messages
    autoHideMessages();

    // Initialize form validation
    initializeFormValidation();
});

/**
 * Initialize Bootstrap tooltips
 */
function initializeTooltips() {
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

/**
 * Initialize confirmation dialogs for destructive actions
 */
function initializeConfirmations() {
    document.querySelectorAll('[data-confirm]').forEach(function(element) {
        element.addEventListener('click', function(e) {
            var message = this.getAttribute('data-confirm');
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });
    });
}

/**
 * Initialize file upload areas with drag and drop
 */
function initializeFileUploads() {
    document.querySelectorAll('.file-upload-area').forEach(function(area) {
        var input = area.querySelector('input[type="file"]');
        if (!input) return;

        // Click handler
        area.addEventListener('click', function() {
            input.click();
        });

        // Drag and drop handlers
        area.addEventListener('dragover', function(e) {
            e.preventDefault();
            area.classList.add('dragover');
        });

        area.addEventListener('dragleave', function(e) {
            e.preventDefault();
            area.classList.remove('dragover');
        });

        area.addEventListener('drop', function(e) {
            e.preventDefault();
            area.classList.remove('dragover');

            var files = e.dataTransfer.files;
            if (files.length > 0) {
                input.files = files;
                updateFileDisplay(area, files[0]);
            }
        });

        // File change handler
        input.addEventListener('change', function() {
            if (this.files.length > 0) {
                updateFileDisplay(area, this.files[0]);
            }
        });
    });
}

/**
 * Update file upload display
 */
function updateFileDisplay(area, file) {
    var display = area.querySelector('.file-name');
    if (display) {
        display.textContent = file.name;
    }

    var size = area.querySelector('.file-size');
    if (size) {
        size.textContent = formatFileSize(file.size);
    }
}

/**
 * Format file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    var k = 1024;
    var sizes = ['Bytes', 'KB', 'MB', 'GB'];
    var i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Initialize charts on dashboard pages
 */
function initializeCharts() {
    // Campaign timeline chart
    var timelineCtx = document.getElementById('campaignTimelineChart');
    if (timelineCtx) {
        fetch('/analytics/api/data?type=campaign_timeline')
            .then(response => response.json())
            .then(data => {
                new Chart(timelineCtx, {
                    type: 'line',
                    data: {
                        labels: data.timeline.map(item => item.hour),
                        datasets: [
                            {
                                label: 'Opened',
                                data: data.timeline.map(item => item.opened),
                                borderColor: '#28a745',
                                backgroundColor: 'rgba(40, 167, 69, 0.1)',
                                tension: 0.4
                            },
                            {
                                label: 'Clicked',
                                data: data.timeline.map(item => item.clicked),
                                borderColor: '#007bff',
                                backgroundColor: 'rgba(0, 123, 255, 0.1)',
                                tension: 0.4
                            },
                            {
                                label: 'Submitted',
                                data: data.timeline.map(item => item.submitted),
                                borderColor: '#dc3545',
                                backgroundColor: 'rgba(220, 53, 69, 0.1)',
                                tension: 0.4
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        scales: {
                            y: {
                                beginAtZero: true,
                                ticks: {
                                    stepSize: 1
                                }
                            }
                        }
                    }
                });
            })
            .catch(error => console.error('Error loading timeline data:', error));
    }

    // Activity summary chart
    var summaryCtx = document.getElementById('activitySummaryChart');
    if (summaryCtx) {
        fetch('/analytics/api/data?type=activity_summary')
            .then(response => response.json())
            .then(data => {
                new Chart(summaryCtx, {
                    type: 'doughnut',
                    data: {
                        labels: data.events.map(item => item.name),
                        datasets: [{
                            data: data.events.map(item => item.value),
                            backgroundColor: [
                                '#007bff',
                                '#28a745',
                                '#ffc107',
                                '#dc3545',
                                '#6c757d'
                            ]
                        }]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false
                    }
                });
            })
            .catch(error => console.error('Error loading summary data:', error));
    }
}

/**
 * Auto-hide flash messages after 5 seconds
 */
function autoHideMessages() {
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
}

/**
 * Initialize client-side form validation
 */
function initializeFormValidation() {
    // Add custom validation methods
    window.addEventListener('load', function() {
        var forms = document.getElementsByClassName('needs-validation');
        Array.prototype.filter.call(forms, function(form) {
            form.addEventListener('submit', function(event) {
                if (form.checkValidity() === false) {
                    event.preventDefault();
                    event.stopPropagation();
                }
                form.classList.add('was-validated');
            }, false);
        });
    });
}

/**
 * Show loading state on buttons
 */
function showLoading(button, originalText) {
    button.disabled = true;
    button.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
    button.dataset.originalText = originalText;
}

/**
 * Hide loading state on buttons
 */
function hideLoading(button) {
    button.disabled = false;
    button.innerHTML = button.dataset.originalText || 'Submit';
}

/**
 * Format percentage for display
 */
function formatPercentage(value, decimals = 1) {
    return parseFloat(value).toFixed(decimals) + '%';
}

/**
 * Format number with thousands separators
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(function() {
        showToast('Copied to clipboard!', 'success');
    }).catch(function(err) {
        console.error('Could not copy text: ', err);
        showToast('Failed to copy to clipboard', 'danger');
    });
}

/**
 * Show toast notification
 */
function showToast(message, type = 'info') {
    var toastHtml = `
        <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
            <div class="d-flex">
                <div class="toast-body">
                    ${message}
                </div>
                <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
            </div>
        </div>
    `;

    var toastContainer = document.getElementById('toastContainer');
    if (!toastContainer) {
        toastContainer = document.createElement('div');
        toastContainer.id = 'toastContainer';
        toastContainer.className = 'toast-container position-fixed bottom-0 end-0 p-3';
        toastContainer.style.zIndex = '1050';
        document.body.appendChild(toastContainer);
    }

    var toastElement = document.createElement('div');
    toastElement.innerHTML = toastHtml;
    toastContainer.appendChild(toastElement);

    var toast = new bootstrap.Toast(toastElement.querySelector('.toast'));
    toast.show();

    // Remove from DOM after hidden
    toastElement.addEventListener('hidden.bs.toast', function() {
        toastElement.remove();
    });
}

/**
 * AJAX request wrapper with loading states
 */
function ajaxRequest(url, options = {}) {
    var showLoading = options.showLoading !== false;
    var loadingElement = options.loadingElement;

    if (showLoading && loadingElement) {
        loadingElement.classList.add('loading');
    }

    return fetch(url, {
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken(),
            ...options.headers
        },
        ...options
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        return response.json();
    })
    .catch(error => {
        console.error('AJAX request error:', error);
        showToast('An error occurred while processing your request', 'danger');
        throw error;
    })
    .finally(() => {
        if (showLoading && loadingElement) {
            loadingElement.classList.remove('loading');
        }
    });
}

/**
 * Get CSRF token from meta tag
 */
function getCsrfToken() {
    var meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.getAttribute('content') : '';
}

/**
 * Export data to CSV
 */
function exportToCSV(data, filename) {
    var csv = convertToCSV(data);
    var blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    var link = document.createElement('a');
    var url = URL.createObjectURL(blob);

    link.setAttribute('href', url);
    link.setAttribute('download', filename);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
}

/**
 * Convert array of objects to CSV
 */
function convertToCSV(data) {
    if (data.length === 0) return '';

    var headers = Object.keys(data[0]);
    var csvHeaders = headers.join(',');

    var csvRows = data.map(function(row) {
        return headers.map(function(header) {
            var value = row[header];
            return typeof value === 'string' && value.includes(',') ? `"${value}"` : value;
        }).join(',');
    });

    return csvHeaders + '\n' + csvRows.join('\n');
}

/**
 * Debounce function for search inputs
 */
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

/**
 * Search functionality
 */
function initializeSearch(searchInput, searchFunction, delay = 300) {
    if (!searchInput) return;

    var debouncedSearch = debounce(searchFunction, delay);
    searchInput.addEventListener('input', function() {
        debouncedSearch(this.value);
    });
}

// Export functions for global use
window.PhashSim = {
    showLoading: showLoading,
    hideLoading: hideLoading,
    copyToClipboard: copyToClipboard,
    showToast: showToast,
    ajaxRequest: ajaxRequest,
    exportToCSV: exportToCSV,
    initializeSearch: initializeSearch,
    formatNumber: formatNumber,
    formatPercentage: formatPercentage
};