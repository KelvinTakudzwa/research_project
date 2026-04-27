import { jsPDF } from 'jspdf';
import autoTable from 'jspdf-autotable';
import {
    Document, Packer, Paragraph, Table, TableRow, TableCell,
    TextRun, HeadingLevel, WidthType, AlignmentType,
    BorderStyle, ShadingType,
} from 'docx';

// ── Shared helpers ─────────────────────────────────────────────────────────────

const fmt = {
    ts:   (v) => v ? new Date(v).toLocaleString([], { dateStyle: 'medium', timeStyle: 'medium' }) : '—',
    pct:  (v) => v != null ? `${parseFloat(v).toFixed(1)}%` : '—',
    conf: (v) => v != null ? `${(parseFloat(v) * 100).toFixed(0)}%` : '—',
    v:    (v) => v != null ? `${parseFloat(v).toFixed(2)}V` : '—',
    c:    (v) => v != null ? `${parseFloat(v).toFixed(1)}°C` : '—',
    w:    (v) => v != null ? `${parseFloat(v).toFixed(1)}W` : '—',
    irr:  (v) => v != null ? `${parseFloat(v).toFixed(1)}` : '—',
};

const TABLE_HEADERS = [
    'Timestamp', 'Fault', 'Severity', 'ML Label', 'Confidence',
    'SoC', 'Batt V', 'Batt °C', 'PV W', 'AC W', 'Irr W/m²',
];

const rowValues = (r) => [
    fmt.ts(r.timestamp),
    r.alert_type || '—',
    r.alert_severity || '—',
    r.pred_label?.replace(/_/g, ' ') || '—',
    fmt.conf(r.confidence),
    fmt.pct(r.soc_percent),
    fmt.v(r.battery_voltage_v),
    fmt.c(r.battery_temp_c),
    fmt.w(r.pv_power_w),
    fmt.w(r.ac_power_w),
    fmt.irr(r.irradiance_wm2),
];

const buildSummary = (data, filterLabel) => {
    const total     = data.length;
    const critical  = data.filter(r => r.alert_severity === 'Critical').length;
    const warning   = data.filter(r => r.alert_severity === 'Warning').length;
    const mlFaults  = ['F1 Partial Shading','F2 Inverter Overload','F3 Deep Discharge','F5 Sensor Dead','Uncertain Anomaly'];
    const mlCount   = data.filter(r => mlFaults.includes(r.alert_type)).length;
    const ruleCount = total - mlCount;

    const counts = {};
    data.forEach(r => { counts[r.alert_type] = (counts[r.alert_type] || 0) + 1; });
    const topFault = Object.entries(counts).sort((a, b) => b[1] - a[1])[0];

    const timestamps = data.map(r => new Date(r.timestamp)).filter(d => !isNaN(d));
    const period = timestamps.length >= 2
        ? `${fmt.ts(Math.min(...timestamps))} → ${fmt.ts(Math.max(...timestamps))}`
        : 'N/A';

    return { total, critical, warning, mlCount, ruleCount, topFault, period, counts, filterLabel };
};

// ── CSV ────────────────────────────────────────────────────────────────────────

export const exportCSV = (data, filterLabel = 'All') => {
    const meta = [
        ['Nexus Grid — Predictive Maintenance Fault Report'],
        [`Generated: ${new Date().toLocaleString()}`],
        [`Filter: ${filterLabel}`],
        [`Total Records: ${data.length}`],
        [],
    ];
    const rows  = data.map(rowValues);
    const lines = [...meta, TABLE_HEADERS, ...rows]
        .map(row => row.map(v => `"${String(v).replace(/"/g, '""')}"`).join(','))
        .join('\r\n');

    const blob = new Blob(['﻿' + lines], { type: 'text/csv;charset=utf-8;' });
    triggerDownload(blob, `nexus_fault_report_${datestamp()}.csv`);
};

// ── PDF ────────────────────────────────────────────────────────────────────────

export const exportPDF = (data, filterLabel = 'All') => {
    const s   = buildSummary(data, filterLabel);
    const doc = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
    const W   = doc.internal.pageSize.getWidth();
    let   y   = 15;

    // ── Title bar ──
    doc.setFillColor(15, 23, 42);
    doc.rect(0, 0, W, 22, 'F');
    doc.setTextColor(255, 255, 255);
    doc.setFontSize(16);
    doc.setFont('helvetica', 'bold');
    doc.text('NEXUS GRID', 14, 11);
    doc.setFontSize(10);
    doc.setFont('helvetica', 'normal');
    doc.text('ML-Driven Predictive Maintenance System — Fault Log Report', 14, 18);
    doc.setTextColor(148, 163, 184);
    doc.text(`Generated: ${new Date().toLocaleString()}`, W - 14, 11, { align: 'right' });
    doc.text(`Filter: ${filterLabel}`, W - 14, 18, { align: 'right' });
    y = 30;

    // ── Executive Summary ──
    doc.setTextColor(30, 41, 59);
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.text('Executive Summary', 14, y);
    y += 6;

    const summaryRows = [
        ['Period', s.period],
        ['Total Fault Events', String(s.total)],
        ['Critical', String(s.critical)],
        ['Warning', String(s.warning)],
        ['ML-Detected Faults', String(s.mlCount)],
        ['Rule-Based Alarms', String(s.ruleCount)],
        ['Most Frequent Fault', s.topFault ? `${s.topFault[0]} (${s.topFault[1]}×)` : 'N/A'],
    ];

    autoTable(doc, {
        startY: y,
        head: [],
        body: summaryRows,
        theme: 'plain',
        styles: { fontSize: 9, cellPadding: 2 },
        columnStyles: {
            0: { fontStyle: 'bold', cellWidth: 50, fillColor: [241, 245, 249], textColor: [51, 65, 85] },
            1: { textColor: [30, 41, 59] },
        },
        margin: { left: 14, right: 14 },
    });
    y = doc.lastAutoTable.finalY + 8;

    // ── Fault Distribution ──
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Fault Distribution', 14, y);
    y += 4;

    const distRows = Object.entries(s.counts)
        .sort((a, b) => b[1] - a[1])
        .map(([type, count]) => {
            const rows    = data.filter(r => r.alert_type === type);
            const avgConf = rows.filter(r => r.confidence != null).map(r => parseFloat(r.confidence));
            const conf    = avgConf.length ? `${(avgConf.reduce((a, b) => a + b, 0) / avgConf.length * 100).toFixed(0)}%` : 'Rule-based';
            const sev     = rows[0]?.alert_severity || '—';
            return [type, String(count), `${((count / s.total) * 100).toFixed(1)}%`, conf, sev];
        });

    autoTable(doc, {
        startY: y,
        head: [['Fault Type', 'Count', '% of Total', 'Avg Confidence', 'Severity']],
        body: distRows,
        theme: 'striped',
        headStyles: { fillColor: [99, 102, 241], textColor: 255, fontStyle: 'bold', fontSize: 9 },
        styles: { fontSize: 9 },
        margin: { left: 14, right: 14 },
    });
    y = doc.lastAutoTable.finalY + 8;

    // ── Full event log (new page if needed) ──
    if (y > 150) { doc.addPage(); y = 15; }
    doc.setFontSize(12);
    doc.setFont('helvetica', 'bold');
    doc.setTextColor(30, 41, 59);
    doc.text('Complete Fault Event Log', 14, y);
    y += 4;

    autoTable(doc, {
        startY: y,
        head: [TABLE_HEADERS],
        body: data.map(rowValues),
        theme: 'striped',
        headStyles: { fillColor: [15, 23, 42], textColor: 255, fontStyle: 'bold', fontSize: 7.5 },
        styles: { fontSize: 7.5, cellPadding: 1.5, overflow: 'linebreak' },
        columnStyles: {
            2: { cellWidth: 20 },
            4: { cellWidth: 18 },
        },
        didParseCell: (data) => {
            if (data.column.index === 2 && data.section === 'body') {
                const sev = data.cell.raw;
                data.cell.styles.textColor = sev === 'Critical' ? [220, 38, 38] : [217, 119, 6];
                data.cell.styles.fontStyle = 'bold';
            }
        },
        margin: { left: 14, right: 14 },
    });

    // ── Footer on each page ──
    const pages = doc.internal.getNumberOfPages();
    for (let i = 1; i <= pages; i++) {
        doc.setPage(i);
        doc.setFontSize(8);
        doc.setTextColor(148, 163, 184);
        doc.text(`Nexus Grid — Confidential | Page ${i} of ${pages}`, W / 2, doc.internal.pageSize.getHeight() - 8, { align: 'center' });
    }

    doc.save(`nexus_fault_report_${datestamp()}.pdf`);
};

// ── DOCX ───────────────────────────────────────────────────────────────────────

export const exportDOCX = async (data, filterLabel = 'All') => {
    const s = buildSummary(data, filterLabel);

    const heading = (text, level = HeadingLevel.HEADING_1) =>
        new Paragraph({
            text, heading: level,
            spacing: { before: 240, after: 120 },
        });

    const body = (text, bold = false) =>
        new Paragraph({
            children: [new TextRun({ text, bold, size: 20 })],
            spacing: { after: 80 },
        });

    const summaryTable = new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        rows: [
            ['Period', s.period],
            ['Total Fault Events', String(s.total)],
            ['Critical / Warning', `${s.critical} / ${s.warning}`],
            ['ML-Detected / Rule-Based', `${s.mlCount} / ${s.ruleCount}`],
            ['Most Frequent Fault', s.topFault ? `${s.topFault[0]} (${s.topFault[1]}×)` : 'N/A'],
        ].map(([label, value]) => new TableRow({
            children: [
                new TableCell({
                    children: [new Paragraph({ children: [new TextRun({ text: label, bold: true, size: 18 })] })],
                    width: { size: 30, type: WidthType.PERCENTAGE },
                    shading: { type: ShadingType.CLEAR, fill: 'F1F5F9' },
                }),
                new TableCell({
                    children: [new Paragraph({ children: [new TextRun({ text: value, size: 18 })] })],
                }),
            ],
        })),
    });

    const makeHeaderRow = (cols) => new TableRow({
        children: cols.map(text => new TableCell({
            children: [new Paragraph({ children: [new TextRun({ text, bold: true, color: 'FFFFFF', size: 16 })] })],
            shading: { type: ShadingType.CLEAR, fill: '0F172A' },
        })),
        tableHeader: true,
    });

    const distTable = new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        rows: [
            makeHeaderRow(['Fault Type', 'Count', '% of Total', 'Avg Confidence', 'Severity']),
            ...Object.entries(s.counts)
                .sort((a, b) => b[1] - a[1])
                .map(([type, count]) => {
                    const rows    = data.filter(r => r.alert_type === type);
                    const avgConf = rows.filter(r => r.confidence != null).map(r => parseFloat(r.confidence));
                    const conf    = avgConf.length ? `${(avgConf.reduce((a, b) => a + b, 0) / avgConf.length * 100).toFixed(0)}%` : 'Rule-based';
                    const sev     = rows[0]?.alert_severity || '—';
                    const cells   = [type, String(count), `${((count / s.total) * 100).toFixed(1)}%`, conf, sev];
                    return new TableRow({
                        children: cells.map(text => new TableCell({
                            children: [new Paragraph({ children: [new TextRun({ text, size: 16 })] })],
                        })),
                    });
                }),
        ],
    });

    const logTable = new Table({
        width: { size: 100, type: WidthType.PERCENTAGE },
        rows: [
            makeHeaderRow(TABLE_HEADERS),
            ...data.map(r => new TableRow({
                children: rowValues(r).map(text => new TableCell({
                    children: [new Paragraph({ children: [new TextRun({ text, size: 14 })] })],
                })),
            })),
        ],
    });

    const doc = new Document({
        sections: [{
            properties: {},
            children: [
                new Paragraph({
                    children: [new TextRun({ text: 'NEXUS GRID', bold: true, size: 48, color: '4F46E5' })],
                    alignment: AlignmentType.CENTER,
                }),
                new Paragraph({
                    children: [new TextRun({ text: 'ML-Driven Predictive Maintenance System', size: 24, color: '64748B' })],
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 120 },
                }),
                new Paragraph({
                    children: [new TextRun({ text: 'Fault Log Report', bold: true, size: 36 })],
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 80 },
                }),
                new Paragraph({
                    children: [new TextRun({ text: `Generated: ${new Date().toLocaleString()}  |  Filter: ${filterLabel}`, size: 18, color: '94A3B8' })],
                    alignment: AlignmentType.CENTER,
                    spacing: { after: 480 },
                }),
                heading('1. Executive Summary'),
                summaryTable,
                heading('2. Fault Distribution'),
                distTable,
                heading('3. Complete Fault Event Log'),
                body(`Total records: ${data.length}`),
                logTable,
            ],
        }],
    });

    const buffer = await Packer.toBlob(doc);
    triggerDownload(buffer, `nexus_fault_report_${datestamp()}.docx`);
};

// ── Util ───────────────────────────────────────────────────────────────────────

const datestamp = () => new Date().toISOString().slice(0, 16).replace('T', '_').replace(':', '-');

const triggerDownload = (blob, filename) => {
    const url = URL.createObjectURL(blob);
    const a   = document.createElement('a');
    a.href    = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
};
