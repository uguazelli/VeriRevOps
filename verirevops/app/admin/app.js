

const API_BASE = '/api';

const schemas = {
    tenants: {
        title: 'Tenants Management',
        headers: ['ID', 'Name', 'Slug', 'URL', 'Active', 'Actions'],
        fields: [
            { name: 'name', label: 'Name', type: 'text', required: true },
            { name: 'slug', label: 'Slug', type: 'text', required: true },
            { name: 'url', label: 'URL', type: 'text', required: true },
            { name: 'is_active', label: 'Active', type: 'checkbox' }
        ]
    },
    subscriptions: {
        title: 'Subscriptions Management',
        headers: ['ID', 'Tenant', 'Quota', 'Usage', 'Start Date', 'End Date', 'Actions'],
        fields: [
            { name: 'tenant_id', label: 'Tenant', type: 'select', required: true },
            { name: 'quota_limit', label: 'Quota Limit', type: 'number', required: true },
            { name: 'usage_count', label: 'Usage Count', type: 'number', required: false },
            { name: 'start_date', label: 'Start Date', type: 'datetime-local', required: false },
            { name: 'end_date', label: 'End Date', type: 'datetime-local', required: false }
        ]
    },
    chat_sessions: {
        title: 'Chat Sessions',
        headers: ['ID', 'Tenant', 'Created At', 'Actions'],
        fields: [
            { name: 'tenant_id', label: 'Tenant', type: 'select', required: true }
        ]
    },
    chat_messages: {
        title: 'Chat Messages',
        headers: ['ID', 'Tenant', 'Session ID', 'Role', 'Content', 'Created At'],
        fields: [] // Read-only
    }
};

let currentEntity = 'tenants';
let currentData = [];
let allTenants = [];

$(document).ready(function () {
    fetchAllTenants();
    loadEntity('tenants');

    // Navigation
    $('.nav-links li').click(function () {
        $('.nav-links li').removeClass('active');
        $(this).addClass('active');
        const target = $(this).data('target');
        loadEntity(target);
    });

    // Create Button
    $('#create-btn').click(function () {
        if (schemas[currentEntity].fields.length === 0) {
            alert('Creating new records for this entity is restricted.');
            return;
        }
        openModal();
    });

    // Modal Close
    $('.close-btn').click(closeModal);
    $(window).click(function (e) {
        if ($(e.target).is('#modal')) closeModal();
    });

    // Form Submit
    $('#data-form').submit(function (e) {
        e.preventDefault();
        saveData();
    });
});

function fetchAllTenants() {
    $.get(`${API_BASE}/tenants`, function (data) {
        allTenants = data;
    });
}



function loadEntity(entity) {
    currentEntity = entity;

    // Handle RAG View
    if (entity === 'rag') {
        $('#page-title').text('RAG Management');
        $('#create-btn').hide();
        $('.table-container').hide();
        $('#rag-view').show();
        populateRagTenants();
        return; // Stop here, no need to fetch standard CRUD data
    }

    // Handle Standard CRUD Views
    $('.table-container').show();
    $('#rag-view').hide();

    const schema = schemas[entity];
    $('#page-title').text(schema.title);
    renderHeaders(schema.headers);

    // Toggle Create Button
    if (schema.fields.length === 0) {
        $('#create-btn').hide();
    } else {
        $('#create-btn').show();
    }

    $.get(`${API_BASE}/${entity}`, function (data) {
        currentData = data;
        renderTable(data);
    }).fail(function () {
        alert('Failed to load data');
    });
}

function renderHeaders(headers) {
    const $thead = $('#data-table thead');
    $thead.empty();
    const $tr = $('<tr>');
    headers.forEach(h => $tr.append(`<th>${h}</th>`));
    $thead.append($tr);
}

function renderTable(data) {
    const $tbody = $('#data-table tbody');
    $tbody.empty();

    if (data.length === 0) {
        $tbody.append('<tr><td colspan="10" style="text-align:center;">No records found</td></tr>');
        return;
    }

    data.forEach(item => {
        const $tr = $('<tr>');

        const tenantName = item.tenant_name || (item.tenant_id ? (allTenants.find(t => t.id === item.tenant_id)?.name || item.tenant_id) : '-');

        // Dynamically render columns based on entity type
        if (currentEntity === 'tenants') {
            $tr.append(`<td>${item.id}</td>`);
            $tr.append(`<td>${item.name}</td>`);
            $tr.append(`<td><span class="badge">${item.slug}</span></td>`);
            $tr.append(`<td>${item.url}</td>`);
            $tr.append(`<td>${item.is_active ? '✅' : '❌'}</td>`);
            $tr.append(`
                <td>
                    <button class="btn-edit" onclick="editRecord(${item.id})">Edit</button>
                    <button class="btn-delete" onclick="deleteRecord(${item.id})">Delete</button>
                </td>
            `);
        } else if (currentEntity === 'subscriptions') {
            $tr.append(`<td>${item.id}</td>`);
            $tr.append(`<td>${tenantName}</td>`);
            $tr.append(`<td>${item.quota_limit}</td>`);
            $tr.append(`<td>${item.usage_count}</td>`);
            $tr.append(`<td>${item.start_date || '-'}</td>`);
            $tr.append(`<td>${item.end_date || '-'}</td>`);
            $tr.append(`
                <td>
                    <button class="btn-edit" onclick="editRecord(${item.id})">Edit</button>
                    <button class="btn-delete" onclick="deleteRecord(${item.id})">Delete</button>
                </td>
            `);
        } else if (currentEntity === 'chat_sessions') {
            $tr.append(`<td>${item.id}</td>`);
            $tr.append(`<td>${tenantName}</td>`);
            $tr.append(`<td>${new Date(item.created_at).toLocaleString()}</td>`);
            $tr.append(`
                <td>
                    <button class="btn-edit" onclick="editRecord(${item.id})">Edit</button>
                    <button class="btn-delete" onclick="deleteRecord(${item.id})">Delete</button>
                </td>
            `);
        } else if (currentEntity === 'chat_messages') {
            $tr.append(`<td>${item.id}</td>`);
            $tr.append(`<td>${tenantName}</td>`);
            $tr.append(`<td>${item.session_id}</td>`);
            $tr.append(`<td><strong>${item.role}</strong></td>`);
            $tr.append(`<td>${item.content.substring(0, 50)}...</td>`);
            $tr.append(`<td>${new Date(item.created_at).toLocaleString()}</td>`);
        }

        $tbody.append($tr);
    });
}

function openModal(data = null) {
    const schema = schemas[currentEntity];
    const $form = $('#data-form');
    $form.empty();
    $form.data('id', data ? data.id : null);

    $('#modal-title').text(data ? 'Edit Record' : 'Create Record');

    schema.fields.forEach(field => {
        let inputHtml = '';
        const value = data ? data[field.name] : '';

        if (field.type === 'text' || field.type === 'number') {
            inputHtml = `<input type="${field.type}" name="${field.name}" value="${value !== undefined ? value : ''}" ${field.required ? 'required' : ''}>`;
        } else if (field.type === 'datetime-local') {
            // Basic handling for datetime-local value format (YYYY-MM-DDTHH:MM)
            let dateVal = value ? new Date(value).toISOString().slice(0, 16) : '';
            inputHtml = `<input type="datetime-local" name="${field.name}" value="${dateVal}" ${field.required ? 'required' : ''}>`;
        } else if (field.type === 'checkbox') {
            const checked = (data && data[field.name]) || (!data && field.name === 'is_active');
            inputHtml = `
                <div class="checkbox-group">
                    <input type="checkbox" name="${field.name}" ${checked ? 'checked' : ''}>
                    <label>${field.label}</label>
                </div>
            `;
            $form.append(`<div class="form-group">${inputHtml}</div>`);
            return;
        } else if (field.type === 'select' && field.name === 'tenant_id') {
            let options = allTenants.map(t => `<option value="${t.id}" ${value == t.id ? 'selected' : ''}>${t.name}</option>`).join('');
            inputHtml = `<select name="${field.name}" ${field.required ? 'required' : ''}>${options}</select>`;
        }

        $form.append(`
            <div class="form-group">
                <label>${field.label}</label>
                ${inputHtml}
            </div>
        `);
    });

    $('#modal').css('display', 'flex');
}

function closeModal() {
    $('#modal').hide();
}

function saveData() {
    const id = $('#data-form').data('id');
    const formData = {};

    $('#data-form').serializeArray().forEach(item => {
        formData[item.name] = item.value;
    });

    // Handle checkboxes
    $('#data-form input[type="checkbox"]').each(function () {
        formData[this.name] = this.checked;
    });

    const method = id ? 'PUT' : 'POST';
    const url = id ? `${API_BASE}/${currentEntity}/${id}` : `${API_BASE}/${currentEntity}`;

    $.ajax({
        url: url,
        type: method,
        contentType: 'application/json',
        data: JSON.stringify(formData),
        success: function () {
            closeModal();
            loadEntity(currentEntity);
        },
        error: function (xhr) {
            alert('Error saving data: ' + xhr.responseText);
        }
    });
}

window.editRecord = function (id) {
    const item = currentData.find(d => d.id === id);
    if (item) openModal(item);
};

window.deleteRecord = function (id) {
    if (!confirm('Are you sure you want to delete this record?')) return;
    $.ajax({
        url: `${API_BASE}/${currentEntity}/${id}`,
        type: 'DELETE',
        success: function () {
            loadEntity(currentEntity);
        },
        error: function (xhr) {
            alert('Error deleting record');
        }
    });
};

function populateRagTenants() {
    const $select = $('#rag-tenant-select');
    // Keep the default option
    const currentVal = $select.val();
    $select.empty();
    $select.append('<option value="">Select Tenant</option>');

    allTenants.forEach(t => {
        $select.append(`<option value="${t.id}">${t.name}</option>`);
    });

    // Restore selection if still valid
    if (currentVal) $select.val(currentVal);
}
