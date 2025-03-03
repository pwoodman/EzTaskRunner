document.addEventListener('DOMContentLoaded', function() {
    // Set default schedule time one hour in the future
    const now = new Date();
    now.setHours(now.getHours() + 1);
    const dateTimeStr = now.toISOString().slice(0, 16);
    const scheduleTimeEl = document.getElementById('schedule_time');
    if (scheduleTimeEl) {
        scheduleTimeEl.value = dateTimeStr;
    }
    const dateSection = document.getElementById('date_section');
    if (dateSection) {
        dateSection.style.display = 'block';
    }

    // Handle form submission
    const taskForm = document.querySelector('form');
    if (taskForm) {
        taskForm.addEventListener('submit', async function(e) {
            e.preventDefault();
            
            // Validate form data
            const scriptPath = document.getElementById('script_path').value;
            if (!scriptPath) {
                showError('Script path is required');
                return;
            }

            const triggerType = document.querySelector('input[name="trigger_type"]:checked')?.value;
            if (!triggerType) {
                showError('Please select a schedule type');
                return;
            }

            // Validate schedule based on trigger type
            if (triggerType === 'date') {
                const scheduleTime = document.getElementById('schedule_time').value;
                if (!scheduleTime) {
                    showError('Schedule time is required for one-time tasks');
                    return;
                }
                if (new Date(scheduleTime) <= new Date()) {
                    showError('Schedule time must be in the future');
                    return;
                }
            } else if (triggerType === 'interval') {
                const hours = parseInt(document.getElementById('interval_hours').value) || 0;
                const minutes = parseInt(document.getElementById('interval_minutes').value) || 0;
                const seconds = parseInt(document.getElementById('interval_seconds').value) || 0;
                if (hours === 0 && minutes === 0 && seconds === 0) {
                    showError('At least one interval value must be greater than 0');
                    return;
                }
            } else if (triggerType === 'cron') {
                const cronExpression = document.getElementById('cron_expression').value;
                if (!cronExpression || cronExpression.split(' ').length !== 5) {
                    showError('Invalid cron expression');
                    return;
                }
            }

            try {
                const formData = new FormData(taskForm);
                const response = await fetch('/add_task', {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const text = await response.text();
                    throw new Error(text || 'Failed to create task');
                }

                // Redirect to dashboard on success
                window.location.href = '/';
            } catch (error) {
                showError(error.message || 'An error occurred while creating the task');
            }
        });
    }

    // Helper function to show error messages
    function showError(message) {
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        const form = document.querySelector('form');
        if (form) {
            form.insertAdjacentElement('beforebegin', alertDiv);
        }
    }

    // Handle trigger type changes
    const triggerRadios = document.querySelectorAll('.trigger-radio');
    triggerRadios.forEach(radio => {
        radio.addEventListener('change', function() {
            document.querySelectorAll('.trigger-section').forEach(section => {
                section.style.display = 'none';
            });
            const sectionToShow = document.getElementById(this.value + '_section');
            if (sectionToShow) {
                sectionToShow.style.display = 'block';
            }
        });
    });

    // Cron Builder functionality
    let cronParts = ['0', '0', '*', '*', '*'];

    function updateCronExpression() {
        const cronExpressionEl = document.getElementById('cron_expression');
        if (cronExpressionEl) {
            cronExpressionEl.value = cronParts.join(' ');
        }
        updateCronDescription();
    }

    function updateCronDescription() {
        let description = 'This will run ';
        const minute = cronParts[0];
        if (minute === '*') { 
            description += 'every minute'; 
        } else if (minute.startsWith('*/')) { 
            description += `every ${minute.substring(2)} minutes`; 
        } else { 
            description += `at minute ${minute}`; 
        }

        const hour = cronParts[1];
        if (hour === '*') { 
            description += ' of every hour'; 
        } else if (hour.startsWith('*/')) { 
            description += ` every ${hour.substring(2)} hours`; 
        } else {
            const hourNum = parseInt(hour, 10);
            const hourStr = hourNum === 0 ? 'midnight' : 
                            hourNum === 12 ? 'noon' : 
                            hourNum < 12 ? `${hourNum} AM` : `${hourNum - 12} PM`;
            description += ` at ${hourStr}`;
        }

        const dom = cronParts[2];
        if (dom !== '*') {
            if (dom === 'L') { 
                description += ' on the last day of the month'; 
            } else { 
                description += ` on the ${dom} day of the month`; 
            }
        }

        const month = cronParts[3];
        if (month !== '*') {
            const monthNames = ['January','February','March','April','May','June','July','August','September','October','November','December'];
            if (month.includes(',')) {
                const months = month.split(',').map(m => monthNames[parseInt(m, 10) - 1]);
                description += ` in ${months.join(', ')}`;
            } else { 
                description += ` in ${monthNames[parseInt(month, 10) - 1]}`;
            }
        }

        const dow = cronParts[4];
        if (dow !== '*') {
            const dayNames = ['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
            if (dow === '1-5') { 
                description += ' on weekdays'; 
            } else if (dow === '0,6') { 
                description += ' on weekends'; 
            } else if (dow.includes(',')) { 
                const days = dow.split(',').map(d => dayNames[parseInt(d, 10)]);
                description += ` on ${days.join(', ')}`;
            } else if (dow.includes('-')) { 
                const [start, end] = dow.split('-');
                description += ` from ${dayNames[parseInt(start, 10)]} to ${dayNames[parseInt(end, 10)]}`;
            } else { 
                description += ` on ${dayNames[parseInt(dow, 10)]}`;
            }
        }
        const cronDescEl = document.getElementById('cronDescription');
        if (cronDescEl) {
            cronDescEl.textContent = description + '.';
        }
    }

    // Handle cron part changes
    document.querySelectorAll('.cron-part').forEach(select => {
        select.addEventListener('change', function() {
            const position = parseInt(this.dataset.position, 10);
            const value = this.value;
            const customInput = this.nextElementSibling;
            if (value === 'custom') {
                if (customInput) {
                    customInput.style.display = 'block';
                    customInput.focus();
                }
            } else {
                if (customInput) {
                    customInput.style.display = 'none';
                }
                cronParts[position] = value;
                updateCronExpression();
            }
        });
    });

    // Handle custom cron inputs
    document.querySelectorAll('.custom-cron-input').forEach(input => {
        input.addEventListener('blur', function() {
            const select = this.previousElementSibling;
            const position = parseInt(select.dataset.position, 10);
            const value = this.value.trim();
            if (value) {
                cronParts[position] = value;
                updateCronExpression();
            } else {
                select.value = cronParts[position];
                this.style.display = 'none';
            }
        });
        input.addEventListener('keypress', function(e) { 
            if (e.key === 'Enter') { 
                this.blur(); 
            }
        });
    });

    // Handle cron presets
    const cronPresetsEl = document.getElementById('cronPresets');
    if (cronPresetsEl) {
        cronPresetsEl.addEventListener('change', function() {
            const value = this.value;
            if (value) {
                const cronExpressionEl = document.getElementById('cron_expression');
                if (cronExpressionEl) {
                    cronExpressionEl.value = value;
                }
                cronParts = value.split(' ');
                const cronMinuteEl = document.getElementById('cronMinute');
                const cronHourEl = document.getElementById('cronHour');
                const cronDomEl = document.getElementById('cronDom');
                const cronMonthEl = document.getElementById('cronMonth');
                const cronDowEl = document.getElementById('cronDow');
                if (cronMinuteEl) cronMinuteEl.value = cronParts[0];
                if (cronHourEl) cronHourEl.value = cronParts[1];
                if (cronDomEl) cronDomEl.value = cronParts[2];
                if (cronMonthEl) cronMonthEl.value = cronParts[3];
                if (cronDowEl) cronDowEl.value = cronParts[4];
                document.querySelectorAll('.custom-cron-input').forEach(input => {
                    input.style.display = 'none';
                });
                updateCronDescription();
            }
        });
    }

    // Initialize cron expression
    updateCronExpression();

    // Add click event listeners to task rows
    document.querySelectorAll('.task-row').forEach(row => {
        row.addEventListener('click', function() {
            const taskId = this.dataset.taskId;
            if (taskId) {
                window.location.href = `/task_history/${taskId}`;
            }
        });
    });

    // Add form submission handler with proper error handling and loading state management
const formElement = document.querySelector('form');
    if (taskForm) {
        // Function to show error messages
        function showError(message) {
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-danger alert-dismissible fade show';
            alertDiv.innerHTML = `
                ${message}
                <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
            `;
            taskForm.insertBefore(alertDiv, taskForm.firstChild);
        }

        taskForm.addEventListener('submit', function(e) {
            e.preventDefault(); // Prevent default form submission

            // Validate form data before submission
            const triggerType = document.querySelector('input[name="trigger_type"]:checked')?.value;
            if (!triggerType) {
                showError('Please select a trigger type (One-time, Interval, or Cron).');
                return;
            }

            // Validate schedule based on trigger type
            if (triggerType === 'date') {
                const scheduleTime = document.getElementById('schedule_time')?.value;
                if (!scheduleTime) {
                    showError('Please select a date and time for the one-time schedule.');
                    return;
                }
                const selectedDate = new Date(scheduleTime);
                if (selectedDate <= new Date()) {
                    showError('The scheduled time must be in the future.');
                    return;
                }
            } else if (triggerType === 'interval') {
                const hours = parseInt(document.getElementById('interval_hours')?.value, 10) || 0;
                const minutes = parseInt(document.getElementById('interval_minutes')?.value, 10) || 0;
                const seconds = parseInt(document.getElementById('interval_seconds')?.value, 10) || 0;
                if (hours === 0 && minutes === 0 && seconds === 0) {
                    showError('Please specify an interval by setting at least one value (hours, minutes, or seconds) greater than 0.');
                    return;
                }
                if (hours < 0 || minutes < 0 || seconds < 0) {
                    showError('Interval values cannot be negative.');
                    return;
                }
                if (minutes >= 60 || seconds >= 60) {
                    showError('Minutes and seconds must be less than 60.');
                    return;
                }
            } else if (triggerType === 'cron') {
                const cronExpression = document.getElementById('cron_expression')?.value.trim();
                if (!cronExpression) {
                    showError('Please provide a cron expression or use the Cron Builder to create one.');
                    return;
                }
                const parts = cronExpression.split(' ');
                if (parts.length !== 5) {
                    showError('Invalid cron expression format. The expression must have exactly 5 parts: minute hour day_of_month month day_of_week');
                    return;
                }
                // Validate each part of the cron expression
                const [minute, hour, dom, month, dow] = parts;
                const validateCronPart = (value, min, max, name) => {
                    if (
                        value === '*' || 
                        value === '?' || 
                        value.startsWith('*/') || 
                        (name === 'day of month' && value === 'L')
                    ) {
                        return true;
                    }
                    const numbers = value.split(',').flatMap(part => {
                        if (part.includes('-')) {
                            const [start, end] = part.split('-').map(Number);
                            return Array.from({ length: end - start + 1 }, (_, i) => start + i);
                        }
                        return [Number(part)];
                    });
                    return numbers.every(num => !isNaN(num) && num >= min && num <= max);
                };
                
                if (!validateCronPart(minute, 0, 59, 'minute')) {
                    showError('Invalid minute in cron expression. Must be 0-59, *, or */n');
                    return;
                }
                if (!validateCronPart(hour, 0, 23, 'hour')) {
                    showError('Invalid hour in cron expression. Must be 0-23, *, or */n');
                    return;
                }
                if (!validateCronPart(dom, 1, 31, 'day of month')) {
                    showError('Invalid day of month in cron expression. Must be 1-31, *, or L');
                    return;
                }
                if (!validateCronPart(month, 1, 12, 'month')) {
                    showError('Invalid month in cron expression. Must be 1-12 or *');
                    return;
                }
                if (!validateCronPart(dow, 0, 6, 'day of week')) {
                    showError('Invalid day of week in cron expression. Must be 0-6 (Sunday=0) or *');
                    return;
                }
            }

            const submitButton = this.querySelector('button[type="submit"]');
            if (!submitButton) return;

            // Disable button and show spinner
            submitButton.disabled = true;
            const spinner = document.createElement('span');
            spinner.className = 'spinner-border spinner-border-sm ms-2';
            spinner.setAttribute('role', 'status');
            spinner.setAttribute('aria-hidden', 'true');
            submitButton.appendChild(spinner);

            // Function to reset button state
            const resetSubmitButton = () => {
                submitButton.disabled = false;
                const existingSpinner = submitButton.querySelector('.spinner-border');
                if (existingSpinner) {
                    existingSpinner.remove();
                }
            };

            // Submit the form using fetch
            fetch(this.action, {
                method: 'POST',
                body: new FormData(this),
                credentials: 'same-origin',
                headers: {
                    'Accept': 'application/json, text/html'
                }
            })
            .then(response => {
                if (!response.ok) {
                    return response.text().then(text => {
                        throw new Error(text || 'Network response was not ok');
                    });
                }
                return response.text();
            })
            .then(html => {
                // Check if response contains error message
                if (html.includes('alert-danger')) {
                    // Error occurred, reset button and update page content
                    resetSubmitButton();
                    const tempDiv = document.createElement('div');
                    tempDiv.innerHTML = html;
                    const newContent = tempDiv.querySelector('.container');
                    if (newContent) {
                        document.querySelector('.container').replaceWith(newContent);
                    }
                } else {
                    // Success, ensure all operations are complete before redirect
                    resetSubmitButton();
                    window.location.href = '/';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                resetSubmitButton();
                showError('Error submitting form. Please try again.');
            });
        });
    }
});
