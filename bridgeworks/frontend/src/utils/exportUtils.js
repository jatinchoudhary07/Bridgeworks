/**
 * useExport — shared export utility
 * Provides exportCSV and exportPDF functions for any table data.
 */

function escapeHtml(value) {
    if (value === null || value === undefined) return '';
    return String(value)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function getColumnWidth(key) {
    const widths = {
        case_id: '10%',
        order_number: '10%',
        created_at_fmt: '12%',
        closed_at_fmt: '12%',
        customer: '20%',
        phone: '16%',
        refund_amount_fmt: '11%',
        refund_mode: '11%',
        qc_completed_by: '12%',
        refund_completed_by: '12%',
        status: '6%',
        status_lbl: '6%',
        return_awb: '14%',
        products_fmt: '30%',
        original_value_fmt: '12%',
        replacement_value_fmt: '14%',
        settlement_type_label: '14%',
        exchange_order_number: '14%',
        settlement_completed_by: '14%',
    };
    return widths[key] || '';
}

function formatCell(key, value) {
    if (value === null || value === undefined) return '—';
    const str = String(value);
    
    // Bold, green amount styling for outstanding clarity
    if (key === 'refund_amount_fmt') {
        return `<strong style="font-weight: 700; color: #059669; font-size: 11.5px;">${escapeHtml(str)}</strong>`;
    }
    // High-contrast dark bold for order or case numbers
    if (key === 'order_number' || key === 'case_id') {
        return `<strong style="font-weight: 700; color: #0f172a;">${escapeHtml(str)}</strong>`;
    }
    
    // Clean styling for statuses
    if (key === 'status' || key === 'status_lbl') {
        const lower = str.toLowerCase();
        
        let icon = '';
        let color = '#475569';
        let bg = '#f8fafc';
        let border = '#e2e8f0';
        
        if (lower.includes('close') || lower.includes('completed') || lower.includes('pass') || lower.includes('ready')) {
            icon = '✓';
        } else if (lower.includes('reject') || lower.includes('fail')) {
            icon = '✗';
        } else if (lower.includes('pending')) {
            icon = '⌛\uFE0E';
        }
        
        return `<span>${icon}</span>`;
    }

    // Split date and time for _at / _fmt fields (e.g. "05 Jun 26, 04:43 pm" -> two lines)
    if (key.includes('created_at') || key.includes('closed_at') || key.includes('_at_fmt')) {
        if (str.includes(', ')) {
            const parts = str.split(', ');
            return `${escapeHtml(parts[0])}<br/><span style="color: #64748b; font-size: 9.5px;">${escapeHtml(parts[1])}</span>`;
        }
    }

    return escapeHtml(str);
}

/**
 * exportCSV(columns, rows, filename)
 * columns: [{ key, label }]
 * rows: array of objects
 */
// Keys whose values should be treated as plain text in Excel (prevents scientific notation)
const TEXT_FORCE_KEYS = new Set(['phone', 'return_awb', 'awb', 'awb_number', 'exchange_order_number', 'order_number', 'case_id']);

export function exportCSV(columns, rows, filename = 'export.csv') {
    const header = columns.map(c => `"${c.label}"`).join(',');
    const body = rows.map(row =>
        columns.map(c => {
            const v = row[c.key] ?? '';
            const str = String(v).replace(/"/g, '""');
            // Prefix with tab so Excel treats the cell as text (prevents numeric / scientific notation rendering)
            const forceText = TEXT_FORCE_KEYS.has(c.key);
            return forceText ? `"\t${str}"` : `"${str}"`;
        }).join(',')
    ).join('\n');
    // Prepend UTF-8 BOM (\uFEFF) so Excel correctly recognizes the encoding and renders non-ASCII characters like ₹ (Rupee) perfectly.
    const csv = `\ufeff${header}\n${body}`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

/**
 * exportPDF(title, columns, rows, filename)
 * Provides a high-fidelity manager-style HTML/CSS print layout which defaults
 * to Portrait printing and renders beautiful typography & clear styling.
 */
export function exportPDF(title, columns, rows, filename = 'export.pdf') {
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
        alert('Please allow popups for this site to print the export.');
        return;
    }

    const exportDate = new Date().toLocaleDateString('en-IN', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
    });
    
    // Count stats
    const totalRecords = rows.length;
    
    // Calculate total products
    let totalProducts = 0;
    let hasProducts = false;
    rows.forEach(r => {
        if (Array.isArray(r.products)) {
            hasProducts = true;
            r.products.forEach(p => {
                totalProducts += parseInt(p.quantity, 10) || 1;
            });
        }
    });

    let htmlContent = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>${escapeHtml(title)} - ${escapeHtml(exportDate)}</title>
            <style>
                html, body {
                    height: auto !important;
                    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif; 
                    padding: 5px; 
                    font-size: 11px; 
                    color: #334155;
                    line-height: 1.3;
                    background-color: #fff;
                }
                .header-container {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 15px;
                    border-bottom: 2px solid #0f172a;
                    padding-bottom: 8px;
                }
                .header-left {
                    display: flex;
                    flex-direction: column;
                }
                h2 { 
                    margin: 0; 
                    font-size: 14px; 
                    color: #0f172a;
                    text-align: left;
                    font-weight: 800;
                    letter-spacing: -0.5px;
                }
                .subtitle { 
                    margin: 3px 0 0 0; 
                    color: #64748b; 
                    font-size: 10px; 
                    font-weight: 500;
                    text-align: left;
                }
                table { 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin-bottom: 10px; 
                    table-layout: fixed;
                    height: auto !important;
                }
                tr { 
                    page-break-inside: avoid;
                    height: 1px !important;
                }
                th, td { 
                    border: 1px solid #cbd5e1; 
                    padding: 5px 7px; 
                    text-align: left; 
                    vertical-align: top;
                    overflow: hidden;
                    word-wrap: break-word;
                    height: auto !important;
                    max-height: none !important;
                }
                th { 
                    background-color: #f8fafc; 
                    color: #475569;
                    font-weight: 700;
                    white-space: normal;
                    word-wrap: normal;
                    word-break: normal;
                    font-size: 9.5px;
                    text-transform: uppercase;
                    letter-spacing: 0.3px;
                }
                td {
                    color: #334155;
                }
                tbody tr:nth-child(even) {
                    background-color: #f8fafc;
                }
                .nowrap {
                    white-space: nowrap;
                }
                .text-right {
                    text-align: right;
                }
                .text-center {
                    text-align: center;
                }
                .summary-container { 
                    padding: 6px 12px; 
                    border: 1px solid #cbd5e1; 
                    background-color: #f8fafc; 
                    border-radius: 4px; 
                    min-width: 180px;
                }
                .summary-line { 
                    display: flex; 
                    justify-content: space-between; 
                    margin-bottom: 3px; 
                    font-size: 11px;
                }
                .summary-line:last-child { 
                    margin-bottom: 0; 
                }
                .summary-label { 
                    font-weight: 600; 
                    color: #475569; 
                    margin-right: 12px;
                }
                .summary-value { 
                    font-weight: 700; 
                    color: #0f172a; 
                }
                @page { 
                    size: portrait; 
                    margin: 0.5cm; 
                }
            </style>
        </head>
        <body>
            <div class="header-container">
                <div class="header-left">
                    <h2>${escapeHtml(title)}</h2>
                    <div class="subtitle">Generated: ${escapeHtml(exportDate)}</div>
                </div>
                <div class="summary-container">
                    <div class="summary-line">
                        <span class="summary-label">Total Records:</span>
                        <span class="summary-value">${totalRecords}</span>
                    </div>
                    ${hasProducts ? `
                    <div class="summary-line">
                        <span class="summary-label">Total Products:</span>
                        <span class="summary-value" style="color: #0f172a;">${totalProducts}</span>
                    </div>
                    ` : ''}
                </div>
            </div>
            
            <table>
                <thead>
                    <tr>
                        ${columns.map(col => `
                            <th style="width: ${getColumnWidth(col.key)}">${escapeHtml(col.label)}</th>
                        `).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${rows.map(row => `
                        <tr>
                            ${columns.map(col => {
                                const val = row[col.key];
                                const isAmount = col.key === 'refund_amount_fmt';
                                const isStatus = col.key === 'status' || col.key === 'status_lbl';
                                const isPhone = col.key === 'phone';
                                const isDate = col.key === 'created_at_fmt' || col.key === 'closed_at_fmt';
                                
                                const alignClass = isAmount ? 'text-right' : (isStatus ? 'text-center' : '');
                                const nowrapClass = isPhone || isDate ? 'nowrap' : '';
                                const combinedClass = [alignClass, nowrapClass].filter(Boolean).join(' ');
                                
                                return `
                                    <td class="${combinedClass}">${formatCell(col.key, val)}</td>
                                `;
                            }).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>

            <script>
                window.onload = function() {
                    window.print();
                };
            </script>
        </body>
        </html>
    `;

    printWindow.document.write(htmlContent);
    printWindow.document.close();
}

/**
 * exportOrderProductPDF(title, subtitle, cases, filename)
 * Renders RTO-style order-wise and product-wise summary PDF reports.
 */
export function exportOrderProductPDF(title, subtitle, cases, filename = 'export.pdf') {
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
        alert('Please allow popups for this site to print the export.');
        return;
    }

    const exportDate = new Date().toLocaleDateString('en-GB');

    // 1) Build Order-wise rows
    const orderRows = cases.map(c => {
        const skus = (c.products || []).map(p => {
            let s = p.sku || '';
            if (p.quantity > 1) s += ` (x${p.quantity})`;
            return s;
        }).filter(Boolean).join(' / ') || '-';

        const productNames = (c.products || []).map(p => p.title || p.name || '').filter(Boolean).join(' / ') || '-';
        const totalQty = (c.products || []).reduce((acc, p) => acc + (Number(p.quantity) || 1), 0);
        
        // Extract remarks/notes/status
        let qcRemarks = c.remarks || c.notes || '';
        if (!qcRemarks) {
            if (c.status) {
                // Clean status label
                qcRemarks = c.status.replace('_', ' ').replace(/\b\w/g, char => char.toUpperCase());
            } else {
                qcRemarks = '-';
            }
        }

        // Date formatting
        let orderDate = '-';
        if (c.created_at) {
            const d = new Date(c.created_at);
            if (!isNaN(d.getTime())) {
                orderDate = d.toLocaleDateString('en-GB');
            }
        }

        return {
            orderNumber: c.order_number || '—',
            orderDate,
            skus,
            totalQty,
            productNames,
            qcRemarks,
        };
    });

    // 2) Build Product-wise rows
    const productMap = new Map();
    cases.forEach(c => {
        (c.products || []).forEach(p => {
            const sku = (p.sku || '').trim();
            const title = (p.title || p.name || '').trim();
            const key = sku ? `sku:${sku}` : `title:${title}`;
            if (!key) return;

            const qty = Number(p.quantity) || 1;

            if (!productMap.has(key)) {
                productMap.set(key, {
                    sku: sku || '-',
                    title: title || '-',
                    totalQty: 0,
                });
            }
            productMap.get(key).totalQty += qty;
        });
    });
    const productRows = Array.from(productMap.values()).sort((a, b) => b.totalQty - a.totalQty);

    const uniqueOrders = cases.length;
    const totalQty = cases.reduce((acc, c) => acc + (c.products || []).reduce((sum, p) => sum + (Number(p.quantity) || 1), 0), 0);

    let htmlContent = `
        <!DOCTYPE html>
        <html>
        <head>
            <title>${escapeHtml(title)} - ${escapeHtml(exportDate)}</title>
            <style>
                body { 
                    font-family: Arial, sans-serif; 
                    padding: 5px; 
                    font-size: 11px; 
                    color: #334155;
                    line-height: 1.3;
                }
                .header-container {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 12px;
                    border-bottom: 2px solid #0f172a;
                    padding-bottom: 6px;
                }
                .header-left {
                    display: flex;
                    flex-direction: column;
                }
                h2 { 
                    margin: 0; 
                    font-size: 15px; 
                    color: #0f172a;
                    text-align: left;
                }
                .subtitle { 
                    margin: 2px 0 0 0; 
                    color: #64748b; 
                    font-size: 11px; 
                    font-weight: 500;
                    text-align: left;
                }
                h3 {
                    font-size: 12px;
                    color: #1e293b;
                    margin: 12px 0 5px 0;
                    border-bottom: 1px solid #cbd5e1;
                    padding-bottom: 2px;
                    font-weight: bold;
                }
                table { 
                    width: 100%; 
                    border-collapse: collapse; 
                    margin-bottom: 10px; 
                    table-layout: fixed; 
                }
                tr { 
                    page-break-inside: avoid; 
                }
                th, td { 
                    border: 1px solid #cbd5e1; 
                    padding: 4px 6px; 
                    text-align: left; 
                    overflow: hidden;
                    vertical-align: top;
                }
                th { 
                    background-color: #f8fafc; 
                    color: #475569;
                    font-weight: bold;
                    white-space: nowrap;
                }
                td {
                    color: #334155;
                }
                .nowrap {
                    white-space: nowrap;
                }
                .ellipsis {
                    white-space: nowrap;
                    text-overflow: ellipsis;
                }
                .wrap-text {
                    white-space: normal;
                    word-wrap: break-word;
                    word-break: break-word;
                }
                .text-center {
                    text-align: center;
                }
                .summary-container { 
                    padding: 5px 10px; 
                    border: 1px solid #cbd5e1; 
                    background-color: #f8fafc; 
                    border-radius: 4px; 
                    min-width: 160px;
                }
                .summary-line { 
                    display: flex; 
                    justify-content: space-between; 
                    margin-bottom: 2px; 
                    font-size: 11px;
                }
                .summary-line:last-child { 
                    margin-bottom: 0; 
                }
                .summary-label { 
                    font-weight: 600; 
                    color: #475569; 
                    margin-right: 10px;
                }
                .summary-value { 
                    font-weight: 700; 
                    color: #0f172a; 
                }
                @page { 
                    size: portrait; 
                    margin: 0.5cm; 
                }
            </style>
        </head>
        <body>
            <div class="header-container">
                <div class="header-left">
                    <h2>${escapeHtml(title)}</h2>
                    <div class="subtitle">${escapeHtml(subtitle)} - ${escapeHtml(exportDate)}</div>
                </div>
                <div class="summary-container">
                    <div class="summary-line">
                        <span class="summary-label">Total Cases Scanned:</span>
                        <span class="summary-value">${uniqueOrders}</span>
                    </div>
                    <div class="summary-line">
                        <span class="summary-label">Total Products Scanned:</span>
                        <span class="summary-value">${totalQty}</span>
                    </div>
                </div>
            </div>
            
            <h3>Order-wise Summary</h3>
            <table>
                <thead>
                    <tr>
                        <th style="width: 10%">Order #</th>
                        <th style="width: 12%">Order Date</th>
                        <th style="width: 20%">SKU(s)</th>
                        <th style="width: 8%; text-align: center;">Total Qty</th>
                        <th style="width: 35%">Product Name(s)</th>
                        <th style="width: 15%; text-align: center;">QC Remarks</th>
                    </tr>
                </thead>
                <tbody>
    `;

    orderRows.forEach((row) => {
        htmlContent += `
            <tr>
                <td class="nowrap"><strong>#${escapeHtml(row.orderNumber.toString().replace('#', ''))}</strong></td>
                <td class="nowrap">${escapeHtml(row.orderDate)}</td>
                <td class="wrap-text">${escapeHtml(row.skus)}</td>
                <td class="text-center nowrap">${escapeHtml(row.totalQty)}</td>
                <td class="ellipsis">${escapeHtml(row.productNames)}</td>
                <td class="text-center wrap-text">${escapeHtml(row.qcRemarks)}</td>
            </tr>
        `;
    });

    htmlContent += `
                </tbody>
            </table>

            <h3>Product-wise Summary</h3>
            <table>
                <thead>
                    <tr>
                        <th style="width: 25%">SKU</th>
                        <th style="width: 60%">Product Name</th>
                        <th style="width: 15%; text-align: center;">Total Qty</th>
                    </tr>
                </thead>
                <tbody>
    `;

    productRows.forEach((row) => {
        htmlContent += `
            <tr>
                <td class="wrap-text"><strong>${escapeHtml(row.sku)}</strong></td>
                <td class="ellipsis">${escapeHtml(row.title)}</td>
                <td class="text-center nowrap">${escapeHtml(row.totalQty)}</td>
            </tr>
        `;
    });

    htmlContent += `
                </tbody>
            </table>

            <script>
                window.onload = function() {
                    window.print();
                };
            </script>
        </body>
        </html>
    `;

    printWindow.document.write(htmlContent);
    printWindow.document.close();
}

